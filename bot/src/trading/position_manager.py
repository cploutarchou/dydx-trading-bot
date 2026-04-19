"""Position entry and exit management for pairs trading."""

import asyncio
import contextlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from src.trading.bot_agent import BotAgent
from src.trading.market_data import get_candles_recent, get_markets

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


def _resolve_bot_agents_path() -> Path:
    """Resolve per-instance bot agents path from environment."""
    configured_path = os.getenv("BOT_AGENTS_FILE", "bot_agents.json")
    instance_id = os.getenv("BOT_INSTANCE_ID", "default")
    resolved = configured_path.replace("{instance_id}", instance_id)
    path = Path(resolved)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path


BOT_AGENTS_PATH = _resolve_bot_agents_path()
_BOT_AGENTS_ASYNC_LOCK = asyncio.Lock()
_BOT_AGENTS_THREAD_LOCK = threading.RLock()

IGNORE_ASSETS = [
    "BTC-USD_x",
    "BTC-USD_y",
]  # Ignore these assets which are not trading on testnet


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _position_identity(position: Dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(position.get("order_id_m1", "")),
        str(position.get("order_id_m2", "")),
        str(position.get("market_1", "")),
        str(position.get("market_2", "")),
    )


def _read_bot_agents_unlocked() -> List[Dict[str, Any]]:
    try:
        with BOT_AGENTS_PATH.open("r", encoding="utf-8") as open_positions_file:
            loaded = json.load(open_positions_file)
        return loaded if isinstance(loaded, list) else []
    except Exception:
        logger.debug("No existing {} found; starting fresh", BOT_AGENTS_PATH)
        return []


