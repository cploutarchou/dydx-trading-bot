"""NATS worker metrics producer.

Wires the WorkerMetricsWriter (ClickHouse ``worker_metrics`` table) to NATS
worker lifecycle signals so task duration, success/failure, retry count, and
throughput are recorded for every backtest command executed by a NATS worker.

The producer is dormant unless ClickHouse writes are enabled
(``BACKTEST_CLICKHOUSE_WRITES_ENABLED=true``). ``WorkerMetricsWriter.record_*``
no-ops when the underlying analytics writer is disabled, so wiring these signals
never changes task runtime behavior and never blocks task execution.

This extends Phase 1 worker metrics to the NATS worker path for Phase 4.
"""

from __future__ import annotations

import os
import socket
import time
from typing import Any, Optional

# correlation_id -> monotonic start time, populated at command start and consumed at completion.
_command_start_times: dict[str, float] = {}


def _worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-nats"


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
        from src.infrastructure.persistence.repository_backtest import BacktestRepository

        analytics_writer = BacktestRepository._build_analytics_writer()
    except Exception:
        # If the analytics writer cannot be constructed, the producer stays a
        # no-op rather than breaking task execution.
        analytics_writer = None
    return init_worker_metrics_writer(analytics_writer)


def record_nats_command_metric(
        command_id: str,
        correlation_id: str,
        run_id: str,
        state: str,
        duration_ms: float,
        retry_count: int,
        writer: Optional[Any],
) -> None:
    """Record a completed NATS command's metrics via the worker metrics writer.

    Pure with respect to ``writer``: callers pass the writer so this is unit
    testable without NATS or ClickHouse. No-ops when writer is None. Maps the
    command state to success/failure so the worker_metrics read model can
    distinguish completed vs failed work.
    """
    if writer is None:
        return
    writer.record_task_metrics(
        worker_id=_worker_id(),
        worker_type="nats",
        queue_name="backtest-commands",
        task_id=command_id,
        task_name=f"backtest-execution-{run_id}" if run_id else "backtest-execution",
        duration_ms=max(0.0, float(duration_ms)),
        success=(state == "completed"),
        retry_count=max(0, int(retry_count)),
    )


def start_nats_command(correlation_id: str) -> None:
    """Record the start time for a NATS command."""
    if correlation_id:
        _command_start_times[correlation_id] = time.monotonic()


def complete_nats_command(
        correlation_id: str,
        command_id: str,
        run_id: str,
        state: str,
        retry_count: int = 0,
        writer: Optional[Any] = None,
) -> None:
    """Record completion of a NATS command with metrics."""
    start_time = _command_start_times.pop(correlation_id, None)
    if start_time is not None:
        duration_ms = (time.monotonic() - start_time) * 1000
        record_nats_command_metric(
            command_id=command_id,
            correlation_id=correlation_id,
            run_id=run_id,
            state=state,
            duration_ms=duration_ms,
            retry_count=retry_count,
            writer=writer or _resolve_writer(),
        )


def fail_nats_command(
        correlation_id: str,
        command_id: str,
        run_id: str,
        error: str,
        retry_count: int = 0,
        writer: Optional[Any] = None,
) -> None:
    """Record failure of a NATS command with metrics."""
    complete_nats_command(
        correlation_id=correlation_id,
        command_id=command_id,
        run_id=run_id,
        state="failed",
        retry_count=retry_count,
        writer=writer,
    )


def get_nats_worker_metrics_writer() -> Optional[Any]:
    """Return the NATS worker metrics writer (lazy initialization)."""
    return _resolve_writer()
