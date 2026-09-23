"""Bot-level max drawdown: stop opening pairs once the account has fallen too far.

A strategy's ``max_drawdown_pct`` is measured on the equity of the subaccount
the runtime trades on, as the exchange reports it: marked to market, after
fees and funding. The peak is the highest equity seen since the measurement
began, which is when the runtime first looked at that subaccount or when an
operator last cleared a drawdown halt. Once equity is ``max_drawdown_pct``
percent below the peak, new entries are halted through the durable entry-halt
latch (:mod:`src.trading.entry_halt`, kind ``max_drawdown``). The operator
clears it from the strategy card like any other entry halt, and the
measurement then starts again from the equity the runtime sees next.

Open pairs are not closed. Their own exits (stop loss, take profit, trailing
stop, timeout, z-score reversion) keep running.

The peak is kept per runtime and subaccount, so a restart or a replaced pod
does not reset it: in the ``drawdown_peaks`` table for managed runtimes, in a
file next to the tracked positions for a standalone run. When the guard halts
entries it marks the peak as tripped, so a halt that was lost before an
operator cleared it is set again rather than forgotten.

Fail closed: when the equity or the stored peak cannot be read or saved, no
pair is opened that cycle.

This is not ``BOT_PORTFOLIO_MAX_DRAWDOWN_PCT`` (:mod:`src.trading.portfolio_risk`).
That one is deployment-wide, keeps its peak in Redis, skips itself when Redis
is down and denies entries cycle by cycle without latching.

Known limits: a withdrawal lowers equity and counts as drawdown, a deposit
raises the peak, and anything else held on the same subaccount moves its
equity too.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx
from loguru import logger
from sqlalchemy import text as _sa_text
from sqlalchemy.exc import SQLAlchemyError

from src.exceptions import BotError
from src.trading import bot_agents_state, entry_halt
from src.trading.account_manager import get_account
from src.trading.arbitrage_observability import record_rejection
from src.trading.entry_halt import HaltScope
from src.trading.trade_persistence import persist_trade_activity_event

STATE_FILE_PREFIX = "drawdown_peak"
ALERT_INTERVAL_SECONDS = 1800.0

# The equity is unknown when the account read fails in transport, at the
# circuit breaker or on a malformed payload.
_EQUITY_READ_ERRORS: tuple[type[BaseException], ...] = (
    httpx.HTTPError,
    asyncio.TimeoutError,
    BotError,
    OSError,
    KeyError,
    TypeError,
    ValueError,
)
# The stored peak is unknown when the database or the state file cannot be read
# or written, or holds something that is not a peak.
_STORE_ERRORS: tuple[type[BaseException], ...] = (
    SQLAlchemyError,
    OSError,
    RuntimeError,
    KeyError,
    TypeError,
    ValueError,
)

AccountReader = Callable[[Any], Awaitable[Any]]

_last_alert_at: Dict[str, datetime] = {}


@dataclass(frozen=True)
class DrawdownState:
    """The equity peak a runtime measures its drawdown from."""

    peak_equity: float
    peak_at: str
    baseline_at: str
    tripped_at: Optional[str] = None


@dataclass(frozen=True)
class DrawdownDecision:
    allowed: bool
    equity: float
    peak_equity: float
    drawdown_pct: float
    limit_pct: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        moment: datetime = (
            value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        )
        return moment.astimezone(timezone.utc).isoformat()
    return str(value)


def _as_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def evaluate_drawdown(
    *, equity: float, peak_equity: float, limit_pct: float
) -> DrawdownDecision:
    """Drawdown of ``equity`` below ``peak_equity`` in percent, and whether it is
    still under ``limit_pct``. Reaching the limit counts as a breach."""
    if not (math.isfinite(peak_equity) and peak_equity > 0):
        raise ValueError(f"peak equity must be a positive number, got {peak_equity!r}")
    drawdown_pct = max(0.0, (peak_equity - equity) / peak_equity * 100.0)
    return DrawdownDecision(
        allowed=drawdown_pct < limit_pct,
        equity=equity,
        peak_equity=peak_equity,
        drawdown_pct=drawdown_pct,
        limit_pct=limit_pct,
    )


def _equity_from(account: Any) -> Optional[float]:
    raw = account.get("equity") if isinstance(account, dict) else None
    if raw is None or raw == "":
        return None
    value = float(raw)
    return value if math.isfinite(value) else None


# ------------------------------------------------------------------------ store


def _uses_database(scope: HaltScope) -> bool:
    return scope.instance_id != entry_halt.STANDALONE_INSTANCE_ID


def state_file_for(instance_id: str) -> Path:
    directory = bot_agents_state.BOT_AGENTS_PATH.parent
    if instance_id == entry_halt.STANDALONE_INSTANCE_ID:
        return directory / f"{STATE_FILE_PREFIX}.json"
    return directory / f"{STATE_FILE_PREFIX}_{instance_id}.json"


def _scope_params(scope: HaltScope) -> Dict[str, Any]:
    return {
        "instance_id": scope.instance_id,
        "network": scope.network,
        "address": scope.address,
        "subaccount": scope.subaccount_number,
    }


def _db_load_state(scope: HaltScope) -> Optional[DrawdownState]:
    from src.infrastructure.database import db

    session = db.get_session()
    try:
        row = session.execute(
            _sa_text(
                "SELECT peak_equity, peak_at, baseline_at, tripped_at "
                "FROM drawdown_peaks WHERE instance_id = :instance_id "
                "AND network = :network AND address = :address "
                "AND subaccount_number = :subaccount"
            ),
            _scope_params(scope),
        ).fetchone()
    finally:
        session.close()
    if row is None:
        return None
    return DrawdownState(
        peak_equity=float(row.peak_equity),
        peak_at=_iso(row.peak_at) or "",
        baseline_at=_iso(row.baseline_at) or "",
        tripped_at=_iso(row.tripped_at),
    )


def _db_save_state(scope: HaltScope, state: DrawdownState) -> None:
    from src.infrastructure.database import db

    params = {
        **_scope_params(scope),
        "peak_equity": state.peak_equity,
        "peak_at": _as_datetime(state.peak_at),
        "baseline_at": _as_datetime(state.baseline_at),
        "tripped_at": _as_datetime(state.tripped_at),
        "updated_at": _utc_now(),
    }
    session = db.get_session()
    try:
        result = session.execute(
            _sa_text(
                "UPDATE drawdown_peaks SET peak_equity = :peak_equity, "
                "peak_at = :peak_at, baseline_at = :baseline_at, "
                "tripped_at = :tripped_at, updated_at = :updated_at "
                "WHERE instance_id = :instance_id AND network = :network "
                "AND address = :address AND subaccount_number = :subaccount"
            ),
            params,
        )
        if not int(getattr(result, "rowcount", 0) or 0):
            session.execute(
                _sa_text(
                    "INSERT INTO drawdown_peaks (instance_id, network, address, "
                    "subaccount_number, peak_equity, peak_at, baseline_at, "
                    "tripped_at, updated_at) VALUES (:instance_id, :network, "
                    ":address, :subaccount, :peak_equity, :peak_at, :baseline_at, "
                    ":tripped_at, :updated_at)"
                ),
                params,
            )
        session.commit()
    finally:
        session.close()


def _db_reset_baselines(scope: HaltScope) -> int:
    from src.infrastructure.database import db

    session = db.get_session()
    try:
        result = session.execute(
            _sa_text(
                "DELETE FROM drawdown_peaks WHERE network = :network "
                "AND address = :address AND subaccount_number = :subaccount"
            ),
            _scope_params(scope),
        )
        session.commit()
        return int(getattr(result, "rowcount", 0) or 0)
    finally:
        session.close()


def _file_load_state(scope: HaltScope) -> Optional[DrawdownState]:
    path = state_file_for(scope.instance_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"drawdown state in {path} is not an object")
    stored_scope = (
        str(payload.get("network", "")),
        str(payload.get("address", "")),
        int(payload.get("subaccount_number", -1)),
    )
    if stored_scope != (scope.network, scope.address, scope.subaccount_number):
        # Another subaccount starts its own measurement.
        return None
    return DrawdownState(
        peak_equity=float(payload["peak_equity"]),
        peak_at=str(payload["peak_at"]),
        baseline_at=str(payload["baseline_at"]),
        tripped_at=_iso(payload.get("tripped_at")),
    )


def _file_save_state(scope: HaltScope, state: DrawdownState) -> None:
    path = state_file_for(scope.instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "network": scope.network,
        "address": scope.address,
        "subaccount_number": scope.subaccount_number,
        "peak_equity": state.peak_equity,
        "peak_at": state.peak_at,
        "baseline_at": state.baseline_at,
        "tripped_at": state.tripped_at,
    }
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def load_state(scope: HaltScope) -> Optional[DrawdownState]:
    """Stored peak for the runtime and subaccount, ``None`` before the first
    observation. Raises when it cannot be read or is not a usable peak."""
    if _uses_database(scope):
        state = _db_load_state(scope)
    else:
        state = _file_load_state(scope)
    if state is not None and not (
        math.isfinite(state.peak_equity) and state.peak_equity > 0
    ):
        raise ValueError(
            f"stored drawdown peak {state.peak_equity!r} is not a positive number"
        )
    return state


def save_state(scope: HaltScope, state: DrawdownState) -> None:
    if _uses_database(scope):
        _db_save_state(scope, state)
    else:
        _file_save_state(scope, state)


def reset_baselines(scope: HaltScope) -> int:
    """Start drawdown measurement again on the scope's subaccount.

    Every runtime there measures from the equity it sees next. Called when an
    operator clears a drawdown halt; raises when the reset cannot be stored, so
    the halt is not cleared without it.
    """
    if _uses_database(scope):
        removed = _db_reset_baselines(scope)
    else:
        path = state_file_for(scope.instance_id)
        removed = 0
        if path.exists():
            path.unlink()
            removed = 1
    logger.warning(
        "Drawdown on {} subaccount {} is measured again from current equity "
        "({} stored peak(s) reset)",
        scope.network,
        scope.subaccount_number,
        removed,
    )
    return removed


# ------------------------------------------------------------------------ check


def _should_alert(key: str, *, now: Optional[datetime] = None) -> bool:
    """A scan cycle runs every few seconds; report a lasting condition once per
    interval."""
    current = now or _utc_now()
    last = _last_alert_at.get(key)
    if last is not None and (current - last).total_seconds() < ALERT_INTERVAL_SECONDS:
        return False
    _last_alert_at[key] = current
    return True


def _report_unavailable(messenger: Any, scope: HaltScope, detail: str) -> None:
    record_rejection("drawdown_state_unavailable")
    logger.warning(
        "Entries skipped this cycle: drawdown on {} subaccount {} cannot be "
        "measured: {}",
        scope.network,
        scope.subaccount_number,
        detail,
    )
    if _should_alert("unavailable"):
        messenger.send_error_message(
            "Entries paused: drawdown cannot be measured",
            f"{scope.network} subaccount {scope.subaccount_number}: {detail}. No "
            "new pairs are opened until the equity and its stored peak can be "
            "read; open positions are still managed.",
            is_critical=False,
            category="execution_drawdown_unavailable",
        )


def _latch(
    scope: HaltScope,
    state: DrawdownState,
    decision: DrawdownDecision,
    messenger: Any,
    scan_cycle_id: str,
    *,
    reasserted: bool = False,
) -> None:
    """Halt new entries on the subaccount, mark the peak as tripped, and say so."""
    record_rejection("max_drawdown")
    measured = (
        f"equity {decision.equity:,.2f} is {decision.drawdown_pct:.2f}% below its "
        f"peak {decision.peak_equity:,.2f} (limit {decision.limit_pct:g}%)"
    )
    if reasserted:
        reason = (
            f"max drawdown halt set again: the limit was reached at "
            f"{state.tripped_at} and no operator has cleared it since; {measured}"
        )
    else:
        reason = f"max drawdown reached: {measured}"
    details: Dict[str, Any] = {
        "kind": entry_halt.KIND_MAX_DRAWDOWN,
        "equity": round(decision.equity, 2),
        "peak_equity": round(decision.peak_equity, 2),
        "drawdown_pct": round(decision.drawdown_pct, 4),
        "limit_pct": decision.limit_pct,
        "peak_at": state.peak_at,
        "baseline_at": state.baseline_at,
        "scan_cycle_id": scan_cycle_id,
    }
    if reasserted:
        details["reasserted"] = True
        details["tripped_at"] = state.tripped_at

    halt_error: Optional[str] = None
    try:
        entry_halt.halt_entries(reason, details, scope=scope)
    except RuntimeError as exc:
        halt_error = str(exc)
        logger.critical(
            "Drawdown halt could not be persisted for {} subaccount {}: {}",
            scope.network,
            scope.subaccount_number,
            exc,
        )

    if halt_error is None and state.tripped_at is None:
        try:
            save_state(scope, replace(state, tripped_at=_utc_now().isoformat()))
        except _STORE_ERRORS as exc:
            # The halt holds. Without the mark, clearing it is followed by one
            # more halt on the next cycle, measured from the old peak.
            logger.error(
                "Drawdown halt is set, but could not be marked on the stored peak "
                "for {} subaccount {}: {}",
                scope.network,
                scope.subaccount_number,
                exc,
            )

    persist_trade_activity_event(
        "trade_entries_halted",
        f"New entries halted: {reason}",
        severity="critical",
        details={
            **details,
            "halt_persisted": halt_error is None,
            **({"halt_error": halt_error} if halt_error else {}),
        },
    )
    if halt_error is None:
        latch_text = (
            "No new pairs are opened on this subaccount until an operator clears "
            "the halt; open positions keep their exits."
        )
    elif not _should_alert("halt_not_persisted"):
        return
    else:
        latch_text = f"Stop this bot until the account is reviewed: {halt_error}."
    messenger.send_error_message(
        "CRITICAL: New entries halted (max drawdown)",
        f"{scope.network} subaccount {scope.subaccount_number}: {reason}. "
        f"{latch_text}",
        is_critical=True,
        category="execution_max_drawdown",
    )


async def check_entry_drawdown(
    client: Any,
    *,
    limit_pct: float,
    messenger: Any,
    scan_cycle_id: str = "",
    read_account: Optional[AccountReader] = None,
) -> bool:
    """True when the drawdown limit lets this cycle open pairs.

    Runs once per entry cycle, after the entry-halt check (so no halt is active
    here) and before any pair is looked at, so the peak follows equity every
    cycle. With the limit at 0 it reads nothing and stores nothing.
    """
    if not limit_pct > 0:
        return True
    scope = entry_halt.current_scope()
    reader = read_account or get_account
    try:
        equity = _equity_from(await reader(client))
    except _EQUITY_READ_ERRORS as exc:
        _report_unavailable(
            messenger, scope, f"account equity could not be read ({exc})"
        )
        return False
    if equity is None or equity <= 0:
        _report_unavailable(
            messenger, scope, f"account equity is not usable ({equity})"
        )
        return False

    try:
        stored = load_state(scope)
    except _STORE_ERRORS as exc:
        _report_unavailable(
            messenger, scope, f"the stored equity peak could not be read ({exc})"
        )
        return False

    if stored is not None and stored.tripped_at is not None:
        # The guard halted entries before and no operator clear has reset it
        # (a clear removes the stored peak), yet no halt is active: the halt
        # never reached the database and the pod holding its file is gone.
        # Set it again instead of resuming.
        decision = evaluate_drawdown(
            equity=equity, peak_equity=stored.peak_equity, limit_pct=limit_pct
        )
        _latch(scope, stored, decision, messenger, scan_cycle_id, reasserted=True)
        return False

    now = _utc_now().isoformat()
    if stored is None:
        state = DrawdownState(peak_equity=equity, peak_at=now, baseline_at=now)
        logger.info(
            "Drawdown on {} subaccount {} is measured from equity {:.2f} "
            "(limit {:g}%)",
            scope.network,
            scope.subaccount_number,
            equity,
            limit_pct,
        )
    elif equity > stored.peak_equity:
        state = replace(stored, peak_equity=equity, peak_at=now)
    else:
        state = stored

    decision = evaluate_drawdown(
        equity=equity, peak_equity=state.peak_equity, limit_pct=limit_pct
    )
    if not decision.allowed:
        _latch(scope, state, decision, messenger, scan_cycle_id)
        return False
    if state is not stored:
        try:
            save_state(scope, state)
        except _STORE_ERRORS as exc:
            # A restart would otherwise measure from a lower, older peak.
            _report_unavailable(
                messenger, scope, f"the equity peak could not be saved ({exc})"
            )
            return False
    return True


def preflight_drawdown_warning(
    scope: HaltScope, *, equity: float, limit_pct: float
) -> Optional[str]:
    """What an operator should know before starting a runtime with a drawdown
    limit, in dollars. Reads the store synchronously; API callers offload it."""
    if not limit_pct > 0 or not (math.isfinite(equity) and equity > 0):
        return None
    where = f"{scope.network} subaccount {scope.subaccount_number}"
    try:
        stored = load_state(scope)
    except _STORE_ERRORS as exc:
        return (
            f"The drawdown peak recorded for this bot on {where} could not be read "
            f"({exc}); it opens no new pairs until it can."
        )
    if stored is None:
        return (
            f"Max drawdown {limit_pct:g}% is measured on the equity of {where}, "
            f"${equity:,.2f} now: new entries halt once it falls "
            f"${equity * limit_pct / 100.0:,.2f} below its peak. Open positions "
            "are not closed."
        )
    decision = evaluate_drawdown(
        equity=equity,
        peak_equity=max(stored.peak_equity, equity),
        limit_pct=limit_pct,
    )
    if stored.tripped_at is not None or not decision.allowed:
        return (
            f"Equity ${equity:,.2f} on {where} is {decision.drawdown_pct:.2f}% below "
            f"this bot's recorded peak ${decision.peak_equity:,.2f}, at or past its "
            f"{limit_pct:g}% max drawdown: the bot will start and manage open "
            "positions, but halts new entries on its first cycle."
        )
    return (
        f"Max drawdown {limit_pct:g}% is measured on the equity of {where}: "
        f"${equity:,.2f} now, peak ${decision.peak_equity:,.2f}. New entries halt "
        f"below ${decision.peak_equity * (1.0 - limit_pct / 100.0):,.2f}. Open "
        "positions are not closed."
    )