def _write_bot_agents_unlocked(positions: List[Dict[str, Any]]) -> None:
    BOT_AGENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = BOT_AGENTS_PATH.with_name(f".{BOT_AGENTS_PATH.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(positions, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, BOT_AGENTS_PATH)


@contextlib.contextmanager
def _bot_agents_file_lock():
    BOT_AGENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = BOT_AGENTS_PATH.with_name(f".{BOT_AGENTS_PATH.name}.lock")
    with lock_path.open("a", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


async def _load_tracked_positions() -> List[Dict[str, Any]]:
    async with _BOT_AGENTS_ASYNC_LOCK:
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                return _read_bot_agents_unlocked()


async def _append_tracked_position(position: Dict[str, Any]) -> None:
    async with _BOT_AGENTS_ASYNC_LOCK:
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                positions = _read_bot_agents_unlocked()
                position_ids = {_position_identity(item) for item in positions}
                if _position_identity(position) not in position_ids:
                    positions.append(position)
                _write_bot_agents_unlocked(positions)


async def _save_processed_positions(
        original_positions: List[Dict[str, Any]],
        remaining_positions: List[Dict[str, Any]],
) -> None:
    """Atomically save processed positions while preserving concurrent appends."""
    processed_ids = {_position_identity(item) for item in original_positions}
    async with _BOT_AGENTS_ASYNC_LOCK:
        with _BOT_AGENTS_THREAD_LOCK:
            with _bot_agents_file_lock():
                current_positions = _read_bot_agents_unlocked()
                concurrent_additions = [
                    item
                    for item in current_positions
                    if _position_identity(item) not in processed_ids
                ]
                _write_bot_agents_unlocked(remaining_positions + concurrent_additions)


def _opposite_order_side(side: str) -> str:
    normalized = str(side).upper()
    if normalized == "BUY":
        return "SELL"
    if normalized == "SELL":
        return "BUY"
    raise ValueError(f"Unsupported order side: {side}")


def _close_side_from_exchange_position(position: Dict[str, Any], fallback_side: str) -> str:
    exchange_side = str(position.get("side", "")).upper()
    if exchange_side == "LONG":
        return "SELL"
    if exchange_side == "SHORT":
        return "BUY"
    return _opposite_order_side(fallback_side)


def _close_size_from_exchange_position(position: Dict[str, Any], fallback_size: Any) -> Any:
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
        messenger.send_error_message(
            "Recovered Orphaned Position Leg",
            f"Submitted reduce-only close for orphaned {orphan_market} leg. Close order: {close_order_id}",
            is_critical=True,
            category="execution_orphan_recovery",
        )
        logger.critical(
            "Recovered orphaned {} leg for pair {} / {} with close order {}",
            orphan_market,
            tracked_position.get("market_1"),
            tracked_position.get("market_2"),
            close_order_id,
        )
        return True
    except Exception as exc:
        tracked_position["pair_status"] = "ORPHANED_EXIT_FAILED"
        tracked_position["orphaned_market"] = orphan_market
        tracked_position["last_orphan_recovery_error"] = str(exc)
        tracked_position["last_orphan_recovery_at"] = _utc_now_iso()
        messenger.send_error_message(
            "CRITICAL: Orphaned Position Leg",
            f"Failed to close orphaned {orphan_market} leg for {tracked_position.get('market_1')} / {tracked_position.get('market_2')}: {exc}",
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
        return False


async def open_positions(client):
    """
    Manage finding triggers for trade entry.

    Load cointegrated pairs and open positions when Z-score threshold is met.
    Store trades for managing later via exit function.
    """

    # Initialize Telegram messenger
    messenger = TelegramMessenger()

    # Load cointegrated pairs using enhanced storage
    pairs = pair_storage.load_pairs()
    logger.info("Loaded {} cointegrated pairs from enhanced storage", len(pairs))

    # Convert to DataFrame for backward compatibility with existing logic
    if pairs:
        df = pd.DataFrame([pair.to_dict() for pair in pairs])
    else:
        logger.warning("No cointegrated pairs found")
        return

    # Get markets from referencing of min order size, tick size etc
    markets = await get_markets(client)

    # Find ZScore triggers
    for index, row in df.iterrows():

        # Extract variables
        base_market = row["base_market"]
        quote_market = row["quote_market"]
        hedge_ratio = row["hedge_ratio"]
        half_life = row["half_life"]

        # Continue if ignore asset
        if base_market in IGNORE_ASSETS or quote_market in IGNORE_ASSETS:
            continue

        # Get prices
        try:
            series_1 = await get_candles_recent(client, base_market)
            series_2 = await get_candles_recent(client, quote_market)
        except Exception:
            logger.exception("Failed to fetch candles for {} / {}", base_market, quote_market)
            continue

        # Get ZScore
        if len(series_1) > 0 and len(series_1) == len(series_2):
            spread = series_1 - (hedge_ratio * series_2)
            z_score = calculate_zscore(spread).values.tolist()[-1]

            # Establish if potential trade
            if abs(z_score) >= ZSCORE_THRESH:

                # Ensure like-for-like not already open (diversify trading)
                is_base_open = await is_open_positions(client, base_market)
                is_quote_open = await is_open_positions(client, quote_market)

                # Place trade
                if not is_base_open and not is_quote_open:

                    # Determine side
                    base_side = "BUY" if z_score < 0 else "SELL"
                    quote_side = "BUY" if z_score > 0 else "SELL"

                    # Get acceptable price in string format with correct number of decimals
                    base_price = series_1[-1]
                    quote_price = series_2[-1]
                    accept_base_price = (
                        float(base_price) * 1.01 if z_score < 0 else float(base_price) * 0.99
                    )
                    accept_quote_price = (
                        float(quote_price) * 1.01 if z_score > 0 else float(quote_price) * 0.99
                    )
                    failsafe_base_price = (
                        float(base_price) * 0.05 if z_score < 0 else float(base_price) * 1.7
                    )
                    base_tick_size = markets["markets"][base_market]["tickSize"]
                    quote_tick_size = markets["markets"][quote_market]["tickSize"]

                    # Format prices
                    accept_base_price = format_number(accept_base_price, base_tick_size)
                    accept_quote_price = format_number(accept_quote_price, quote_tick_size)
                    accept_failsafe_base_price = format_number(failsafe_base_price, base_tick_size)

                    # Get size
                    base_quantity = 1 / base_price * USD_PER_TRADE
                    quote_quantity = 1 / quote_price * USD_PER_TRADE
                    base_step_size = markets["markets"][base_market]["stepSize"]
                    quote_step_size = markets["markets"][quote_market]["stepSize"]

                    # Format sizes
                    base_size = format_number(base_quantity, base_step_size)
                    quote_size = format_number(quote_quantity, quote_step_size)

                    # Ensure size (minimum order size greater than $1 according to V4 documentation)
                    base_min_order_size = 1 / float(markets["markets"][base_market]["oraclePrice"])
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
                            logger.warning(
                                "Insufficient collateral {:.2f} < {:.2f}; skipping trade",
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
                            logger.warning(
                                "Trade would breach collateral buffer: {:.2f} - {:.2f} < {:.2f}; stopping execution",
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
                        bot_open_dict = await bot_agent.open_trades()

                        # Guard: Handle failure
                        if bot_open_dict == "failed":
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
                            # Send trade opened notification before deleting bot_open_dict
                            trade_info = {
                                "pair": f"{base_market} / {quote_market}",
                                "base_market": base_market,
                                "quote_market": quote_market,
                                "base_side": bot_open_dict.get("base_side", "Unknown"),
                                "quote_side": bot_open_dict.get("quote_side", "Unknown"),
                                "base_size": bot_open_dict.get("base_size", 0),
                                "quote_size": bot_open_dict.get("quote_size", 0),
                                "z_score": bot_open_dict.get("z_score", 0),
                                "hedge_ratio": bot_open_dict.get("hedge_ratio", 0),
                                "half_life": bot_open_dict.get("half_life", 0),
                                "market_1_order_id": bot_open_dict.get("market_1_order_id", ""),
                                "market_2_order_id": bot_open_dict.get("market_2_order_id", ""),
                            }
                            messenger.send_trade_opened_message(trade_info)

                            # Save trade using atomic per-instance state update.
                            await _append_tracked_position(bot_open_dict)
                            del bot_open_dict

                            # Confirm live status in print
                            logger.info(
                                "Trade status: Live for {} / {}",
                                base_market,
                                quote_market,
                            )

    # Save agents
    logger.info("Manage open trades cycle complete")


async def manage_trade_exits(client):
    """
    Manage exiting open positions based on exit criteria.

    Checks Z-score levels and closes positions when reversion occurs.
    """

    # Initialize Telegram messenger
    messenger = TelegramMessenger()

    # Initialize saving output
    save_output = []

    open_positions_dict = await _load_tracked_positions()
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

        # Get markets for reference of tick size
        markets = await get_markets(client)
        z_score_traded: float = float(position["z_score"])
        z_score_current: float = z_score_traded

        # Protect API
        await asyncio.sleep(0.2)

        # Trigger close based on Z-Score
        if CLOSE_AT_ZSCORE_CROSS:

            # Initialize z_scores
            hedge_ratio = position["hedge_ratio"]
            if len(series_1) > 0 and len(series_1) == len(series_2):
                spread = series_1 - (hedge_ratio * series_2)
                z_score_current = calculate_zscore(spread).values.tolist()[-1]

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
            price_m1 = float(series_1[-1])
            price_m2 = float(series_2[-1])
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
            try:

                # Close position for market 1
                logger.info(
                    "Closing position for {} (subaccount inferred)",
                    position_market_m1,
                )

                (close_order_m1, close_order_m1_id) = await _place_reduce_only_close_with_retries(
                    client,
                    market=position_market_m1,
                    side=side_m1,
                    size=position_size_m1,
                    price=accept_price_m1,
                    attempts=3,
                )

                logger.debug("Close order m1 id: {}", close_order_m1.get("id"))

                # Protect API
                await asyncio.sleep(1)

                # Close position for market 2
                logger.info(
                    "Closing position for {} (subaccount inferred)",
                    position_market_m2,
                )

                (close_order_m2, close_order_m2_id) = await _place_reduce_only_close_with_retries(
                    client,
                    market=position_market_m2,
                    side=side_m2,
                    size=position_size_m2,
                    price=accept_price_m2,
                    attempts=3,
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
                        close_order_m2, close_order_m2_id = await _place_reduce_only_close_with_retries(
                            client,
                            market=position_market_m2,
                            side=side_m2,
                            size=position_size_m2,
                            price=accept_price_m2,
                            attempts=3,
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
                        save_output.append(position)
                        continue

                position["last_exit_error"] = str(exc)
                position["last_exit_error_at"] = _utc_now_iso()
                save_output.append(position)

        # Keep record if items and save
        else:
            save_output.append(position)

    # Save remaining items
    logger.info("{} items remaining; persisting {}", len(save_output), BOT_AGENTS_PATH)
    await _save_processed_positions(open_positions_dict, save_output)
