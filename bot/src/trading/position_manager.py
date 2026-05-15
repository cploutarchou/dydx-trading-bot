"""Position entry and exit management for pairs trading."""

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import pandas as pd
from loguru import logger

from src.constants import (
    CLOSE_AT_ZSCORE_CROSS,
    USD_MIN_COLLATERAL,
    USD_PER_TRADE,
    ZSCORE_THRESH,
)
from src.infrastructure.domain.cointegration_storage import pair_storage
from src.shared.notifications import TelegramMessenger
from src.shared.utils import format_number
from src.trading.account_manager import (
    get_account,
    get_open_positions,
    get_order,
    is_open_positions,
    place_market_order,
)
from src.trading.analysis.cointegration import calculate_zscore
from src.trading.arbitrage_observability import increment_metric, record_rejection
from src.trading.arbitrage_runtime_config import (
    is_arbitrage_improvements_enabled,
    is_pair_priority_engine_enabled,
    pair_priority_max_pairs,
)
from src.trading.bot_agent import BotAgent
from src.trading.bot_agents_state import (
    BOT_AGENTS_PATH,
    append_tracked_position,
    load_tracked_positions,
    save_processed_positions,
)
from src.trading.market_data import get_candles_recent, get_markets
from src.trading.pair_priority import prioritize_pairs
from src.trading.trade_persistence import (
    persist_live_trade_closed,
    persist_live_trade_opened,
    persist_trade_activity_event,
)

IGNORE_ASSETS = [
    "BTC-USD_x",
    "BTC-USD_y",
]  # Ignore these assets which are not trading on testnet


# Per-pair entry failure backoff state to avoid hammering failing markets.
# key: "BASE|QUOTE" -> {"failure_count": int, "next_retry_at": float, "last_error": str}
_ENTRY_FAILURE_STATE: Dict[str, Dict[str, Any]] = {}


def _as_float(value: Any, *, field_name: str) -> float:
    """Convert numeric-like runtime values to float with explicit failures."""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {field_name}: {value!r}") from exc


def _as_numeric_series(values: Any, *, field_name: str) -> pd.Series:
    """Convert iterable/Series values to a numeric float pandas Series."""
    series = values if isinstance(values, pd.Series) else pd.Series(values)
    numeric_series = pd.to_numeric(series, errors="coerce")
    if numeric_series.isna().any():
        raise ValueError(f"Invalid numeric series for {field_name}")
    return numeric_series.astype(float)


def _entry_backoff_now() -> float:
    return time.monotonic()


def _entry_pair_key(base_market: str, quote_market: str) -> str:
    return f"{base_market}|{quote_market}"


def _entry_backoff_seconds(failure_count: int) -> float:
    base = float(os.getenv("ENTRY_FAILURE_BACKOFF_BASE_SECONDS", "15") or "15")
    mult = float(os.getenv("ENTRY_FAILURE_BACKOFF_MULTIPLIER", "2") or "2")
    max_seconds = float(os.getenv("ENTRY_FAILURE_BACKOFF_MAX_SECONDS", "180") or "180")
    exponent = max(0, int(failure_count) - 1)
    delay = base * (mult**exponent)
    return min(max_seconds, max(base, delay))


def _entry_should_skip_pair(pair_key: str) -> tuple[bool, float]:
    state = _ENTRY_FAILURE_STATE.get(pair_key)
    if not state:
        return False, 0.0
    next_retry_at = float(state.get("next_retry_at", 0.0) or 0.0)
    remaining = next_retry_at - _entry_backoff_now()
    return (remaining > 0), max(0.0, remaining)


def _record_entry_failure(pair_key: str, error: Any):
    current = _ENTRY_FAILURE_STATE.get(pair_key, {})
    failure_count = int(current.get("failure_count", 0) or 0) + 1
    cooldown = _entry_backoff_seconds(failure_count)
    _ENTRY_FAILURE_STATE[pair_key] = {
        "failure_count": failure_count,
        "next_retry_at": _entry_backoff_now() + cooldown,
        "last_error": str(error),
        "last_failure_at": _utc_now_iso(),
    }


def _record_entry_success(pair_key: str):
    if pair_key in _ENTRY_FAILURE_STATE:
        _ENTRY_FAILURE_STATE.pop(pair_key, None)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_recent_candles_for_cycle(
    client,
    market: str,
    cycle_cache: Optional[Dict[str, Any]],
):
    if not is_arbitrage_improvements_enabled() or cycle_cache is None:
        return await get_candles_recent(client, market)
    if market in cycle_cache:
        increment_metric("duplicate_api_calls_avoided_total")
        increment_metric("exchange_api_calls_saved_total")
        logger.debug("scan_cycle_candle_cache_hit market={}", market)
        return cycle_cache[market]
    result = await get_candles_recent(client, market)
    cycle_cache[market] = result
    return result


