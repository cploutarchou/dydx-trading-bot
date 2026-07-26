"""Worker metrics analytics writer for ClickHouse."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from src.infrastructure.storage.clickhouse_writer import ClickHouseAnalyticsWriter


class WorkerMetricsWriter:
    """Dedicated writer for worker metrics to ClickHouse worker_metrics table.
    
    This writer batches metrics in-memory and flushes them periodically or when
    batch size thresholds are reached. It's designed to be used by Celery workers
    and other background task processors.
    """

    def __init__(
            self,
            analytics_writer: ClickHouseAnalyticsWriter | None = None,
            batch_size: int = 100,
            flush_interval_seconds: float = 5.0,
    ):
        self.analytics_writer = analytics_writer
        self.batch_size = max(1, batch_size)
        self.flush_interval_seconds = max(0.1, flush_interval_seconds)

        self._buffer: list[dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        self._last_flush_time = time.monotonic()

        # Start background flush thread if batching is enabled
        self._stop_event = threading.Event()
        if self._should_run_background_flusher():
            self._flush_thread = threading.Thread(target=self._background_flusher, daemon=True)
            self._flush_thread.start()
        else:
            self._flush_thread = None

    def _should_run_background_flusher(self) -> bool:
        return self.flush_interval_seconds > 0

    def _background_flusher(self) -> None:
        """Background thread that periodically flushes metrics buffer."""
        while not self._stop_event.is_set():
            try:
                self._maybe_flush()
                # Sleep in small increments to allow quick shutdown
                for _ in range(10):
                    if self._stop_event.is_set():
                        break
                    time.sleep(self.flush_interval_seconds / 10.0)
            except Exception:
                # Never let background thread die from exceptions
                pass

    def record_metric(
            self,
            worker_id: str,
            worker_type: str,
            queue_name: str,
            metric_name: str,
            metric_value: float,
            timestamp: datetime | None = None,
    ) -> None:
        """Record a single worker metric.
        
        Args:
            worker_id: Unique identifier for the worker instance
            worker_type: Type of worker (e.g., 'celery', 'backtest', 'market_sync')
            queue_name: Name of the queue the worker is processing
            metric_name: Name of the metric (e.g., 'task_duration_ms', 'tasks_completed')
            metric_value: Numeric value of the metric
            timestamp: When the metric was recorded (defaults to now UTC)
        """
        if self.analytics_writer is None or not self.analytics_writer.enabled:
            return

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        metric_row = {
            "metric_time": timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"),
            "worker_id": worker_id,
            "worker_type": worker_type,
            "queue_name": queue_name,
            "metric_name": metric_name,
            "metric_value": metric_value,
        }

        with self._buffer_lock:
            self._buffer.append(metric_row)
            if len(self._buffer) >= self.batch_size:
                self._flush_buffer()

    def record_task_metrics(
            self,
            worker_id: str,
            worker_type: str,
            queue_name: str,
            task_id: str,
            task_name: str,
            duration_ms: float,
            success: bool,
            retry_count: int = 0,
            timestamp: datetime | None = None,
    ) -> None:
        """Record a comprehensive set of metrics for a completed task.
        
        Args:
            worker_id: Unique identifier for the worker instance
            worker_type: Type of worker
            queue_name: Name of the queue
            task_id: Unique identifier for the task
            task_name: Name/type of the task
            duration_ms: How long the task took to complete (milliseconds)
            success: Whether the task completed successfully
            retry_count: How many times the task was retried
            timestamp: When the task completed (defaults to now UTC)
        """
        if self.analytics_writer is None or not self.analytics_writer.enabled:
            return

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Record individual metrics for the task
        base_metrics = [
            ("task_duration_ms", duration_ms),
            ("task_success", 1.0 if success else 0.0),
            ("task_failure", 0.0 if success else 1.0),
            ("task_retry_count", float(retry_count)),
        ]

        for metric_name, metric_value in base_metrics:
            self.record_metric(
                worker_id=worker_id,
                worker_type=worker_type,
                queue_name=queue_name,
                metric_name=f"{task_name}.{metric_name}",
                metric_value=metric_value,
                timestamp=timestamp,
            )

        # Also record overall worker throughput metrics
        self.record_metric(
            worker_id=worker_id,
            worker_type=worker_type,
            queue_name=queue_name,
            metric_name="tasks_completed",
            metric_value=1.0,
            timestamp=timestamp,
        )

        if success:
            self.record_metric(
                worker_id=worker_id,
                worker_type=worker_type,
                queue_name=queue_name,
                metric_name="tasks_succeeded",
                metric_value=1.0,
                timestamp=timestamp,
            )
        else:
            self.record_metric(
                worker_id=worker_id,
                worker_type=worker_type,
                queue_name=queue_name,
                metric_name="tasks_failed",
                metric_value=1.0,
                timestamp=timestamp,
            )

    def record_heartbeat(
            self,
            worker_id: str,
            worker_type: str,
            queue_name: str,
            heartbeat_age_seconds: float | None = None,
            timestamp: datetime | None = None,
    ) -> None:
        """Record a worker heartbeat metric.
        
        Args:
            worker_id: Unique identifier for the worker instance
            worker_type: Type of worker
            queue_name: Name of the queue the worker is processing
            heartbeat_age_seconds: Age of the heartbeat in seconds (if None, calculated from timestamp)
            timestamp: When the heartbeat was recorded (defaults to now UTC)
        """
        if self.analytics_writer is None or not self.analytics_writer.enabled:
            return

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        if heartbeat_age_seconds is None:
            # This would be calculated by the caller
            return

        self.record_metric(
            worker_id=worker_id,
            worker_type=worker_type,
            queue_name=queue_name,
            metric_name="heartbeat_age_seconds",
            metric_value=heartbeat_age_seconds,
            timestamp=timestamp,
        )

    def _flush_buffer(self) -> int:
        """Flush the current buffer to ClickHouse."""
        with self._buffer_lock:
            if not self._buffer:
                return 0

            buffer = self._buffer.copy()
            self._buffer.clear()
            self._last_flush_time = time.monotonic()

        if self.analytics_writer is None or not self.analytics_writer.enabled:
            return 0

        try:
            return self.analytics_writer.write_rows("worker_metrics", buffer)
        except Exception:
            # If write fails, put the buffer back for retry
            with self._buffer_lock:
                self._buffer.extend(buffer)
            return 0

    def _maybe_flush(self) -> int:
        """Flush buffer if flush interval has elapsed."""
        now = time.monotonic()
        if now - self._last_flush_time >= self.flush_interval_seconds:
            return self._flush_buffer()
        return 0

    def flush(self, force: bool = False) -> int:
        """Manually flush the metrics buffer.
        
        Args:
            force: If True, force flush even if buffer is empty or interval hasn't elapsed
            
        Returns:
            Number of metrics flushed
        """
        if force:
            return self._flush_buffer()
        return self._maybe_flush()

    def close(self) -> None:
        """Clean up resources, flushing any pending metrics."""
        if self._stop_event:
            self._stop_event.set()
        if self._flush_thread:
            self._flush_thread.join(timeout=10.0)
        self.flush(force=True)


# Global worker metrics writer instance - initialized by application
_worker_metrics_writer: WorkerMetricsWriter | None = None


def get_worker_metrics_writer() -> WorkerMetricsWriter | None:
    """Get the global worker metrics writer instance."""
    return _worker_metrics_writer


def init_worker_metrics_writer(analytics_writer: ClickHouseAnalyticsWriter | None = None) -> WorkerMetricsWriter:
    """Initialize the global worker metrics writer instance.
    
    Args:
        analytics_writer: The ClickHouse analytics writer to use
        
    Returns:
        The initialized worker metrics writer
    """
    global _worker_metrics_writer
    if _worker_metrics_writer is None:
        _worker_metrics_writer = WorkerMetricsWriter(analytics_writer)
    return _worker_metrics_writer
