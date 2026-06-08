"""Optional post-backtest candle aggregation task hooks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from src.infrastructure.workers.celery_app import celery_app


@celery_app.task(name="backtests.aggregate_candles")
def aggregate_backtest_candles(run_id: str) -> Dict[str, Any]:
    """Import-safe aggregation hook.

    The backend falls back to the database when Redis aggregation is unavailable, so
    this task intentionally preserves that behavior until a concrete aggregation
    implementation is added.
    """
    return {
        "run_id": run_id,
        "status": "skipped",
        "reason": "candle aggregation task is a compatibility hook",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
