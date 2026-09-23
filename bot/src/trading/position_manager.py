"""Position entry and exit management for pairs trading."""

import asyncio
import math
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
import pandas as pd
from loguru import logger

from src.constants import (
    CLOSE_AT_ZSCORE_CROSS,
    DYDX_API_THROTTLE_SECONDS,
    MAX_DRAWDOWN_PCT,
    MAX_POSITIONS,
    POSITION_TIMEOUT_HOURS,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    TRAILING_STOP_PCT,
    USD_MIN_COLLATERAL,
    USD_PER_TRADE,
    ZSCORE_THRESH,
)
from src.exceptions import BotError, UnhedgedExposureError
from src.infrastructure.domain.cointegration_storage import pair_storage
from src.shared.dataframe_utils import (
    cleanup_dataframe,
    register_dataframe,
    unregister_dataframe,
)
from src.shared.notifications import TelegramMessenger
from src.shared.utils import format_number, format_size_down
from src.trading import drawdown_guard, entry_halt, indexer_freshness
from src.trading.account_manager import (
    get_account,
    get_open_positions,
    get_order,
    get_order_fills,
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
from src.trading.pair_priority import PairPriorityScore, prioritize_pairs
from src.trading.portfolio_risk import check_portfolio_entry_guard
from src.trading.realized_pnl import (
    RealizedPnl,
    RealizedPnlInputError,
    compute_pair_realized_pnl,
    sum_fill_fees,
)
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


def _record_entry_failure(pair_key: str, error: Any) -> None:
    current = _ENTRY_FAILURE_STATE.get(pair_key, {})
    failure_count = int(current.get("failure_count", 0) or 0) + 1
    cooldown = _entry_backoff_seconds(failure_count)
    _ENTRY_FAILURE_STATE[pair_key] = {
        "failure_count": failure_count,
        "next_retry_at": _entry_backoff_now() + cooldown,
        "last_error": str(error),
        "last_failure_at": _utc_now_iso(),
    }


def _record_entry_success(pair_key: str) -> None:
    if pair_key in _ENTRY_FAILURE_STATE:
        _ENTRY_FAILURE_STATE.pop(pair_key, None)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _position_leg_pnl(
    side: str, entry_price: float, current_price: float, size: float
) -> float:
    normalized_side = str(side).upper()
    if normalized_side == "BUY":
        return (current_price - entry_price) * size
    if normalized_side == "SELL":
        return (entry_price - current_price) * size
    raise ValueError(f"Unsupported order side: {side}")


def _pair_unrealized_pnl_pct(
    position: Dict[str, Any],
    *,
    current_price1: float,
    current_price2: float,
) -> float:
    entry_price1 = _as_float(position["order_m1_price"], field_name="order_m1_price")
    entry_price2 = _as_float(position["order_m2_price"], field_name="order_m2_price")
    size1 = abs(_as_float(position["order_m1_size"], field_name="order_m1_size"))
    size2 = abs(_as_float(position["order_m2_size"], field_name="order_m2_size"))
    pnl = _position_leg_pnl(
        str(position["order_m1_side"]),
        entry_price1,
        current_price1,
        size1,
    ) + _position_leg_pnl(
        str(position["order_m2_side"]),
        entry_price2,
        current_price2,
        size2,
    )
    entry_notional = (entry_price1 * size1) + (entry_price2 * size2)
    if entry_notional <= 0:
        raise ValueError("Tracked position entry notional must be positive")
    return (pnl / entry_notional) * 100.0


def _position_open_age_hours(position: Dict[str, Any]) -> float:
    opened_at_candidates: list[datetime] = []
    for key in ("order_time_m1", "order_time_m2"):
        raw = str(position.get(key) or "").strip()
        if not raw:
            continue
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        opened_at_candidates.append(parsed.astimezone(timezone.utc))
    if not opened_at_candidates:
        return 0.0
    opened_at = min(opened_at_candidates)
    return max(0.0, (datetime.now(timezone.utc) - opened_at).total_seconds() / 3600.0)


PEAK_PNL_KEY = "peak_unrealized_pnl_pct"
PEAK_PNL_AT_KEY = "peak_unrealized_pnl_at"


def _trailing_stop_triggered(
    unrealized_pnl_pct: float, peak_unrealized_pnl_pct: Optional[float]
) -> bool:
    """Armed once the pair's best unrealized P&L has reached the trail distance;
    fires when P&L has fallen that distance below its best level.

    The stop level (best - distance) is then never below break-even, so the
    stop loss keeps owning the downside and is never tightened by the trail.
    """
    if TRAILING_STOP_PCT <= 0 or peak_unrealized_pnl_pct is None:
        return False
    if peak_unrealized_pnl_pct < TRAILING_STOP_PCT:
        return False
    return unrealized_pnl_pct <= peak_unrealized_pnl_pct - TRAILING_STOP_PCT


def _fold_peak_unrealized_pnl(
    position: Dict[str, Any], unrealized_pnl_pct: float
) -> float:
    """Ratchet the pair's best unrealized P&L %, kept on the tracked position so
    it survives restarts. A position tracked before the trailing stop existed,
    or with an unusable stored value, starts from the current observation."""
    previous: Optional[float] = None
    stored = position.get(PEAK_PNL_KEY)
    if stored is not None:
        try:
            previous = float(stored)
        except (TypeError, ValueError):
            previous = None
        if previous is not None and not math.isfinite(previous):
            previous = None
        if previous is None:
            logger.warning(
                "Ignoring unusable stored peak P&L {!r} for {} / {}",
                stored,
                position.get("market_1", "?"),
                position.get("market_2", "?"),
            )
    if previous is None or unrealized_pnl_pct > previous:
        position[PEAK_PNL_KEY] = unrealized_pnl_pct
        position[PEAK_PNL_AT_KEY] = _utc_now_iso()
        return unrealized_pnl_pct
    return previous


def _resolve_exit_reason(
    *,
    z_score_current: float,
    z_score_traded: float,
    unrealized_pnl_pct: float,
    position_age_hours: float,
    peak_unrealized_pnl_pct: Optional[float] = None,
) -> Optional[str]:
    if STOP_LOSS_PCT > 0 and unrealized_pnl_pct <= (-1.0 * STOP_LOSS_PCT):
        return "stop_loss"
    if TAKE_PROFIT_PCT > 0 and unrealized_pnl_pct >= TAKE_PROFIT_PCT:
        return "take_profit"
    if _trailing_stop_triggered(unrealized_pnl_pct, peak_unrealized_pnl_pct):
        return "trailing_stop"
    if POSITION_TIMEOUT_HOURS > 0 and position_age_hours >= POSITION_TIMEOUT_HOURS:
        return "timeout"
    if CLOSE_AT_ZSCORE_CROSS:
        z_score_level_check = abs(z_score_current) >= abs(z_score_traded)
        z_score_cross_check = (z_score_current < 0 < z_score_traded) or (
            z_score_current > 0 > z_score_traded
        )
        if z_score_level_check and z_score_cross_check:
            return "zscore_reversion"
    return None


def _exit_reason_label(reason: str) -> str:
    labels = {
        "stop_loss": "Stop-loss",
        "take_profit": "Take-profit",
        "trailing_stop": "Trailing stop",
        "timeout": "Position timeout",
        "zscore_reversion": "Z-score reversion",
    }
    return labels.get(str(reason or "").strip(), "Exit signal")


def _exit_confirm_max_attempts() -> int:
    raw = os.getenv("BOT_EXIT_CONFIRM_MAX_ATTEMPTS", "6")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 6


def _exit_buffer_pct() -> float:
    """Accept-price band for discretionary exits (default 5%)."""
    try:
        return max(0.1, float(os.getenv("EXIT_ACCEPT_PRICE_BUFFER_PCT", "5.0")))
    except (TypeError, ValueError):
        return 5.0


def _stop_exit_buffer_pct() -> float:
    """Accept-price band for stop-loss exits (default 15%, wider: stops are
    time-critical and must not sit unfilled)."""
    try:
        return max(0.1, float(os.getenv("EXIT_STOP_ACCEPT_PRICE_BUFFER_PCT", "15.0")))
    except (TypeError, ValueError):
        return 15.0


def _exit_confirm_delay_seconds() -> float:
    raw = os.getenv("BOT_EXIT_CONFIRM_DELAY_SECONDS", "2.0")
    try:
        return max(0.1, float(raw))
    except (TypeError, ValueError):
        return 2.0


def _remaining_leg_size(
    exchange_position: Optional[Dict[str, Any]], fallback_size: Any
) -> float:
    if not exchange_position:
        return 0.0
    raw = (
        exchange_position.get("sumOpen")
        or exchange_position.get("size")
        or fallback_size
    )
    try:
        return abs(float(raw))
    except (TypeError, ValueError):
        return 0.0


def _classify_exit_confirmation_state(
    position: Dict[str, Any],
    exchange_positions: Dict[str, Any],
    pre_close_sizes: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    market_1 = str(position.get("market_1") or "")
    market_2 = str(position.get("market_2") or "")
    exchange_m1 = exchange_positions.get(market_1)
    exchange_m2 = exchange_positions.get(market_2)

    open_m1 = exchange_m1 is not None
    open_m2 = exchange_m2 is not None
    if not open_m1 and not open_m2:
        return {"pair_status": "CLOSE_CONFIRMED", "flat_confirmed": True}

    original_size_m1 = abs(float(position.get("order_m1_size") or 0.0))
    original_size_m2 = abs(float(position.get("order_m2_size") or 0.0))
    remaining_size_m1 = _remaining_leg_size(exchange_m1, position.get("order_m1_size"))
    remaining_size_m2 = _remaining_leg_size(exchange_m2, position.get("order_m2_size"))

    # Shared-subaccount support: when another instance holds the same market,
    # the account aggregate never drops to zero after OUR close — flat for us
    # means "the aggregate decreased by at least our tracked size". Without a
    # pre-close snapshot (legacy callers) only full absence confirms.
    def _leg_closed_by_us(market_open: bool, market: str, our_size: float) -> bool:
        if not market_open:
            return True
        if not pre_close_sizes or market not in pre_close_sizes:
            return False
        if our_size <= 0.0:
            return False
        current_agg = _remaining_leg_size(exchange_positions.get(market), None)
        closed_amount = pre_close_sizes[market] - current_agg
        return closed_amount + 1e-9 >= our_size - 1e-9

    if _leg_closed_by_us(open_m1, market_1, original_size_m1) and _leg_closed_by_us(
        open_m2, market_2, original_size_m2
    ):
        return {
            "pair_status": "CLOSE_CONFIRMED",
            "flat_confirmed": True,
            "shared_subaccount_confirmed": True,
        }

    size_tolerance = 1e-12
    partial_m1 = open_m1 and remaining_size_m1 + size_tolerance < original_size_m1
    partial_m2 = open_m2 and remaining_size_m2 + size_tolerance < original_size_m2

    state: Dict[str, Any] = {
        "flat_confirmed": False,
        "remaining_size_m1": remaining_size_m1,
        "remaining_size_m2": remaining_size_m2,
    }
    if open_m1 != open_m2:
        state["pair_status"] = "ORPHANED_EXIT_FAILED"
        state["orphaned_market"] = market_1 if open_m1 else market_2
        return state
    if partial_m1 or partial_m2:
        state["pair_status"] = "PARTIALLY_CLOSED"
        return state
    state["pair_status"] = "CLOSING"
    return state


async def _confirm_exchange_flat_after_close(
    client: Any,
    *,
    position: Dict[str, Any],
    close_order_ids: Dict[str, str],
    pre_close_sizes: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    last_state: Dict[str, Any] = {
        "pair_status": "CLOSE_SUBMITTED",
        "flat_confirmed": False,
    }
    for attempt in range(1, _exit_confirm_max_attempts() + 1):
        await asyncio.sleep(_exit_confirm_delay_seconds())
        exchange_positions = await get_open_positions(client)
        last_state = _classify_exit_confirmation_state(
            position, exchange_positions, pre_close_sizes=pre_close_sizes
        )
        last_state["attempt"] = attempt
        last_state["close_order_ids"] = dict(close_order_ids)
        if bool(last_state.get("flat_confirmed")):
            return last_state

    fills_summary: Dict[str, int] = {}
    for market_key, order_id in close_order_ids.items():
        if not order_id:
            continue
        market = str(position.get(market_key) or "")
        try:
            fills_summary[market_key] = len(
                await get_order_fills(client, order_id, market=market)
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch exit fills for {} ({}): {}", market_key, order_id, exc
            )
    last_state["fill_counts"] = fills_summary
    last_state["timed_out"] = True
    return last_state


# ---------------------------------------------------------------------------
# Untracked-exposure reconciliation sweep
# ---------------------------------------------------------------------------

_UNTRACKED_ALERT_COOLDOWN_SECONDS = 3600.0
_untracked_alert_last_sent: Dict[str, float] = {}


def _untracked_exposure_alerts_enabled() -> bool:
    raw = os.getenv("UNTRACKED_EXPOSURE_ALERTS_ENABLED", "true")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


async def detect_untracked_exchange_exposure(
    exchange_positions: Dict[str, Any],
    tracked_positions: List[Dict[str, Any]],
    messenger: TelegramMessenger,
) -> List[str]:
    """Alert on exchange positions no tracked pair accounts for.

    This is the reconciliation backstop for unknown-outcome entries: if an
    order landed despite a "failed" entry (or a partial fill escaped cleanup),
    the position shows up here as exposure with no owner. Detection only —
    closing is deliberately left to the operator, because on a shared
    subaccount "untracked by this instance" may mean "owned by another
    instance" (set UNTRACKED_EXPOSURE_ALERTS_ENABLED=false for such
    deployments).
    """
    tracked_markets = set()
    for position in tracked_positions:
        if not isinstance(position, dict):
            continue
        for key in ("market_1", "market_2"):
            market = str(position.get(key) or "").strip()
            if market:
                tracked_markets.add(market)

    untracked = []
    now = time.monotonic()
    for market, pos in (exchange_positions or {}).items():
        if market in tracked_markets:
            continue
        untracked.append(market)
        increment_metric("untracked_exposure_detected_total")
        if not _untracked_exposure_alerts_enabled():
            continue
        last = _untracked_alert_last_sent.get(market)
        if last is not None and now - last < _UNTRACKED_ALERT_COOLDOWN_SECONDS:
            continue
        _untracked_alert_last_sent[market] = now
        increment_metric("untracked_exposure_alerted_total")
        side = str((pos or {}).get("side") or "?")
        size = str((pos or {}).get("sumOpen") or "?")
        detail = (
            f"Exchange reports a {side} position of {size} on {market} that no "
            "tracked pair accounts for. Possible escaped fill or foreign "
            "instance on a shared subaccount. Manual verification required."
        )
        logger.critical("Untracked exchange exposure: {}", detail)
        messenger.send_error_message(
            "CRITICAL: Untracked Exchange Exposure",
            detail,
            is_critical=True,
            category="reconciliation_untracked_exposure",
        )
        persist_trade_activity_event(
            "reconciliation_untracked_exposure",
            detail,
            severity="critical",
            details={"market": market, "side": side, "size": size},
        )
    return untracked


# What an indexer fills lookup raises when it cannot answer: transport errors,
# the circuit breaker and other bot-domain errors, and malformed payloads.
_FILL_LOOKUP_ERRORS = (httpx.HTTPError, OSError, BotError, RuntimeError, ValueError)


async def _order_fee_from_fills(
    client: Any, order_id: Any, market: str
) -> Optional[Decimal]:
    """Fee paid on one order, or ``None`` when it cannot be read."""
    if not order_id:
        return None
    try:
        fills = await get_order_fills(client, str(order_id), market=market)
    except _FILL_LOOKUP_ERRORS as exc:
        logger.warning(
            "Could not fetch fills for fee of order {} on {}: {}", order_id, market, exc
        )
        return None
    return sum_fill_fees(fills)


async def _realized_pnl_for_closed_pair(
    client: Any,
    position: Dict[str, Any],
    *,
    exit_price_m1: Any,
    exit_price_m2: Any,
    exit_size_m1: Any,
    exit_size_m2: Any,
    close_order_m1_id: Any,
    close_order_m2_id: Any,
) -> Optional[RealizedPnl]:
    """Net realised P&L of a pair that was just closed.

    Returns ``None`` (and logs) when the entry data is unusable; a missing
    number must never be stored as a zero P&L.
    """
    market_1 = str(position.get("market_1", ""))
    market_2 = str(position.get("market_2", ""))
    fees = [
        await _order_fee_from_fills(client, position.get("order_id_m1"), market_1),
        await _order_fee_from_fills(client, position.get("order_id_m2"), market_2),
        await _order_fee_from_fills(client, close_order_m1_id, market_1),
        await _order_fee_from_fills(client, close_order_m2_id, market_2),
    ]
    try:
        realized = compute_pair_realized_pnl(
            side1=position.get("order_m1_side"),
            entry_price1=position.get("order_m1_price"),
            exit_price1=exit_price_m1,
            size1=exit_size_m1,
            side2=position.get("order_m2_side"),
            entry_price2=position.get("order_m2_price"),
            exit_price2=exit_price_m2,
            size2=exit_size_m2,
            fees=fees,
        )
    except RealizedPnlInputError as exc:
        logger.error(
            "Realised P&L not recorded for {} / {}: {}", market_1, market_2, exc
        )
        return None
    position["realized_pnl"] = str(realized.net)
    position["realized_pnl_gross"] = str(realized.gross)
    position["realized_pnl_fees"] = str(realized.fees)
    position["realized_pnl_fees_complete"] = realized.fees_complete
    if not realized.fees_complete:
        logger.warning(
            "Realised P&L for {} / {} is net of known fees only ({} of 4 orders)",
            market_1,
            market_2,
            sum(1 for fee in fees if fee is not None),
        )
    return realized


async def _exit_price_from_fills(
    client: Any, order_id: str, market: str, fallback: str
) -> tuple[str, str]:
    """Resolve the execution price for a close order from its fills.

    Returns (price, source). The recorded exit price must be what the close
    actually filled at (VWAP across fills); the accept-band price (±5% off
    market when the order was submitted) systematically misstates realized
    P&L by up to 5% of notional per leg, so it is only a fallback when the
    fills endpoint is unavailable.
    """
    try:
        fills = await get_order_fills(client, order_id, market=market)
    except Exception as exc:
        logger.warning(
            "Could not fetch fills for close order {} on {}: {}",
            order_id,
            market,
            exc,
        )
        return fallback, "accept_band_fallback"

    total_size = 0.0
    total_notional = 0.0
    for fill in fills:
        if not isinstance(fill, dict):
            continue
        price = fill.get("price")
        size = fill.get("size")
        if price in (None, "") or size in (None, ""):
            continue
        try:
            fill_size = abs(float(size))
            total_size += fill_size
            total_notional += float(price) * fill_size
        except (TypeError, ValueError):
            continue
    if total_size <= 0:
        return fallback, "accept_band_fallback"
    return str(total_notional / total_size), "fills_vwap"


async def _get_recent_candles_for_cycle(
    client: Any,
    market: str,
    cycle_cache: Optional[Dict[str, Any]],
) -> Any:
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
    client: Any,
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
    # Prefer THIS instance's tracked side: on a shared subaccount the
    # aggregate net side can be dominated by another instance's opposite
    # position, and closing "the aggregate direction" would INCREASE our
    # exposure (audit F6). Exchange side is only a fallback when tracked
    # side metadata is missing/unparseable.
    try:
        return _opposite_order_side(fallback_side)
    except ValueError:
        pass
    exchange_side = str(position.get("side", "")).upper()
    if exchange_side == "LONG":
        return "SELL"
    if exchange_side == "SHORT":
        return "BUY"
    raise ValueError(
        f"Cannot determine close side: tracked side={fallback_side!r}, "
        f"exchange side={exchange_side!r}"
    )


def _close_size_from_exchange_position(
    position: Dict[str, Any], fallback_size: Any
) -> Any:
    # Prefer THIS instance's tracked size over the account aggregate
    # (sumOpen): on a shared subaccount the aggregate includes other
    # instances' positions, and a reduce-only close for the aggregate size
    # would flatten THEIR exposure too (audit F6). Aggregate is only a
    # fallback for legacy rows without tracked sizes.
    tracked = fallback_size
    if tracked not in (None, "", 0, "0", 0.0):
        return tracked
    return position.get("sumOpen") or position.get("size")


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
    # format_number is untyped (shared util over Any market metadata); bind
    # through a typed local so the Any does not leak out of the -> str contract.
    formatted: str = format_number(accept_price, tick_size)
    return formatted


async def _place_reduce_only_close_with_retries(
    client: Any,
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
            result: tuple[Dict[str, Any], str] = await place_market_order(
                client,
                market=market,
                side=side,
                size=size,
                price=price,
                reduce_only=True,
            )
            return result
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
    client: Any,
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


# Set by the runtime when a shutdown was requested. The entry scan checks it
# before every pair so a stopping instance finishes the entry in flight but
# opens nothing new (a scan can otherwise outlive the deployment's grace period
# and be killed between two legs).
_ENTRY_STOP_REQUESTED = False


def request_entry_stop() -> None:
    global _ENTRY_STOP_REQUESTED
    _ENTRY_STOP_REQUESTED = True


def reset_entry_stop() -> None:
    """For a fresh runtime in the same process (tests, supervised restarts)."""
    global _ENTRY_STOP_REQUESTED
    _ENTRY_STOP_REQUESTED = False


async def open_positions(client: Any) -> None:
    """
    Manage finding triggers for trade entry.

    Load cointegrated pairs and open positions when Z-score threshold is met.
    Store trades for managing later via exit function.
    """

    scan_cycle_id = uuid4().hex[:12]
    increment_metric("arbitrage_scan_cycles_total")

    # The subaccount's entry halt: set after a failed emergency close (a leg
    # may be open with no hedge) or when the drawdown limit was reached. No new
    # pair is opened until an operator has checked the account and cleared it
    # (strategy card, or python -m src.trading.entry_halt --clear). Exits keep
    # running.
    halt_state = entry_halt.entries_halted()
    if halt_state is not None:
        increment_metric("arbitrage_entries_halted_cycles_total")
        if halt_state.get("unverified"):
            # The latch could not be read, so whether this subaccount was halted
            # before a restart is unknown. Open nothing; the next cycle asks again.
            logger.warning(
                "Entries skipped this cycle: {}", halt_state.get("reason", "unknown")
            )
            return
        logger.critical(
            "Entries are halted since {}: {}. Verify the account, then clear the latch.",
            halt_state.get("halted_at", "unknown"),
            halt_state.get("reason", "unknown"),
        )
        return

    # Initialize Telegram messenger
    messenger = TelegramMessenger()

    # Prices, positions and order status all come from the indexer. While it is
    # behind the chain an entry would be priced on old data and could not be
    # confirmed afterwards, so this cycle opens nothing. Not a latch: entries
    # resume by themselves once the indexer has caught up. Exits keep running.
    staleness = await indexer_freshness.check_indexer_freshness(client)
    if staleness is not None:
        increment_metric("arbitrage_entries_blocked_stale_indexer_cycles_total")
        logger.warning("Entries skipped this cycle: {}", staleness.describe())
        if indexer_freshness.should_alert():
            messenger.send_error_message(
                "Entries paused: dYdX indexer is stale",
                f"{staleness.describe()}. No new pairs are opened until it catches "
                "up; open positions are still managed.",
                is_critical=False,
                category="execution_indexer_stale",
            )
        return

    # Bot-level max drawdown on the subaccount's equity. Reaching it latches
    # the entry halt above; an unreadable equity or peak skips this cycle.
    # Runs before any pair is looked at so the peak follows equity every cycle.
    if not await drawdown_guard.check_entry_drawdown(
        client,
        limit_pct=MAX_DRAWDOWN_PCT,
        messenger=messenger,
        scan_cycle_id=scan_cycle_id,
        read_account=get_account,
    ):
        return

    # Load cointegrated pairs using enhanced storage
    pairs = pair_storage.load_pairs()
    logger.info("Loaded {} cointegrated pairs from enhanced storage", len(pairs))

    if not pairs:
        logger.warning("No cointegrated pairs found")
        return

    # Get markets from referencing of min order size, tick size etc
    markets = await get_markets(client)
    market_map = markets.get("markets", {}) if isinstance(markets, dict) else {}

    priority_scores: list[PairPriorityScore] = []
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
    df_id = register_dataframe(
        df, "position_scan", {"scan_cycle_id": scan_cycle_id, "pairs_count": len(pairs)}
    )

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
        if _ENTRY_STOP_REQUESTED:
            logger.info(
                "scan_cycle={} stopping the entry scan: shutdown requested",
                scan_cycle_id,
            )
            break

        # Extract variables
        base_market = row["base_market"]
        quote_market = row["quote_market"]
        pair_key = _entry_pair_key(base_market, quote_market)
        try:
            hedge_ratio = _as_float(row["hedge_ratio"], field_name="hedge_ratio")
            half_life = _as_float(row["half_life"], field_name="half_life")
            # Pairs stored before the intercept field existed fall back to 0.0,
            # which reproduces the legacy (intercept-free) spread.
            intercept = _as_float(
                row.get("intercept", 0.0) if hasattr(row, "get") else 0.0,
                field_name="intercept",
            )
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

            # Spread must match the fitted relationship used for pair
            # selection: series_1 - hedge_ratio*series_2 - intercept.
            spread = series_1_numeric - (hedge_ratio * series_2_numeric) - intercept
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
                    tracked_positions = await load_tracked_positions()
                    if MAX_POSITIONS > 0 and len(tracked_positions) >= MAX_POSITIONS:
                        record_rejection("max_positions")
                        logger.warning(
                            "scan_cycle={} opportunity_rejected pair={}/{} "
                            "reason=max_positions tracked_positions={} max_positions={}",
                            scan_cycle_id,
                            base_market,
                            quote_market,
                            len(tracked_positions),
                            MAX_POSITIONS,
                        )
                        persist_trade_activity_event(
                            "trade_entry_rejected_max_positions",
                            (
                                f"Rejected entry for {base_market} / {quote_market}: "
                                f"tracked positions {len(tracked_positions)} reached max {MAX_POSITIONS}"
                            ),
                            severity="warning",
                            details={
                                "market_1": base_market,
                                "market_2": quote_market,
                                "tracked_positions": len(tracked_positions),
                                "max_positions": MAX_POSITIONS,
                            },
                        )
                        break

                    # Account-level (portfolio) guard: the shared subaccount
                    # already reflects every instance's fills, so this is the
                    # authoritative aggregate view (no cross-process state).
                    # On by default since Phase B (disable via
                    # BOT_PORTFOLIO_RISK_ENABLED=false). Each pair leg books
                    # USD_PER_TRADE notional in its market.
                    portfolio_decision = await check_portfolio_entry_guard(
                        client,
                        incremental_notional_usd=USD_PER_TRADE * 2,
                        entry_markets=(base_market, quote_market),
                        per_leg_notional_usd=USD_PER_TRADE,
                    )
                    if not portfolio_decision.allowed:
                        record_rejection(portfolio_decision.primary_reason)
                        logger.warning(
                            "scan_cycle={} opportunity_rejected pair={}/{} "
                            "reason=portfolio_risk reasons={} equity={} "
                            "free_collateral={} open_markets={}",
                            scan_cycle_id,
                            base_market,
                            quote_market,
                            list(portfolio_decision.reasons),
                            (
                                portfolio_decision.snapshot.equity
                                if portfolio_decision.snapshot
                                else None
                            ),
                            (
                                portfolio_decision.snapshot.free_collateral
                                if portfolio_decision.snapshot
                                else None
                            ),
                            (
                                portfolio_decision.snapshot.open_market_count
                                if portfolio_decision.snapshot
                                else None
                            ),
                        )
                        persist_trade_activity_event(
                            "trade_entry_rejected_portfolio_risk",
                            (
                                f"Rejected entry for {base_market} / {quote_market}: "
                                f"portfolio risk limits exceeded "
                                f"({', '.join(portfolio_decision.reasons)})"
                            ),
                            severity="warning",
                            details={
                                "market_1": base_market,
                                "market_2": quote_market,
                                "reasons": list(portfolio_decision.reasons),
                                "equity": (
                                    portfolio_decision.snapshot.equity
                                    if portfolio_decision.snapshot
                                    else None
                                ),
                                "free_collateral": (
                                    portfolio_decision.snapshot.free_collateral
                                    if portfolio_decision.snapshot
                                    else None
                                ),
                                "open_markets": (
                                    portfolio_decision.snapshot.open_market_count
                                    if portfolio_decision.snapshot
                                    else None
                                ),
                                "max_open_markets": (
                                    portfolio_decision.limits.max_open_markets
                                ),
                                "aggregate": (
                                    {
                                        "total_equity": (
                                            portfolio_decision.aggregate_totals.total_equity
                                        ),
                                        "total_free_collateral": (
                                            portfolio_decision.aggregate_totals.total_free_collateral
                                        ),
                                        "total_open_markets": (
                                            portfolio_decision.aggregate_totals.total_open_markets
                                        ),
                                        "accounts": (
                                            portfolio_decision.aggregate_totals.accounts
                                        ),
                                        "incomplete_accounts": (
                                            portfolio_decision.aggregate_totals.incomplete_accounts
                                        ),
                                    }
                                    if portfolio_decision.aggregate_totals
                                    else None
                                ),
                            },
                        )
                        break

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
                    # Leg 2 is closed on the opposite side to leg 1, so its
                    # fail-safe bound mirrors the base one on market 2's scale.
                    failsafe_quote_price = (
                        quote_price * 1.7
                        if quote_side == "SELL"
                        else quote_price * 0.05
                    )
                    base_tick_size = markets["markets"][base_market]["tickSize"]
                    quote_tick_size = markets["markets"][quote_market]["tickSize"]

                    # Format prices
                    accept_base_price_formatted = format_number(
                        accept_base_price, base_tick_size
                    )
                    accept_quote_price_formatted = format_number(
                        accept_quote_price, quote_tick_size
                    )
                    accept_failsafe_base_price_formatted = format_number(
                        failsafe_base_price, base_tick_size
                    )
                    accept_failsafe_quote_price_formatted = format_number(
                        failsafe_quote_price, quote_tick_size
                    )

                    # Get size
                    base_quantity = 1 / base_price * USD_PER_TRADE
                    quote_quantity = 1 / quote_price * USD_PER_TRADE
                    base_step_size = markets["markets"][base_market]["stepSize"]
                    quote_step_size = markets["markets"][quote_market]["stepSize"]

                    # Format sizes — floored to the step: sizes must never
                    # round UP past the intended notional.
                    base_size = format_size_down(base_quantity, base_step_size)
                    quote_size = format_size_down(quote_quantity, quote_step_size)

                    # Ensure size (minimum order size greater than $1 according to V4 documentation)
                    base_min_order_size = 1 / float(
                        markets["markets"][base_market]["oraclePrice"]
                    )
                    quote_min_order_size = 1 / float(
                        markets["markets"][quote_market]["oraclePrice"]
                    )

                    # Combine checks — against the FORMATTED size, not the raw
                    # quantity: a size that floors below the $1 minimum would
                    # only fail at the exchange.
                    check_base = float(base_size) > base_min_order_size
                    check_quote = float(quote_size) > quote_min_order_size

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
                            base_price=accept_base_price_formatted,
                            quote_side=quote_side,
                            quote_size=quote_size,
                            quote_price=accept_quote_price_formatted,
                            accept_failsafe_base_price=accept_failsafe_base_price_formatted,
                            accept_failsafe_quote_price=accept_failsafe_quote_price_formatted,
                            z_score=z_score,
                            half_life=half_life,
                            hedge_ratio=hedge_ratio,
                            intercept=intercept,
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
                        except UnhedgedExposureError as exc:
                            # The pair could not be flattened. Stop opening
                            # pairs now, in this cycle and the following ones.
                            record_rejection("entry_unhedged_exposure")
                            _record_entry_failure(pair_key, exc)
                            # The alert below must go out whatever happens to
                            # the latch: if neither store takes the halt, the
                            # operator is the only thing stopping more entries.
                            halt_error: Optional[str] = None
                            try:
                                entry_halt.halt_entries(
                                    f"emergency close failed for {base_market} / {quote_market}",
                                    {
                                        "kind": entry_halt.KIND_UNHEDGED_EXPOSURE,
                                        "market_1": base_market,
                                        "market_2": quote_market,
                                        "error": str(exc),
                                        "scan_cycle_id": scan_cycle_id,
                                    },
                                )
                            except RuntimeError as halt_exc:
                                halt_error = str(halt_exc)
                                logger.critical(
                                    "Entry halt could not be persisted after {} / {}: {}",
                                    base_market,
                                    quote_market,
                                    halt_exc,
                                )
                            persist_trade_activity_event(
                                "trade_entries_halted",
                                f"New entries halted: emergency close failed for {base_market} / {quote_market}",
                                severity="critical",
                                details={
                                    "market_1": base_market,
                                    "market_2": quote_market,
                                    "error": str(exc),
                                    "halt_persisted": halt_error is None,
                                    **(
                                        {"halt_error": halt_error} if halt_error else {}
                                    ),
                                },
                            )
                            latch_text = (
                                "No new pairs will be opened until the account is "
                                "verified and the latch is cleared."
                                if halt_error is None
                                else f"Stop this bot until the account is verified: "
                                f"{halt_error}."
                            )
                            messenger.send_error_message(
                                "CRITICAL: New entries halted",
                                f"Emergency close failed for {base_market} / {quote_market}. "
                                f"A leg may be open without a hedge. {latch_text}",
                                is_critical=True,
                                category="execution_emergency_cleanup",
                            )
                            logger.critical(
                                "Unhedged exposure after {} / {}; entries halted",
                                base_market,
                                quote_market,
                            )
                            # break, not return: the scan's cleanup below
                            # (DataFrame tracking) must still run.
                            break
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
                        # Defensive legacy-shape check; bind through Any so the
                        # typed dict contract does not narrow it away.
                        legacy_open_result: Any = bot_open_dict
                        if legacy_open_result == "failed":
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
                                    "order_m1_side": bot_open_dict.get("order_m1_side"),
                                    "order_m2_side": bot_open_dict.get("order_m2_side"),
                                    "order_m1_size": bot_open_dict.get("order_m1_size"),
                                    "order_m2_size": bot_open_dict.get("order_m2_size"),
                                    "order_m1_price": bot_open_dict.get(
                                        "order_m1_price"
                                    ),
                                    "order_m2_price": bot_open_dict.get(
                                        "order_m2_price"
                                    ),
                                    "order_time_m1": bot_open_dict.get("order_time_m1"),
                                    "order_time_m2": bot_open_dict.get("order_time_m2"),
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

    # Cleanup DataFrame tracking after all processing is complete
    if df_id:
        unregister_dataframe(df_id)
    cleanup_dataframe(df)

    logger.info("arbitrage_scan_cycle_complete cycle_id={}", scan_cycle_id)


async def manage_trade_exits(client: Any) -> str | None:
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

    # Reconciliation sweep BEFORE the empty-state early return: exposure
    # with an empty tracked state is exactly the escaped-fill scenario this
    # exists to catch, and the early return below would otherwise skip it.
    exchange_pos = await get_open_positions(client)
    logger.debug("Exchange reports {} open positions", len(exchange_pos))
    await detect_untracked_exchange_exposure(
        exchange_pos, open_positions_dict, messenger
    )

    # Guard: Exit if no open positions in file
    if len(open_positions_dict) < 1:
        return "complete"

    # Create live position tickers list
    markets_live = list(exchange_pos.keys())

    # Protect API
    await asyncio.sleep(0.5)

    # Check all saved positions match order record
    # Exit trade according to any exit trade rules
    for position in open_positions_dict:
        try:

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

            ## Ensure sizes match what was sent to the exchange
            # Size drift (partial-fill reconciliation, manual resize) is a warning;
            # market/side identity mismatches below remain hard failures.
            if str(position_size_m1) != str(order_size_m1):
                logger.warning(
                    "Tracked size {} for {} diverges from exchange order size {}",
                    position_size_m1,
                    position_market_m1,
                    order_size_m1,
                )
            if str(position_size_m2) != str(order_size_m2):
                logger.warning(
                    "Tracked size {} for {} diverges from exchange order size {}",
                    position_size_m2,
                    position_market_m2,
                    order_size_m2,
                )
            # Override size to match what DYDX exchange has (authoritative for exits)
            position_size_m1 = order_m1["size"]
            position_size_m2 = order_m2["size"]

            # Perform matching checks
            check_m1 = (
                position_market_m1 == order_market_m1
                and position_side_m1 == order_side_m1
            )
            check_m2 = (
                position_market_m2 == order_market_m2
                and position_side_m2 == order_side_m2
            )
            m1_live = position_market_m1 in markets_live
            m2_live = position_market_m2 in markets_live
            check_live = m1_live and m2_live

            # Guard: If not all match exit with error
            if not check_m1 or not check_m2 or not check_live:
                if check_m1 and check_m2 and (m1_live != m2_live):
                    orphan_market = (
                        position_market_m1 if m1_live else position_market_m2
                    )
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
                    # Both legs are flat on-exchange but this code path never
                    # persisted the close (e.g. closed manually, close-order
                    # confirmation raced a fill, or liquidation). Persist the
                    # close and emit an audit event so trade history and the
                    # realtime positions view stay truthful instead of reporting
                    # a permanently-open trade.
                    position["pair_status"] = "CLOSE_CONFIRMED_EXTERNAL"
                    position["last_exit_reason"] = "external_close"
                    persisted_trade_id = persist_live_trade_closed(
                        position,
                        exit_price1=position.get("order_m1_price"),
                        exit_price2=position.get("order_m2_price"),
                        exit_size1=position_size_m1,
                        exit_size2=position_size_m2,
                    )
                    persist_trade_activity_event(
                        "trade_exit_close_confirmed_external",
                        (
                            f"Tracked pair {position_market_m1} / {position_market_m2} "
                            "found flat on exchange without a bot-submitted close"
                        ),
                        severity="warning",
                        details={
                            "market_1": position_market_m1,
                            "market_2": position_market_m2,
                            "exit_reason": "external_close",
                        },
                        related_trade_id=persisted_trade_id,
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
            if DYDX_API_THROTTLE_SECONDS > 0:
                await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)
            series_2 = await get_candles_recent(client, position_market_m2)
            if DYDX_API_THROTTLE_SECONDS > 0:
                await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)

            series_1_numeric = _as_numeric_series(series_1, field_name="series_1_exit")
            series_2_numeric = _as_numeric_series(series_2, field_name="series_2_exit")

            # Get markets for reference of tick size
            markets = await get_markets(client)
            z_score_traded: float = _as_float(
                position["z_score"], field_name="z_score_traded"
            )
            z_score_current: float = z_score_traded

            # Protect API
            if DYDX_API_THROTTLE_SECONDS > 0:
                await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)

            price_m1 = _as_float(series_1_numeric.iloc[-1], field_name="price_m1")
            price_m2 = _as_float(series_2_numeric.iloc[-1], field_name="price_m2")
            unrealized_pnl_pct = 0.0
            pnl_available = False
            if STOP_LOSS_PCT > 0 or TAKE_PROFIT_PCT > 0 or TRAILING_STOP_PCT > 0:
                try:
                    unrealized_pnl_pct = _pair_unrealized_pnl_pct(
                        position,
                        current_price1=price_m1,
                        current_price2=price_m2,
                    )
                    pnl_available = True
                except Exception as exc:
                    logger.warning(
                        "Unable to evaluate PnL-based exit controls for {} / {}: {}",
                        position_market_m1,
                        position_market_m2,
                        exc,
                    )
                    position["last_exit_warning"] = str(exc)
                    position["last_exit_warning_at"] = _utc_now_iso()
            # The trailing stop is only judged on a P&L that was actually
            # computed: the 0.0 fallback above would read as a full give-back
            # from any armed peak and close the pair for no reason.
            peak_unrealized_pnl_pct: Optional[float] = None
            if TRAILING_STOP_PCT > 0 and pnl_available:
                peak_unrealized_pnl_pct = _fold_peak_unrealized_pnl(
                    position, unrealized_pnl_pct
                )
            position_age_hours = _position_open_age_hours(position)

            if CLOSE_AT_ZSCORE_CROSS:
                hedge_ratio = _as_float(
                    position["hedge_ratio"], field_name="hedge_ratio"
                )
                intercept = _as_float(
                    position.get("intercept", 0.0), field_name="intercept"
                )
                if len(series_1_numeric) > 0 and len(series_1_numeric) == len(
                    series_2_numeric
                ):
                    spread = (
                        series_1_numeric - (hedge_ratio * series_2_numeric) - intercept
                    )
                    z_score_current = _as_float(
                        calculate_zscore(spread).values.tolist()[-1],
                        field_name="z_score_current",
                    )

            exit_reason = _resolve_exit_reason(
                z_score_current=z_score_current,
                z_score_traded=z_score_traded,
                unrealized_pnl_pct=unrealized_pnl_pct,
                position_age_hours=position_age_hours,
                peak_unrealized_pnl_pct=peak_unrealized_pnl_pct,
            )
            is_close = exit_reason is not None

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

                # Accept-price band scales with exit urgency: stop-losses and
                # trailing stops must fill NOW (a 5% band lets them sit
                # unfilled through good-til-block expiry in fast markets);
                # discretionary exits keep the tighter band.
                exit_reason_key = str(exit_reason or "exit_signal")
                if exit_reason_key in ("stop_loss", "trailing_stop"):
                    _exit_buffer = 1.0 + _stop_exit_buffer_pct() / 100.0
                else:
                    _exit_buffer = 1.0 + _exit_buffer_pct() / 100.0
                accept_price_m1 = (
                    price_m1 * _exit_buffer
                    if side_m1 == "BUY"
                    else price_m1 * (2.0 - _exit_buffer)
                )
                accept_price_m2 = (
                    price_m2 * _exit_buffer
                    if side_m2 == "BUY"
                    else price_m2 * (2.0 - _exit_buffer)
                )
                tick_size_m1 = markets["markets"][position_market_m1]["tickSize"]
                tick_size_m2 = markets["markets"][position_market_m2]["tickSize"]
                accept_price_m1_formatted = format_number(accept_price_m1, tick_size_m1)
                accept_price_m2_formatted = format_number(accept_price_m2, tick_size_m2)

                # Close positions
                close_order_m1 = None
                close_order_m2 = None
                close_order_m1_id = ""
                close_order_m2_id = ""
                close_order_time_m1 = ""
                close_order_time_m2 = ""
                exit_reason_text = _exit_reason_label(exit_reason_key)
                position["pair_status"] = "CLOSE_SUBMITTED"
                position["last_exit_reason"] = exit_reason_key
                position["last_exit_signal_at"] = _utc_now_iso()
                persist_trade_activity_event(
                    "trade_exit_attempt_started",
                    (
                        f"Exit trigger ({exit_reason_key}) for "
                        f"{position_market_m1} / {position_market_m2}"
                    ),
                    details={
                        "market_1": position_market_m1,
                        "market_2": position_market_m2,
                        "z_score_current": float(z_score_current),
                        "z_score_traded": float(z_score_traded),
                        "exit_reason": exit_reason_key,
                        "unrealized_pnl_pct": float(unrealized_pnl_pct),
                        "peak_unrealized_pnl_pct": peak_unrealized_pnl_pct,
                        "position_age_hours": float(position_age_hours),
                    },
                )
                try:
                    logger.info(
                        "Closing position for {} (subaccount inferred)",
                        position_market_m1,
                    )

                    # Snapshot the account aggregates BEFORE our closes so
                    # confirmation can attribute our share on a shared
                    # subaccount (flat-for-us = aggregate dropped by our
                    # tracked size, not aggregate == 0).
                    try:
                        pre_close_exchange = await get_open_positions(client)
                        pre_close_sizes = {
                            market_key: _remaining_leg_size(
                                pre_close_exchange.get(market_key), None
                            )
                            for market_key in (position_market_m1, position_market_m2)
                        }
                    except Exception as snapshot_error:
                        pre_close_sizes = {}
                        logger.warning(
                            "Could not snapshot pre-close aggregate sizes for "
                            "{} / {}: {}",
                            position_market_m1,
                            position_market_m2,
                            snapshot_error,
                        )

                    close_order_m1, close_order_m1_id = (
                        await _place_reduce_only_close_with_retries(
                            client,
                            market=position_market_m1,
                            side=side_m1,
                            size=position_size_m1,
                            price=accept_price_m1_formatted,
                            attempts=3,
                        )
                    )

                    logger.debug("Close order m1 id: {}", close_order_m1.get("id"))
                    position["close_order_m1_id"] = close_order_m1_id
                    close_order_time_m1 = _utc_now_iso()

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
                            price=accept_price_m2_formatted,
                            attempts=3,
                        )
                    )

                    logger.debug("Close order m2 id: {}", close_order_m2.get("id"))
                    position["close_order_m2_id"] = close_order_m2_id
                    close_order_time_m2 = _utc_now_iso()
                    position["pair_status"] = "CLOSING"

                    close_confirmation = await _confirm_exchange_flat_after_close(
                        client,
                        position=position,
                        close_order_ids={
                            "market_1": close_order_m1_id,
                            "market_2": close_order_m2_id,
                        },
                        pre_close_sizes=pre_close_sizes or None,
                    )
                    position.update(close_confirmation)

                    if bool(close_confirmation.get("flat_confirmed")):
                        position["pair_status"] = "CLOSE_CONFIRMED"
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
                        messenger.send_trade_closed_message(
                            trade_info, exit_reason_text
                        )
                        # Record what the close actually filled at, not the
                        # accept-band price used at submission time.
                        exit_price_m1, exit_price_m1_source = (
                            await _exit_price_from_fills(
                                client,
                                close_order_m1_id,
                                position_market_m1,
                                accept_price_m1_formatted,
                            )
                        )
                        exit_price_m2, exit_price_m2_source = (
                            await _exit_price_from_fills(
                                client,
                                close_order_m2_id,
                                position_market_m2,
                                accept_price_m2_formatted,
                            )
                        )
                        position["exit_price_m1_source"] = exit_price_m1_source
                        position["exit_price_m2_source"] = exit_price_m2_source
                        realized = await _realized_pnl_for_closed_pair(
                            client,
                            position,
                            exit_price_m1=exit_price_m1,
                            exit_price_m2=exit_price_m2,
                            exit_size_m1=position_size_m1,
                            exit_size_m2=position_size_m2,
                            close_order_m1_id=close_order_m1_id,
                            close_order_m2_id=close_order_m2_id,
                        )
                        persisted_trade_id = persist_live_trade_closed(
                            position,
                            exit_price1=exit_price_m1,
                            exit_price2=exit_price_m2,
                            exit_size1=position_size_m1,
                            exit_size2=position_size_m2,
                            realized_pnl=realized.net if realized else None,
                            realized_pnl_pct=realized.net_pct if realized else None,
                        )
                        persist_trade_activity_event(
                            "trade_exit_close_confirmed",
                            (
                                f"Confirmed flat exchange state for {position_market_m1} / "
                                f"{position_market_m2}"
                            ),
                            details={
                                "market_1": position_market_m1,
                                "market_2": position_market_m2,
                                "close_order_m1_id": close_order_m1_id,
                                "close_order_m2_id": close_order_m2_id,
                                "close_order_m1_side": side_m1,
                                "close_order_m2_side": side_m2,
                                "close_order_m1_size": position_size_m1,
                                "close_order_m2_size": position_size_m2,
                                "close_order_m1_price": exit_price_m1,
                                "close_order_m2_price": exit_price_m2,
                                "close_order_m1_price_source": exit_price_m1_source,
                                "close_order_m2_price_source": exit_price_m2_source,
                                "close_order_time_m1": close_order_time_m1,
                                "close_order_time_m2": close_order_time_m2,
                                "z_score": float(z_score_current),
                                "exit_reason": exit_reason_key,
                                "confirmation_attempts": int(
                                    close_confirmation.get("attempt", 0) or 0
                                ),
                            },
                            related_trade_id=persisted_trade_id,
                        )
                        continue

                    confirmation_state = str(
                        close_confirmation.get("pair_status") or "CLOSING"
                    )
                    confirmation_detail = (
                        f"Close submitted for {position_market_m1} / {position_market_m2} "
                        f"but flat state was not confirmed. state={confirmation_state}"
                    )
                    messenger.send_error_message(
                        f"CRITICAL: Exit Not Confirmed ({confirmation_state})",
                        confirmation_detail,
                        is_critical=True,
                        category="execution_exit_confirmation_failed",
                    )
                    logger.critical(confirmation_detail)
                    persist_trade_activity_event(
                        "trade_exit_confirmation_failed",
                        confirmation_detail,
                        severity="critical",
                        details={
                            "market_1": position_market_m1,
                            "market_2": position_market_m2,
                            "close_order_m1_id": close_order_m1_id,
                            "close_order_m2_id": close_order_m2_id,
                            "exit_reason": exit_reason_key,
                            "confirmation_state": confirmation_state,
                            "confirmation_details": close_confirmation,
                        },
                    )
                    save_output.append(position)
                    continue

                except Exception as exc:
                    logger.exception(
                        "Exit failed for {} / {}",
                        position_market_m1,
                        position_market_m2,
                    )
                    if close_order_m1 is not None and close_order_m2 is None:
                        position["pair_status"] = "ORPHANED_EXIT_FAILED"
                        position["orphaned_market"] = position_market_m2
                        position["close_order_m1_id"] = close_order_m1_id
                        position["last_exit_error"] = str(exc)
                        position["last_exit_error_at"] = _utc_now_iso()
                        critical_detail = (
                            f"Submitted close for {position_market_m1} but failed to close "
                            f"{position_market_m2}: {exc}"
                        )
                        messenger.send_error_message(
                            "CRITICAL: Partial Close Exposure",
                            critical_detail,
                            is_critical=True,
                            category="execution_partial_close_failed",
                        )
                        logger.critical(
                            "First close leg succeeded for {} / {}, second leg failed; orphaned {} exposure remains",
                            position_market_m1,
                            position_market_m2,
                            position_market_m2,
                        )
                        persist_trade_activity_event(
                            "trade_exit_orphaned",
                            critical_detail,
                            severity="critical",
                            details={
                                "market_1": position_market_m1,
                                "market_2": position_market_m2,
                                "close_order_m1_id": close_order_m1_id,
                                "close_order_m1_side": side_m1,
                                "close_order_m1_size": position_size_m1,
                                "close_order_m1_price": accept_price_m1_formatted,
                                "close_order_time_m1": close_order_time_m1,
                                "exit_reason": exit_reason_key,
                                "error": str(exc),
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

        except Exception as exc:
            # One unreadable or diverged position must not block exit
            # management (stops, z-score exits) for every other tracked
            # position: keep it tracked, alert, and continue the pass.
            position["last_exit_error"] = str(exc)
            position["last_exit_error_at"] = _utc_now_iso()
            logger.exception(
                "Exit management failed for tracked position {} / {}",
                position.get("market_1", "?"),
                position.get("market_2", "?"),
            )
            messenger.send_error_message(
                "CRITICAL: Exit Management Failed",
                (
                    f"Exit management failed for {position.get('market_1', '?')} / "
                    f"{position.get('market_2', '?')}: {exc}. "
                    "Position remains tracked; manual verification required."
                ),
                is_critical=True,
                category="exit_management_failed",
            )
            save_output.append(position)
            continue

    # Save remaining items
    logger.info("{} items remaining; persisting {}", len(save_output), BOT_AGENTS_PATH)
    await save_processed_positions(open_positions_dict, save_output)
    return None