async def _resolve_leg_open_state(
    client,
    *,
    base_market: str,
    quote_market: str,
    scan_cycle_id: str,
) -> tuple[bool, bool]:
    """Resolve whether either leg is already open, with safe fallback behavior."""
    if is_arbitrage_improvements_enabled():
        try:
            open_positions_snapshot = await get_open_positions(client)
            is_base_open = base_market in open_positions_snapshot
            is_quote_open = quote_market in open_positions_snapshot
            increment_metric("duplicate_api_calls_avoided_total")
            increment_metric("exchange_api_calls_saved_total")
            return is_base_open, is_quote_open
        except Exception as exc:
            logger.warning(
                "scan_cycle={} position_snapshot_failed pair={}/{} error={} falling_back_to_legacy_checks",
                scan_cycle_id,
                base_market,
                quote_market,
                exc,
            )

    is_base_open = await is_open_positions(client, base_market)
    is_quote_open = await is_open_positions(client, quote_market)
    return is_base_open, is_quote_open


def _build_trade_opened_notification(
    bot_open_dict: Dict[str, Any],
    *,
    fallback_base_market: str = "",
    fallback_quote_market: str = "",
    fallback_base_side: str = "",
    fallback_quote_side: str = "",
    fallback_base_size: Any = 0,
    fallback_quote_size: Any = 0,
    fallback_z_score: Any = 0,
    fallback_hedge_ratio: Any = 0,
    fallback_half_life: Any = 0,
) -> Dict[str, Any]:
    """Map BotAgent.open_trades() fields into Telegram's opened-trade payload."""
    base_market = bot_open_dict.get("market_1", "") or fallback_base_market
    quote_market = bot_open_dict.get("market_2", "") or fallback_quote_market
    return {
        "pair": f"{base_market} / {quote_market}",
        "base_market": base_market,
        "quote_market": quote_market,
        "base_side": bot_open_dict.get("order_m1_side", "") or fallback_base_side,
        "quote_side": bot_open_dict.get("order_m2_side", "") or fallback_quote_side,
        "base_size": bot_open_dict.get("order_m1_size", 0) or fallback_base_size,
        "quote_size": bot_open_dict.get("order_m2_size", 0) or fallback_quote_size,
        "z_score": bot_open_dict.get("z_score", 0) or fallback_z_score,
        "hedge_ratio": bot_open_dict.get("hedge_ratio", 0) or fallback_hedge_ratio,
        "half_life": bot_open_dict.get("half_life", 0) or fallback_half_life,
        "market_1_order_id": bot_open_dict.get("order_id_m1", ""),
        "market_2_order_id": bot_open_dict.get("order_id_m2", ""),
    }


def _opposite_order_side(side: str) -> str:
    normalized = str(side).upper()
    if normalized == "BUY":
        return "SELL"
    if normalized == "SELL":
        return "BUY"
    raise ValueError(f"Unsupported order side: {side}")


def _close_side_from_exchange_position(
    position: Dict[str, Any], fallback_side: str
) -> str:
    exchange_side = str(position.get("side", "")).upper()
    if exchange_side == "LONG":
        return "SELL"
    if exchange_side == "SHORT":
        return "BUY"
    return _opposite_order_side(fallback_side)


def _close_size_from_exchange_position(
    position: Dict[str, Any], fallback_size: Any
) -> Any:
    return position.get("sumOpen") or position.get("size") or fallback_size


def _failsafe_close_price(
    market: str,
    side: str,
    exchange_position: Optional[Dict[str, Any]],
    markets: Dict[str, Any],
    fallback_price: Any = None,
) -> str:
    raw_price = (
        (exchange_position or {}).get("entryPrice")
        or (exchange_position or {}).get("price")
        or fallback_price
    )
    price = float(raw_price)
    accept_price = price * 1.7 if side == "BUY" else price * 0.3
    tick_size = markets["markets"][market]["tickSize"]
    return format_number(accept_price, tick_size)


async def _place_reduce_only_close_with_retries(
    client,
    *,
    market: str,
    side: str,
    size: Any,
    price: Any,
    attempts: int = 3,
) -> tuple[Dict[str, Any], str]:
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return await place_market_order(
                client,
                market=market,
                side=side,
                size=size,
                price=price,
                reduce_only=True,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Reduce-only close attempt {}/{} failed for {}: {}",
                attempt,
                attempts,
                market,
                exc,
            )
            if attempt < attempts:
                await asyncio.sleep(min(2.0, 0.5 * attempt))
    raise RuntimeError(f"Failed reduce-only close for {market}") from last_error


