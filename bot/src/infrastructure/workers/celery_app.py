"""Celery application for durable bot background work."""

from __future__ import annotations

import os
import sys

from celery import Celery
from kombu import Queue

from src.shared import env_loader
from src.shared.redis_env import redis_url

# =============================================================================
# macOS multiprocessing workaround
# =============================================================================
# On macOS, the default fork() multiprocessing start method is incompatible with
# the Objective-C runtime. Set spawn as the default for Celery worker processes.
# This must be set BEFORE any imports that might trigger Objective-C initialization.
# =============================================================================
if sys.platform == "darwin":
    import multiprocessing

    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        # Already set, that's fine
        pass

env_loader.load_repo_env(__file__)

DEFAULT_CELERY_QUEUES = ("backtests", "default", "high_priority", "scheduled")


def _redis_url(db_offset: int = 0) -> str:
    return redis_url(db_offset=db_offset, prefer_celery_broker=True)


def _queue_names() -> tuple[str, ...]:
    raw = os.getenv("CELERY_QUEUES", ",".join(DEFAULT_CELERY_QUEUES))
    queues = tuple(queue.strip() for queue in raw.split(",") if queue.strip())
    return queues or DEFAULT_CELERY_QUEUES


def _beat_schedule() -> dict[str, dict[str, object]]:
    enabled = os.getenv("MARKET_SYNC_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled:
        return {}
    return {
        "sync-market-candles": {
            "task": "bot.sync_market_candles",
            "schedule": _MARKET_SYNC_INTERVAL,
            "options": {"queue": "scheduled"},
        },
    }


celery_app = Celery(
    "dydx_bot",
    broker=_redis_url(0),
    backend=os.getenv("CELERY_RESULT_BACKEND") or _redis_url(1),
    include=[
        "src.infrastructure.workers.backtest_tasks",
        "src.infrastructure.workers.market_sync_tasks",
    ],
)

_MARKET_SYNC_INTERVAL = float(os.getenv("MARKET_SYNC_INTERVAL_SECONDS", "10"))
_QUEUES = _queue_names()

celery_app.conf.update(
    task_default_queue="default",
    task_queues=tuple(Queue(name) for name in _QUEUES),
    task_routes={
        "backtests.run": {"queue": os.getenv("BACKTEST_CELERY_QUEUE", "backtests")},
        "bot.sync_market_candles": {"queue": "scheduled"},
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")),
    worker_max_tasks_per_child=int(
        os.getenv("CELERY_WORKER_MAX_TASKS_PER_CHILD", "100")
    ),
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
    # Visibility timeout must be greater than task_time_limit to prevent re-delivery
    # Default: 10% higher than the hard time limit
    broker_visibility_timeout=int(
        float(
            os.getenv(
                "CELERY_BROKER_VISIBILITY_TIMEOUT",
                str(
                    int(
                        os.getenv(
                            "BACKTEST_CELERY_TASK_TIME_LIMIT", str(7 * 24 * 60 * 60)
                        )
                    )
                    * 1.1
                ),
            )
        )
    ),
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", str(24 * 60 * 60))),
    timezone="UTC",
    enable_utc=True,
    beat_schedule=_beat_schedule(),
)

# Wire the Celery worker metrics producer (ClickHouse worker_metrics). The
# producer is dormant unless BACKTEST_CLICKHOUSE_WRITES_ENABLED=true; see
# src/infrastructure/workers/celery_metrics.py.
from src.infrastructure.workers.celery_metrics import (  # noqa: E402
    register_celery_metrics_signals,
)

register_celery_metrics_signals()
