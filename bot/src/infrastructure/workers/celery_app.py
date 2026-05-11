"""Celery application for durable bot background work."""

from __future__ import annotations

import os
from urllib.parse import quote

from celery import Celery


def _redis_url(db_offset: int = 0) -> str:
    explicit_url = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL")
    if explicit_url:
        return explicit_url

    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    db = int(os.getenv("REDIS_DB", "0") or 0) + db_offset
    password = os.getenv("REDIS_PASSWORD", "")
    scheme = "rediss" if os.getenv("REDIS_SSL", "false").lower() == "true" else "redis"
    auth = f":{quote(password)}@" if password else ""
    return f"{scheme}://{auth}{host}:{port}/{db}"


celery_app = Celery(
    "dydx_bot",
    broker=_redis_url(0),
    backend=os.getenv("CELERY_RESULT_BACKEND") or _redis_url(1),
    include=[
        "src.infrastructure.workers.backtest_tasks",
        "src.infrastructure.workers.candle_aggregate_tasks",
        "src.infrastructure.workers.market_sync_tasks",
    ],
)

_MARKET_SYNC_INTERVAL = float(os.getenv("MARKET_SYNC_INTERVAL_SECONDS", "10"))

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")),
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    result_extended=True,
    task_time_limit=int(
        os.getenv("BACKTEST_CELERY_TASK_TIME_LIMIT", str(7 * 24 * 60 * 60))
    ),
    task_soft_time_limit=int(
        os.getenv("BACKTEST_CELERY_TASK_SOFT_TIME_LIMIT", str(7 * 24 * 60 * 60 - 60))
    ),
    broker_connection_retry_on_startup=True,
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", str(24 * 60 * 60))),
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "sync-market-candles": {
            "task": "bot.sync_market_candles",
            "schedule": _MARKET_SYNC_INTERVAL,
        },
    },
)