async def _close_orphan_exchange_leg(
    client,
    *,
    tracked_position: Dict[str, Any],
    exchange_positions: Dict[str, Any],
    orphan_market: str,
    fallback_side: str,
    fallback_size: Any,
    messenger: TelegramMessenger,
) -> bool:
    markets = await get_markets(client)
    exchange_position = exchange_positions.get(orphan_market, {})
    close_side = _close_side_from_exchange_position(exchange_position, fallback_side)
    close_size = _close_size_from_exchange_position(exchange_position, fallback_size)
    close_price = _failsafe_close_price(
        orphan_market,
        close_side,
        exchange_position,
        markets,
    )

    try:
        _, close_order_id = await _place_reduce_only_close_with_retries(
            client,
            market=orphan_market,
            side=close_side,
            size=close_size,
            price=close_price,
            attempts=3,
        )
        messenger.send_recovery_message(
            "Recovered Orphaned Position Leg",
            f"Submitted reduce-only close for orphaned {orphan_market} leg. Close order: {close_order_id}",
            category="execution_orphan_recovery",
        )
        logger.critical(
            "Recovered orphaned {} leg for pair {} / {} with close order {}",
            orphan_market,
            tracked_position.get("market_1"),
            tracked_position.get("market_2"),
            close_order_id,
        )
        persist_trade_activity_event(
            "trade_exit_orphan_recovered",
            f"Recovered orphaned {orphan_market} leg with reduce-only close",
            severity="warning",
            details={
                "market_1": tracked_position.get("market_1"),
                "market_2": tracked_position.get("market_2"),
                "orphan_market": orphan_market,
                "close_order_id": close_order_id,
            },
        )
        return True
    except Exception as exc:
        tracked_position["pair_status"] = "ORPHANED_EXIT_FAILED"
        tracked_position["orphaned_market"] = orphan_market
        tracked_position["last_orphan_recovery_error"] = str(exc)
        tracked_position["last_orphan_recovery_at"] = _utc_now_iso()
        messenger.send_error_message(
            "CRITICAL: Orphaned Position Leg",
            (
                f"Failed to close orphaned {orphan_market} leg for "
                f"{tracked_position.get('market_1')} / "
                f"{tracked_position.get('market_2')}: {exc}"
            ),
            is_critical=True,
            category="execution_orphan_recovery_failed",
        )
        logger.critical(
            "Failed to recover orphaned {} leg for pair {} / {}: {}",
            orphan_market,
            tracked_position.get("market_1"),
            tracked_position.get("market_2"),
            exc,
        )
        persist_trade_activity_event(
            "trade_exit_orphan_recovery_failed",
            f"Failed orphaned leg recovery for {orphan_market}: {exc}",
            severity="critical",
            details={
                "market_1": tracked_position.get("market_1"),
                "market_2": tracked_position.get("market_2"),
                "orphan_market": orphan_market,
                "error": str(exc),
            },
        )
        return False


