"""Optional Celery Beat market-data sync tasks."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

from src.infrastructure.workers.celery_app import celery_app


def _enabled() -> bool:
    return os.getenv("MARKET_SYNC_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@celery_app.task(name="bot.sync_market_candles")
def sync_market_candles() -> Dict[str, Any]:
    """Import-safe scheduler hook; disabled unless explicitly configured."""
    if not _enabled():
        return {
            "status": "skipped",
            "reason": "MARKET_SYNC_ENABLED is false",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    return {
        "status": "skipped",
        "reason": "market sync implementation is not configured for this deployment",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
