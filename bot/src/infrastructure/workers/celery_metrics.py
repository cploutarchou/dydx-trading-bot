"""Celery worker metrics producer.

Wires the WorkerMetricsWriter (ClickHouse ``worker_metrics`` table) to Celery
task lifecycle signals so task duration, success/failure, retry count, and
throughput are recorded for every task executed by a Celery worker.

The producer is dormant unless ClickHouse writes are enabled
(``BACKTEST_CLICKHOUSE_WRITES_ENABLED=true``). ``WorkerMetricsWriter.record_*``
no-ops when the underlying analytics writer is disabled, so wiring these signals
never changes task runtime behavior and never blocks task execution.

This closes the Phase 1 gap that the worker_metrics table had a writer/reader but
no producer: the Celery worker is the authoritative async worker, so it is the
correct place to emit worker metrics.
"""

from __future__ import annotations

import os
import socket
import time
from typing import Any, Optional

# task_id -> monotonic start time, populated by task_prerun and consumed by
# task_postrun. Bounded by the number of in-flight tasks in this process.
_task_start_times: dict[str, float] = {}


def _worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def _resolve_writer() -> Optional[Any]:
    """Return the global WorkerMetricsWriter, initializing it lazily from env.

    Reuses BacktestRepository._build_analytics_writer() so ClickHouse connection
    settings are identical to the rest of the bot. Returns a writer even when
    ClickHouse is disabled (it will be a no-op writer), keeping the producer
    wired and ready without changing runtime behavior.
    """
    from src.infrastructure.storage.worker_metrics_writer import (
        get_worker_metrics_writer,
        init_worker_metrics_writer,
    )

    writer = get_worker_metrics_writer()
    if writer is not None:
        return writer
    analytics_writer = None
    try:
        from src.infrastructure.persistence.repository_backtest import (
            BacktestRepository,
        )

        analytics_writer = BacktestRepository._build_analytics_writer()
    except Exception:
        # If the analytics writer cannot be constructed, the producer stays a
        # no-op rather than breaking task execution.
        analytics_writer = None
    return init_worker_metrics_writer(analytics_writer)


def record_celery_task_metric(
    task_id: str,
    task_name: str,
    state: str,
    duration_ms: float,
    retries: int,
    queue_name: str,
    writer: Optional[Any],
) -> None:
    """Record a completed task's metrics via the worker metrics writer.

    Pure with respect to ``writer``: callers pass the writer so this is unit
    testable without Celery or ClickHouse. No-ops when writer is None. Maps the
    Celery task state to success/failure so the worker_metrics read model can
    distinguish completed vs failed work.
    """
    if writer is None:
        return
    writer.record_task_metrics(
        worker_id=_worker_id(),
        worker_type="celery",
        queue_name=queue_name or "celery",
        task_id=task_id,
        task_name=task_name or "unknown",
        duration_ms=max(0.0, float(duration_ms)),
        success=(state == "SUCCESS"),
        retry_count=max(0, int(retries)),
    )


def _on_task_prerun(task_id: str = "", **_kwargs: Any) -> None:
    _task_start_times[str(task_id)] = time.monotonic()


def _on_task_postrun(
    task_id: str = "",
    task: Any = None,
    state: str = "",
    **_kwargs: Any,
) -> None:
    # Metrics collection must never raise into the task execution path.
    try:
        tid = str(task_id)
        started = _task_start_times.pop(tid, None)
        duration_ms = 0.0
        if started is not None:
            duration_ms = max(0.0, (time.monotonic() - started) * 1000.0)

        request = getattr(task, "request", None)
        retries = int(getattr(request, "retries", 0) or 0)
        delivery = getattr(request, "delivery_info", None)
        queue_name = "celery"
        if isinstance(delivery, dict):
            queue_name = str(delivery.get("routing_key") or "celery")

        writer = _resolve_writer()
        record_celery_task_metric(
            task_id=tid,
            task_name=getattr(task, "name", "unknown"),
            state=state,
            duration_ms=duration_ms,
            retries=retries,
            queue_name=queue_name,
            writer=writer,
        )
    except Exception:
        pass


def register_celery_metrics_signals() -> None:
    """Connect Celery task lifecycle signals to the metrics producer."""
    from celery.signals import task_postrun, task_prerun

    task_prerun.connect(_on_task_prerun, weak=False)
    task_postrun.connect(_on_task_postrun, weak=False)