async def open_positions(client):
    """
    Manage finding triggers for trade entry.

    Load cointegrated pairs and open positions when Z-score threshold is met.
    Store trades for managing later via exit function.
    """

    scan_cycle_id = uuid4().hex[:12]
    increment_metric("arbitrage_scan_cycles_total")

    # Initialize Telegram messenger
    messenger = TelegramMessenger()

    # Load cointegrated pairs using enhanced storage
    pairs = pair_storage.load_pairs()
    logger.info("Loaded {} cointegrated pairs from enhanced storage", len(pairs))

    if not pairs:
        logger.warning("No cointegrated pairs found")
        return

    # Get markets from referencing of min order size, tick size etc
    markets = await get_markets(client)
    market_map = markets.get("markets", {}) if isinstance(markets, dict) else {}

    priority_scores = []
    pair_priority_enabled = is_pair_priority_engine_enabled()
    if pair_priority_enabled:
        max_pairs = pair_priority_max_pairs()
        pairs, priority_scores = prioritize_pairs(
            pairs,
            market_map=market_map,
            max_pairs=max_pairs,
        )
        if priority_scores:
            top = priority_scores[0]
            logger.info(
                "scan_cycle={} pair_priority_top pair={} score={:.4f} reasons={}",
                scan_cycle_id,
                top.pair,
                top.score,
                ",".join(top.explanation),
            )

    increment_metric("pair_candidates_total", len(pairs))

    # Convert to DataFrame for backward compatibility with existing logic
    df = pd.DataFrame([pair.to_dict() for pair in pairs])
    cycle_candle_cache: Optional[Dict[str, Any]] = (
        {} if is_arbitrage_improvements_enabled() else None
    )
    logger.info(
        "arbitrage_scan_cycle_start cycle_id={} pair_candidates={} pair_priority_enabled={}",
        scan_cycle_id,
        len(df),
        pair_priority_enabled,
    )

    # Find ZScore triggers
    for index, row in df.iterrows():

        # Extract variables
        base_market = row["base_market"]
        quote_market = row["quote_market"]
        pair_key = _entry_pair_key(base_market, quote_market)
        try:
            hedge_ratio = _as_float(row["hedge_ratio"], field_name="hedge_ratio")
            half_life = _as_float(row["half_life"], field_name="half_life")
        except ValueError as exc:
            increment_metric("pair_candidates_skipped_total")
            logger.warning(
                "scan_cycle={} pair_skipped pair={}/{} reason=invalid_pair_data error={}",
                scan_cycle_id,
                base_market,
                quote_market,
                exc,
            )
            continue

        # Continue if ignore asset
        if base_market in IGNORE_ASSETS or quote_market in IGNORE_ASSETS:
            increment_metric("pair_candidates_skipped_total")
            logger.debug(
                "scan_cycle={} pair_skipped pair={}/{} reason=ignored_asset",
                scan_cycle_id,
                base_market,
                quote_market,
            )
            continue

        skip_pair, remaining = _entry_should_skip_pair(pair_key)
        if skip_pair:
            increment_metric("pair_candidates_skipped_total")
            logger.debug(
                "scan_cycle={} pair_skipped pair={}/{} reason=entry_cooldown remaining_seconds={:.1f}",
                scan_cycle_id,
                base_market,
                quote_market,
                remaining,
            )
            continue

        # Get prices
        try:
            series_1 = await _get_recent_candles_for_cycle(
                client, base_market, cycle_candle_cache
            )
            series_2 = await _get_recent_candles_for_cycle(
                client, quote_market, cycle_candle_cache
            )
        except Exception:
            increment_metric("pair_candidates_skipped_total")
            increment_metric("stale_data_detected_total")
            logger.exception(
                "Failed to fetch candles for {} / {}", base_market, quote_market
            )
            continue

        # Get ZScore
        if len(series_1) > 0 and len(series_1) == len(series_2):
            try:
                series_1_numeric = _as_numeric_series(series_1, field_name="series_1")
                series_2_numeric = _as_numeric_series(series_2, field_name="series_2")
            except ValueError as exc:
                increment_metric("pair_candidates_skipped_total")
                logger.warning(
                    "scan_cycle={} pair_skipped pair={}/{} reason=invalid_series_data error={}",
                    scan_cycle_id,
                    base_market,
                    quote_market,
                    exc,
                )
                continue

            spread = series_1_numeric - (hedge_ratio * series_2_numeric)
            try:
                z_score = _as_float(
                    calculate_zscore(spread).values.tolist()[-1],
                    field_name="z_score",
                )
            except ValueError as exc:
                increment_metric("pair_candidates_skipped_total")
                logger.warning(
                    "scan_cycle={} pair_skipped pair={}/{} reason=invalid_z_score error={}",
                    scan_cycle_id,
                    base_market,
                    quote_market,
                    exc,
                )
                continue

            # Establish if potential trade
            if abs(z_score) >= ZSCORE_THRESH:
                increment_metric("opportunities_detected_total")
                logger.info(
                    "scan_cycle={} opportunity_detected pair={}/{} z_score={:.6f} threshold={:.6f}",
                    scan_cycle_id,
                    base_market,
                    quote_market,
                    float(z_score),
                    float(ZSCORE_THRESH),
                )

                # Ensure like-for-like not already open (diversify trading)
                is_base_open, is_quote_open = await _resolve_leg_open_state(
                    client,
                    base_market=base_market,
                    quote_market=quote_market,
                    scan_cycle_id=scan_cycle_id,
                )

                # Place trade
                if not is_base_open and not is_quote_open:

                    # Determine side
                    base_side = "BUY" if z_score < 0 else "SELL"
                    quote_side = "BUY" if z_score > 0 else "SELL"

                    # Get acceptable price in string format with correct number of decimals
                    base_price = _as_float(
                        series_1_numeric.iloc[-1], field_name="base_price"
                    )
                    quote_price = _as_float(
                        series_2_numeric.iloc[-1], field_name="quote_price"
                    )
                    accept_base_price = (
                        base_price * 1.01 if z_score < 0 else base_price * 0.99
                    )
                    accept_quote_price = (
                        quote_price * 1.01 if z_score > 0 else quote_price * 0.99
                    )
                    failsafe_base_price = (
                        base_price * 0.05 if z_score < 0 else base_price * 1.7
                    )
                    base_tick_size = markets["markets"][base_market]["tickSize"]
                    quote_tick_size = markets["markets"][quote_market]["tickSize"]

                    # Format prices
                    accept_base_price = format_number(accept_base_price, base_tick_size)
                    accept_quote_price = format_number(
                        accept_quote_price, quote_tick_size
                    )
                    accept_failsafe_base_price = format_number(
                        failsafe_base_price, base_tick_size
                    )

                    # Get size
                    base_quantity = 1 / base_price * USD_PER_TRADE
                    quote_quantity = 1 / quote_price * USD_PER_TRADE
                    base_step_size = markets["markets"][base_market]["stepSize"]
                    quote_step_size = markets["markets"][quote_market]["stepSize"]

                    # Format sizes
                    base_size = format_number(base_quantity, base_step_size)
                    quote_size = format_number(quote_quantity, quote_step_size)

                    # Ensure size (minimum order size greater than $1 according to V4 documentation)
                    base_min_order_size = 1 / float(
                        markets["markets"][base_market]["oraclePrice"]
                    )
                    quote_min_order_size = 1 / float(
                        markets["markets"][quote_market]["oraclePrice"]
                    )

                    # Combine checks
                    check_base = float(base_quantity) > base_min_order_size
                    check_quote = float(quote_quantity) > quote_min_order_size

                    # If checks pass, place trades
                    if check_base and check_quote:

                        # Check account balance
                        account = await get_account(client)
                        free_collateral = float(account["freeCollateral"])
                        logger.info(
                            "Free collateral {:.2f} (min required {:.2f})",
                            free_collateral,
                            USD_MIN_COLLATERAL,
                        )

                        # P1.6: Guard 1 - Ensure minimum collateral
                        if free_collateral < USD_MIN_COLLATERAL:
                            record_rejection("insufficient_collateral")
                            logger.warning(
                                "scan_cycle={} opportunity_rejected pair={}/{} "
                                "reason=insufficient_collateral free_collateral={:.2f} "
                                "min_required={:.2f}",
                                scan_cycle_id,
                                base_market,
                                quote_market,
                                free_collateral,
                                USD_MIN_COLLATERAL,
                            )
                            break

                        # P1.6: Guard 2 - Ensure buffer above trade size (fail-safe for subsequent trades)
                        # Keep at least 1.25x min collateral remaining after this trade
                        COLLATERAL_BUFFER_RATIO = 1.25
                        remaining_after_trade = free_collateral - USD_PER_TRADE
                        required_buffer = USD_MIN_COLLATERAL * COLLATERAL_BUFFER_RATIO
                        if remaining_after_trade < required_buffer:
                            record_rejection("collateral_buffer")
                            logger.warning(
                                "scan_cycle={} opportunity_rejected pair={}/{} "
                                "reason=collateral_buffer free_collateral={:.2f} "
                                "usd_per_trade={:.2f} required_buffer={:.2f}",
                                scan_cycle_id,
                                base_market,
                                quote_market,
                                free_collateral,
                                USD_PER_TRADE,
                                required_buffer,
                            )
                            break

                        # Create Bot Agent
                        bot_agent = BotAgent(
                            client,
                            market_1=base_market,
                            market_2=quote_market,
                            base_side=base_side,
                            base_size=base_size,
                            base_price=accept_base_price,
                            quote_side=quote_side,
                            quote_size=quote_size,
                            quote_price=accept_quote_price,
                            accept_failsafe_base_price=accept_failsafe_base_price,
                            z_score=z_score,
                            half_life=half_life,
                            hedge_ratio=hedge_ratio,
                        )

                        # Open Trades
                        persist_trade_activity_event(
                            "trade_entry_attempt_started",
                            f"Entry attempt for {base_market} / {quote_market}",
                            details={
                                "market_1": base_market,
                                "market_2": quote_market,
                                "z_score": float(z_score),
                                "hedge_ratio": float(hedge_ratio),
                            },
                        )
                        try:
                            bot_open_dict = await bot_agent.open_trades()
                        except Exception as exc:
                            record_rejection("entry_execution_failed")
                            _record_entry_failure(pair_key, exc)
                            persist_trade_activity_event(
                                "trade_entry_attempt_failed",
                                f"Entry execution failed for {base_market} / {quote_market}: {exc}",
                                severity="error",
                                details={
                                    "market_1": base_market,
                                    "market_2": quote_market,
                                    "error": str(exc),
                                    "failure_count": int(
                                        _ENTRY_FAILURE_STATE.get(pair_key, {}).get(
                                            "failure_count", 0
                                        )
                                    ),
                                },
                            )
                            logger.exception(
                                "Entry execution failed for {} / {}; applying cooldown",
                                base_market,
                                quote_market,
                            )
                            continue

                        # Guard: Handle failure
                        if bot_open_dict == "failed":
                            record_rejection("bot_agent_failed")
                            _record_entry_failure(pair_key, "bot_agent returned failed")
                            persist_trade_activity_event(
                                "trade_entry_attempt_failed",
                                f"Bot agent returned failed for {base_market} / {quote_market}",
                                severity="error",
                                details={
                                    "market_1": base_market,
                                    "market_2": quote_market,
                                    "failure_count": int(
                                        _ENTRY_FAILURE_STATE.get(pair_key, {}).get(
                                            "failure_count", 0
                                        )
                                    ),
                                },
                            )
                            logger.warning(
                                "Bot agent failed to open trades for {} / {}",
                                base_market,
                                quote_market,
                            )
                            continue

                        # Handle success in opening trades
                        if (
                            isinstance(bot_open_dict, dict)
                            and bot_open_dict.get("pair_status") == "LIVE"
                        ):
                            increment_metric("opportunities_executed_total")
                            _record_entry_success(pair_key)
                            # Send trade opened notification before deleting bot_open_dict
                            trade_info = _build_trade_opened_notification(
                                bot_open_dict,
                                fallback_base_market=base_market,
                                fallback_quote_market=quote_market,
                                fallback_base_side=base_side,
                                fallback_quote_side=quote_side,
                                fallback_base_size=base_size,
                                fallback_quote_size=quote_size,
                                fallback_z_score=z_score,
                                fallback_hedge_ratio=hedge_ratio,
                                fallback_half_life=half_life,
                            )
                            messenger.send_trade_opened_message(trade_info)

                            # Save trade using atomic per-instance state update.
                            await append_tracked_position(bot_open_dict)
                            persisted_trade_id = persist_live_trade_opened(
                                bot_open_dict
                            )
                            persist_trade_activity_event(
                                "trade_entry_opened",
                                f"Opened live trade for {base_market} / {quote_market}",
                                details={
                                    "market_1": base_market,
                                    "market_2": quote_market,
                                    "z_score": float(
                                        bot_open_dict.get("z_score", z_score)
                                    ),
                                    "order_id_m1": bot_open_dict.get("order_id_m1"),
                                    "order_id_m2": bot_open_dict.get("order_id_m2"),
                                },
                                related_trade_id=persisted_trade_id,
                            )
                            del bot_open_dict

                            # Confirm live status in print
                            logger.info(
                                "Trade status: Live for {} / {}",
                                base_market,
                                quote_market,
                            )
                        elif isinstance(bot_open_dict, dict):
                            record_rejection("non_live_pair_status")
                            _record_entry_failure(
                                pair_key,
                                f"bot_agent pair_status={bot_open_dict.get('pair_status', 'unknown')}",
                            )
                            persist_trade_activity_event(
                                "trade_entry_attempt_failed",
                                f"Bot agent returned non-live status for {base_market} / {quote_market}",
                                severity="warning",
                                details={
                                    "market_1": base_market,
                                    "market_2": quote_market,
                                    "pair_status": bot_open_dict.get(
                                        "pair_status", "unknown"
                                    ),
                                    "comments": bot_open_dict.get("comments", ""),
                                    "failure_count": int(
                                        _ENTRY_FAILURE_STATE.get(pair_key, {}).get(
                                            "failure_count", 0
                                        )
                                    ),
                                },
                            )

                    else:
                        record_rejection("min_order_size")
                        logger.debug(
                            "scan_cycle={} opportunity_rejected pair={}/{} "
                            "reason=min_order_size base_check={} quote_check={}",
                            scan_cycle_id,
                            base_market,
                            quote_market,
                            check_base,
                            check_quote,
                        )
                else:
                    record_rejection("market_already_open")
                    logger.debug(
                        "scan_cycle={} opportunity_rejected pair={}/{} "
                        "reason=market_already_open base_open={} quote_open={}",
                        scan_cycle_id,
                        base_market,
                        quote_market,
                        is_base_open,
                        is_quote_open,
                    )
            else:
                logger.debug(
                    "scan_cycle={} pair_no_opportunity pair={}/{} z_score={:.6f} threshold={:.6f}",
                    scan_cycle_id,
                    base_market,
                    quote_market,
                    z_score,
                    float(ZSCORE_THRESH),
                )
        else:
            increment_metric("pair_candidates_skipped_total")
            increment_metric("stale_data_detected_total")
            logger.debug(
                "scan_cycle={} pair_skipped pair={}/{} reason=invalid_series_lengths len_1={} len_2={}",
                scan_cycle_id,
                base_market,
                quote_market,
                len(series_1),
                len(series_2),
            )

    logger.info("arbitrage_scan_cycle_complete cycle_id={}", scan_cycle_id)


