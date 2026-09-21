"""Refuse new entries while the dYdX indexer is behind the chain.

Everything the runtime reads comes from the indexer: prices, positions and the
status of its own orders. When the indexer stalls (the public testnet one was
19 hours behind on 2026-09-21) the bot trades on old prices and cannot confirm
an order it has just placed, which ends in an emergency close and a critical
alert for a leg that never existed.

The check is self-healing: it blocks the current scan cycle only, and entries
resume on their own once the indexer has caught up. It never latches. Exits are
not affected.

Configuration:
    BOT_INDEXER_MAX_LAG_SECONDS    maximum age of the indexer's latest block
                                   (default 120; 0 disables the check)
    BOT_INDEXER_STALE_ALERT_SECONDS  minimum gap between operator alerts while
                                   the indexer stays stale (default 1800)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.infrastructure import resilience

DEFAULT_MAX_LAG_SECONDS = 120.0
ENV_MAX_LAG_SECONDS = "BOT_INDEXER_MAX_LAG_SECONDS"
DEFAULT_ALERT_INTERVAL_SECONDS = 1800.0
ENV_ALERT_INTERVAL_SECONDS = "BOT_INDEXER_STALE_ALERT_SECONDS"

_last_alert_at: Optional[datetime] = None


@dataclass(frozen=True)
class IndexerStaleness:
    """Why entries are blocked this cycle."""

    reason: str
    lag_seconds: Optional[float]
    max_lag_seconds: float
    indexer_height: Optional[str] = None
    indexer_time: Optional[str] = None

    def describe(self) -> str:
        if self.lag_seconds is None:
            return f"dYdX indexer freshness could not be verified ({self.reason})"
        return (
            f"dYdX indexer is {format_lag(self.lag_seconds)} behind the chain "
            f"(latest indexed block {self.indexer_height} at {self.indexer_time}; "
            f"limit {format_lag(self.max_lag_seconds)})"
        )


def format_lag(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 120:
        return f"{seconds:.0f}s"
    if seconds < 2 * 3600:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def max_lag_seconds() -> float:
    raw = os.getenv(ENV_MAX_LAG_SECONDS, "").strip()
    if not raw:
        return DEFAULT_MAX_LAG_SECONDS
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_MAX_LAG_SECONDS


def _parse_indexer_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def check_indexer_freshness(
    client: Any, *, now: Optional[datetime] = None
) -> Optional[IndexerStaleness]:
    """Return why entries must wait, or ``None`` when the indexer is current.

    Fails closed: if the height cannot be read or parsed, the indexer is not
    known to be current, so entries wait for the next cycle.
    """
    limit = max_lag_seconds()
    if limit <= 0:
        return None

    try:
        payload = await resilience.call_async(
            "dydx_indexer", lambda: client.indexer.utility.get_height()
        )
    except Exception as exc:
        return IndexerStaleness(
            reason=f"height request failed: {type(exc).__name__}",
            lag_seconds=None,
            max_lag_seconds=limit,
        )

    indexed_at = _parse_indexer_time(
        payload.get("time") if isinstance(payload, dict) else None
    )
    if indexed_at is None:
        return IndexerStaleness(
            reason="height response carried no usable block time",
            lag_seconds=None,
            max_lag_seconds=limit,
        )

    current = now or datetime.now(timezone.utc)
    lag = (current - indexed_at).total_seconds()
    if lag <= limit:
        return None
    return IndexerStaleness(
        reason="indexer is behind the chain",
        lag_seconds=lag,
        max_lag_seconds=limit,
        indexer_height=str(payload.get("height")),
        indexer_time=indexed_at.isoformat(),
    )


def should_alert(*, now: Optional[datetime] = None) -> bool:
    """Rate-limit the operator alert: a scan cycle runs every few seconds and a
    stall can last hours, so the condition is reported once per interval."""
    global _last_alert_at
    raw = os.getenv(ENV_ALERT_INTERVAL_SECONDS, "").strip()
    try:
        interval = max(0.0, float(raw)) if raw else DEFAULT_ALERT_INTERVAL_SECONDS
    except ValueError:
        interval = DEFAULT_ALERT_INTERVAL_SECONDS

    current = now or datetime.now(timezone.utc)
    if (
        _last_alert_at is not None
        and (current - _last_alert_at).total_seconds() < interval
    ):
        return False
    _last_alert_at = current
    return True