async def manage_trade_exits(client):
    """
    Manage exiting open positions based on exit criteria.

    Checks Z-score levels and closes positions when reversion occurs.
    """

    # Initialize Telegram messenger
    messenger = TelegramMessenger()

    # Initialize saving output
    save_output = []

    open_positions_dict = await load_tracked_positions()
    logger.debug("Loaded {} tracked positions", len(open_positions_dict))
    if not BOT_AGENTS_PATH.exists() and len(open_positions_dict) == 0:
        logger.info("No {} found; nothing to close", BOT_AGENTS_PATH)
        return "complete"

    # Guard: Exit if no open positions in file
    if len(open_positions_dict) < 1:
        return "complete"

    # Get all open positions per trading platform
    exchange_pos = await get_open_positions(client)
    logger.debug("Exchange reports {} open positions", len(exchange_pos))

    # Create live position tickers list
    markets_live = list(exchange_pos.keys())

    # Protect API
    await asyncio.sleep(0.5)

    # Check all saved positions match order record
    # Exit trade according to any exit trade rules
    for position in open_positions_dict:

        # Initialize is_close trigger
        is_close = False

        # Extract position matching information from file - market 1
        position_market_m1 = position["market_1"]
        position_size_m1 = position["order_m1_size"]
        position_side_m1 = position["order_m1_side"]

        # Extract position matching information from file - market 2
        position_market_m2 = position["market_2"]
        position_size_m2 = position["order_m2_size"]
        position_side_m2 = position["order_m2_side"]

        # Protect API
        await asyncio.sleep(0.5)

        # Get order info m1 per exchange
        order_m1 = await get_order(client, position["order_id_m1"])
        order_market_m1 = order_m1["ticker"]
        order_size_m1 = order_m1["size"]
        order_side_m1 = order_m1["side"]

        # Protect API Rate limits
        await asyncio.sleep(0.5)

        # Get order info m2 per exchange
        order_m2 = await get_order(client, position["order_id_m2"])
        order_market_m2 = order_m2["ticker"]
        order_size_m2 = order_m2["size"]
        order_side_m2 = order_m2["side"]

        ## New: Ensure sizes match what was sent to the exchange
        # Override size to match what DYDX exchange has
        position_size_m1 = order_m1["size"]
        position_size_m2 = order_m2["size"]

        # Perform matching checks
        check_m1 = (
            position_market_m1 == order_market_m1
            and position_size_m1 == order_size_m1
            and position_side_m1 == order_side_m1
        )
        check_m2 = (
            position_market_m2 == order_market_m2
            and position_size_m2 == order_size_m2
            and position_side_m2 == order_side_m2
        )
        m1_live = position_market_m1 in markets_live
        m2_live = position_market_m2 in markets_live
        check_live = m1_live and m2_live

        # Guard: If not all match exit with error
        if not check_m1 or not check_m2 or not check_live:
            if check_m1 and check_m2 and (m1_live != m2_live):
                orphan_market = position_market_m1 if m1_live else position_market_m2
                orphan_side = position_side_m1 if m1_live else position_side_m2
                orphan_size = position_size_m1 if m1_live else position_size_m2
                logger.critical(
                    "Detected one-sided orphaned exposure for {} / {}; attempting reduce-only close on {}",
                    position_market_m1,
                    position_market_m2,
                    orphan_market,
                )
                recovered = await _close_orphan_exchange_leg(
                    client,
                    tracked_position=position,
                    exchange_positions=exchange_pos,
                    orphan_market=orphan_market,
                    fallback_side=orphan_side,
                    fallback_size=orphan_size,
                    messenger=messenger,
                )
                if not recovered:
                    save_output.append(position)
                continue

            if check_m1 and check_m2 and not m1_live and not m2_live:
                logger.warning(
                    "Tracked pair {} / {} is no longer open on exchange; removing local state",
                    position_market_m1,
                    position_market_m2,
                )
                continue

            logger.error(
                "Position mismatch for {} / {}; local state diverged from exchange",
                position_market_m1,
                position_market_m2,
            )
            logger.error(
                "Program does not recognise some open positions. Manual intervention required."
            )
            raise RuntimeError(
                f"Exchange/local state mismatch for {position_market_m1}/{position_market_m2}"
            )

        # Get prices
        series_1 = await get_candles_recent(client, position_market_m1)
        await asyncio.sleep(0.2)
        series_2 = await get_candles_recent(client, position_market_m2)
        await asyncio.sleep(0.2)

        series_1_numeric = _as_numeric_series(series_1, field_name="series_1_exit")
        series_2_numeric = _as_numeric_series(series_2, field_name="series_2_exit")

        # Get markets for reference of tick size
        markets = await get_markets(client)
        z_score_traded: float = _as_float(
            position["z_score"], field_name="z_score_traded"
        )
        z_score_current: float = z_score_traded

        # Protect API
        await asyncio.sleep(0.2)

        # Trigger close based on Z-Score
        if CLOSE_AT_ZSCORE_CROSS:

            # Initialize z_scores
            hedge_ratio = _as_float(position["hedge_ratio"], field_name="hedge_ratio")
            if len(series_1_numeric) > 0 and len(series_1_numeric) == len(
                series_2_numeric
            ):
                spread = series_1_numeric - (hedge_ratio * series_2_numeric)
                z_score_current = _as_float(
                    calculate_zscore(spread).values.tolist()[-1],
                    field_name="z_score_current",
                )

            # Determine trigger
            z_score_level_check = abs(z_score_current) >= abs(z_score_traded)
            z_score_cross_check = (z_score_current < 0 < z_score_traded) or (
                z_score_current > 0 > z_score_traded
            )

            # Close trade
            if z_score_level_check and z_score_cross_check:
                # Initiate close trigger
                is_close = True

        # Close positions if triggered
        if is_close:

            # Determine side - m1
            side_m1 = "SELL"
            if position_side_m1 == "SELL":
                side_m1 = "BUY"

            # Determine side - m2
            side_m2 = "SELL"
            if position_side_m2 == "SELL":
                side_m2 = "BUY"

            # Get and format Price
            price_m1 = _as_float(series_1_numeric.iloc[-1], field_name="price_m1")
            price_m2 = _as_float(series_2_numeric.iloc[-1], field_name="price_m2")
            accept_price_m1 = price_m1 * 1.05 if side_m1 == "BUY" else price_m1 * 0.95
            accept_price_m2 = price_m2 * 1.05 if side_m2 == "BUY" else price_m2 * 0.95
            tick_size_m1 = markets["markets"][position_market_m1]["tickSize"]
            tick_size_m2 = markets["markets"][position_market_m2]["tickSize"]
            accept_price_m1 = format_number(accept_price_m1, tick_size_m1)
            accept_price_m2 = format_number(accept_price_m2, tick_size_m2)

            # Close positions
            close_order_m1 = None
            close_order_m2 = None
            close_order_m1_id = ""
            close_order_m2_id = ""
            persist_trade_activity_event(
                "trade_exit_attempt_started",
                f"Exit trigger for {position_market_m1} / {position_market_m2}",
                details={
                    "market_1": position_market_m1,
                    "market_2": position_market_m2,
                    "z_score_current": float(z_score_current),
                    "z_score_traded": float(z_score_traded),
                },
            )
            try:

                # Close position for market 1
                logger.info(
                    "Closing position for {} (subaccount inferred)",
                    position_market_m1,
                )

                close_order_m1, close_order_m1_id = (
                    await _place_reduce_only_close_with_retries(
                        client,
                        market=position_market_m1,
                        side=side_m1,
                        size=position_size_m1,
                        price=accept_price_m1,
                        attempts=3,
                    )
                )

                logger.debug("Close order m1 id: {}", close_order_m1.get("id"))

                # Protect API
                await asyncio.sleep(1)

                # Close position for market 2
                logger.info(
                    "Closing position for {} (subaccount inferred)",
                    position_market_m2,
                )

                close_order_m2, close_order_m2_id = (
                    await _place_reduce_only_close_with_retries(
                        client,
                        market=position_market_m2,
                        side=side_m2,
                        size=position_size_m2,
                        price=accept_price_m2,
                        attempts=3,
                    )
                )

                logger.debug("Close order m2 id: {}", close_order_m2.get("id"))

                # Send trade closed notification
                trade_info = {
                    "pair": f"{position_market_m1} / {position_market_m2}",
                    "base_market": position_market_m1,
                    "quote_market": position_market_m2,
                    "base_side": side_m1,
                    "quote_side": side_m2,
                    "base_size": position_size_m1,
                    "quote_size": position_size_m2,
                    "z_score": z_score_current,
                    "close_order_m1_id": close_order_m1_id,
                    "close_order_m2_id": close_order_m2_id,
                }
                messenger.send_trade_closed_message(trade_info, "Z-score reversion")
                persisted_trade_id = persist_live_trade_closed(
                    position,
                    exit_price1=accept_price_m1,
                    exit_price2=accept_price_m2,
                    exit_size1=position_size_m1,
                    exit_size2=position_size_m2,
                )
                persist_trade_activity_event(
                    "trade_exit_closed",
                    f"Closed trade for {position_market_m1} / {position_market_m2}",
                    details={
                        "market_1": position_market_m1,
                        "market_2": position_market_m2,
                        "close_order_m1_id": close_order_m1_id,
                        "close_order_m2_id": close_order_m2_id,
                        "z_score": float(z_score_current),
                    },
                    related_trade_id=persisted_trade_id,
                )

            except Exception as exc:
                logger.exception(
                    "Exit failed for {} with {}",
                    position_market_m1,
                    position_market_m2,
                )
                if close_order_m1 is not None and close_order_m2 is None:
                    logger.critical(
                        "First close leg succeeded for {} / {}, second leg failed; retrying orphaned {} leg",
                        position_market_m1,
                        position_market_m2,
                        position_market_m2,
                    )
                    try:
                        close_order_m2, close_order_m2_id = (
                            await _place_reduce_only_close_with_retries(
                                client,
                                market=position_market_m2,
                                side=side_m2,
                                size=position_size_m2,
                                price=accept_price_m2,
                                attempts=3,
                            )
                        )
                        messenger.send_trade_closed_message(
                            {
                                "pair": f"{position_market_m1} / {position_market_m2}",
                                "base_market": position_market_m1,
                                "quote_market": position_market_m2,
                                "base_side": side_m1,
                                "quote_side": side_m2,
                                "base_size": position_size_m1,
                                "quote_size": position_size_m2,
                                "z_score": z_score_current,
                                "close_order_m1_id": close_order_m1_id,
                                "close_order_m2_id": close_order_m2_id,
                            },
                            "Z-score reversion after orphan retry",
                        )
                        persisted_trade_id = persist_live_trade_closed(
                            position,
                            exit_price1=accept_price_m1,
                            exit_price2=accept_price_m2,
                            exit_size1=position_size_m1,
                            exit_size2=position_size_m2,
                        )
                        persist_trade_activity_event(
                            "trade_exit_closed_after_orphan_retry",
                            f"Closed trade for {position_market_m1} / {position_market_m2} after orphan retry",
                            severity="warning",
                            details={
                                "market_1": position_market_m1,
                                "market_2": position_market_m2,
                                "close_order_m1_id": close_order_m1_id,
                                "close_order_m2_id": close_order_m2_id,
                                "z_score": float(z_score_current),
                            },
                            related_trade_id=persisted_trade_id,
                        )
                        continue
                    except Exception as retry_exc:
                        position["pair_status"] = "ORPHANED_EXIT_FAILED"
                        position["orphaned_market"] = position_market_m2
                        position["close_order_m1_id"] = close_order_m1_id
                        position["last_orphan_recovery_error"] = str(retry_exc)
                        position["last_orphan_recovery_at"] = _utc_now_iso()
                        messenger.send_error_message(
                            "CRITICAL: Partial Close Exposure",
                            f"Closed {position_market_m1} but failed to close {position_market_m2}: {retry_exc}",
                            is_critical=True,
                            category="execution_partial_close_failed",
                        )
                        persist_trade_activity_event(
                            "trade_exit_orphan_retry_failed",
                            (
                                "Partial close exposure: failed to close "
                                f"{position_market_m2} after closing {position_market_m1}"
                            ),
                            severity="critical",
                            details={
                                "market_1": position_market_m1,
                                "market_2": position_market_m2,
                                "close_order_m1_id": close_order_m1_id,
                                "error": str(retry_exc),
                            },
                        )
                        save_output.append(position)
                        continue

                position["last_exit_error"] = str(exc)
                position["last_exit_error_at"] = _utc_now_iso()
                persist_trade_activity_event(
                    "trade_exit_attempt_failed",
                    f"Exit failed for {position_market_m1} / {position_market_m2}: {exc}",
                    severity="error",
                    details={
                        "market_1": position_market_m1,
                        "market_2": position_market_m2,
                        "error": str(exc),
                    },
                )
                save_output.append(position)

        # Keep record if items and save
        else:
            save_output.append(position)

    # Save remaining items
    logger.info("{} items remaining; persisting {}", len(save_output), BOT_AGENTS_PATH)
    await save_processed_positions(open_positions_dict, save_output)
