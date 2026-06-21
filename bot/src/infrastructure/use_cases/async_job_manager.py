"""Supervised asyncio task helpers with durable job-state persistence."""

from __future__ import annotations

import asyncio
import os
import threading
import time
import traceback
from collections import deque
from typing import Any, Awaitable, Callable, Coroutine, Optional, cast
from uuid import uuid4

from loguru import logger
from src.infrastructure.database import db
from src.infrastructure.persistence.repository import UnitOfWork


class AsyncJobManager:
    """Create and supervise asyncio tasks without losing task failures."""

    def __init__(self):
        self.tasks: dict[str, asyncio.Task[Any]] = {}
        self._persistence_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self._progress_checkpoint: dict[str, tuple[float, float]] = {}
        self._progress_persisted_total = 0
        self._progress_skipped_total = 0
        self._progress_skip_log_every = max(
            0,
            int(os.getenv("JOB_PROGRESS_SKIP_LOG_EVERY", "100") or 100),
        )
        self._progress_min_interval_seconds = max(
            0.0,
            float(os.getenv("JOB_PROGRESS_MIN_INTERVAL_SECONDS", "1.5") or 1.5),
        )
        self._progress_min_delta_pct = max(
            0.0,
            float(os.getenv("JOB_PROGRESS_MIN_DELTA_PCT", "1.0") or 1.0),
        )
        self._pool_overload_events: deque[float] = deque()
        self._pool_overload_window_seconds = max(
            1.0,
            float(os.getenv("JOB_PERSISTENCE_OVERLOAD_WINDOW_SECONDS", "30") or 30),
        )
        self._pool_overload_threshold = max(
            1,
            int(os.getenv("JOB_PERSISTENCE_OVERLOAD_FAILURE_THRESHOLD", "3") or 3),
        )
        self._pool_overload_cooldown_seconds = max(
            1.0,
            float(os.getenv("JOB_PERSISTENCE_OVERLOAD_COOLDOWN_SECONDS", "20") or 20),
        )
        self._persistence_backoff_until = 0.0

    @staticmethod
    def _looks_like_pool_overload(exc: BaseException) -> bool:
        message = str(exc).lower()
        return "queuepool limit" in message or (
            "connection timed out" in message and "sqlalche.me/e/20/3o7r" in message
        )

    def _trim_pool_overload_events_locked(self, now: float) -> None:
        cutoff = now - self._pool_overload_window_seconds
        while self._pool_overload_events and self._pool_overload_events[0] < cutoff:
            self._pool_overload_events.popleft()

    def _record_persistence_failure(self, exc: BaseException) -> None:
        if not self._looks_like_pool_overload(exc):
            return

        with self._metrics_lock:
            now = time.monotonic()
            self._pool_overload_events.append(now)
            self._trim_pool_overload_events_locked(now)
            self._persistence_backoff_until = max(
                self._persistence_backoff_until,
                now + self._pool_overload_cooldown_seconds,
            )

    def _record_persistence_success(self) -> None:
        with self._metrics_lock:
            self._pool_overload_events.clear()
            self._persistence_backoff_until = 0.0

    def _persistence_backoff_remaining_seconds(self) -> float:
        with self._metrics_lock:
            now = time.monotonic()
            remaining = self._persistence_backoff_until - now
            return max(0.0, remaining)

    def _should_skip_persistence_due_to_backoff(self) -> bool:
        return self._persistence_backoff_remaining_seconds() > 0.0

    def get_runtime_metrics(self) -> dict[str, Any]:
        with self._metrics_lock:
            now = time.monotonic()
            self._trim_pool_overload_events_locked(now)
            skipped = int(self._progress_skipped_total)
            persisted = int(self._progress_persisted_total)
            total_updates = skipped + persisted
            skip_ratio = (
                (float(skipped) / float(total_updates)) if total_updates > 0 else 0.0
            )
            recent_pool_events = len(self._pool_overload_events)
            backoff_remaining = max(0.0, self._persistence_backoff_until - now)
            return {
                "progress_updates_persisted": persisted,
                "progress_updates_skipped": skipped,
                "progress_skip_ratio": round(skip_ratio, 4),
                "persistence_pool_overload_events_recent": recent_pool_events,
                "persistence_pool_overloaded": (
                    recent_pool_events >= self._pool_overload_threshold
                ),
                "persistence_pool_overload_window_seconds": self._pool_overload_window_seconds,
                "persistence_pool_overload_threshold": self._pool_overload_threshold,
                "persistence_backoff_active": backoff_remaining > 0.0,
                "persistence_backoff_remaining_seconds": round(backoff_remaining, 3),
                "persistence_backoff_cooldown_seconds": self._pool_overload_cooldown_seconds,
            }

    def _should_persist_progress(self, job_id: str, progress_pct: float) -> bool:
        if progress_pct <= 0.0 or progress_pct >= 100.0:
            return True

        now = time.monotonic()
        previous = self._progress_checkpoint.get(job_id)
        if previous is None:
            return True

        previous_ts, previous_pct = previous
        enough_time_elapsed = (now - previous_ts) >= self._progress_min_interval_seconds
        enough_progress_delta = (
            abs(progress_pct - previous_pct) >= self._progress_min_delta_pct
        )
        return enough_time_elapsed or enough_progress_delta

    def _record_progress_checkpoint(self, job_id: str, progress_pct: float) -> None:
        self._progress_checkpoint[job_id] = (time.monotonic(), progress_pct)

    def _clear_progress_checkpoint(self, job_id: str) -> None:
        self._progress_checkpoint.pop(job_id, None)

    def _resolve_bot_id(
        self, uow: UnitOfWork, bot_instance_id: Optional[str]
    ) -> Optional[int]:
        if not bot_instance_id:
            return None
        bot = uow.bots.get_by_instance_id(bot_instance_id)
        return bot.id if bot is not None else None

    def _with_uow(self, operation: Callable[[UnitOfWork], Any]) -> Any:
        if not self._persistence_configured():
            logger.debug("job_persistence_skipped reason=no_explicit_database_target")
            return None
        if self._should_skip_persistence_due_to_backoff():
            remaining = self._persistence_backoff_remaining_seconds()
            logger.debug(
                "job_persistence_skipped reason=pool_overload_backoff remaining_seconds={}",
                round(remaining, 3),
            )
            return None
        try:
            with self._persistence_lock:
                with db.session_scope() as session:
                    uow = UnitOfWork(session)
                    result = operation(uow)
                    self._record_persistence_success()
                    return result
        except Exception as exc:
            logger.warning("job_persistence_failed error={}", exc)
            self._record_persistence_failure(exc)
            return None

    @staticmethod
    def _persistence_configured() -> bool:
        return any(
            bool(os.getenv(name, "").strip())
            for name in (
                "BOT_DATABASE_URL",
                "DATABASE_URL",
                "BOT_DB_HOST",
                "DB_HOST",
            )
        )

    def create_job(
        self,
        *,
        job_type: str,
        bot_instance_id: Optional[str] = None,
        job_id: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        resolved_job_id = job_id or f"{job_type}-{uuid4().hex[:12]}"

        def _create(uow: UnitOfWork):
            existing = uow.jobs.get_by_job_id(resolved_job_id)
            if existing is not None:
                return existing
            bot_id = self._resolve_bot_id(uow, bot_instance_id)
            return uow.jobs.create_job(
                resolved_job_id,
                bot_id,
                job_type,
                parameters=parameters,
                metadata={
                    **(metadata or {}),
                    "bot_instance_id": bot_instance_id,
                },
            )

        self._with_uow(_create)
        logger.info(
            "job_created job_id={} job_type={} bot_id={}",
            resolved_job_id,
            job_type,
            bot_instance_id,
        )
        return resolved_job_id

    def mark_running(self, job_id: str, *, process_id: Optional[int] = None) -> None:
        self._clear_progress_checkpoint(job_id)
        self._with_uow(lambda uow: uow.jobs.start_job(job_id, process_id=process_id))
        logger.info("job_started job_id={} process_id={}", job_id, process_id)

    def mark_progress(
        self,
        job_id: str,
        progress_pct: float,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        normalized_progress = max(0.0, min(100.0, float(progress_pct or 0.0)))
        if not self._should_persist_progress(job_id, normalized_progress):
            skipped_total = 0
            with self._metrics_lock:
                self._progress_skipped_total += 1
                skipped_total = self._progress_skipped_total
            if (
                self._progress_skip_log_every > 0
                and skipped_total % self._progress_skip_log_every == 0
            ):
                logger.info(
                    "job_progress_throttle_skips total_skipped={} total_persisted={} min_interval_seconds={} min_delta_pct={}",
                    skipped_total,
                    self._progress_persisted_total,
                    self._progress_min_interval_seconds,
                    self._progress_min_delta_pct,
                )
            return

        self._record_progress_checkpoint(job_id, normalized_progress)
        with self._metrics_lock:
            self._progress_persisted_total += 1
        self._with_uow(
            lambda uow: uow.jobs.update_progress(
                job_id,
                normalized_progress,
                metadata=metadata,
            )
        )

    def mark_completed(
        self,
        job_id: str,
        *,
        result: Optional[dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None,
    ) -> None:
        self._clear_progress_checkpoint(job_id)
        self._with_uow(
            lambda uow: uow.jobs.complete_job(
                job_id,
                result=result,
                execution_time_ms=execution_time_ms,
            )
        )
        logger.info("job_completed job_id={}", job_id)

    def mark_failed(
        self,
        job_id: str,
        error: BaseException | str,
        *,
        traceback_summary: Optional[str] = None,
    ) -> None:
        self._clear_progress_checkpoint(job_id)
        message = str(error).strip()
        if not message:
            if isinstance(error, BaseException):
                message = error.__class__.__name__
            else:
                message = "unknown_error"
        self._with_uow(
            lambda uow: uow.jobs.fail_job(
                job_id,
                error_message=message,
                error_traceback=traceback_summary,
            )
        )
        logger.error("job_failed job_id={} error={}", job_id, message)

    def mark_cancelled(self, job_id: str, *, reason: Optional[str] = None) -> None:
        self._clear_progress_checkpoint(job_id)
        self._with_uow(lambda uow: uow.jobs.cancel_job(job_id, reason=reason))
        logger.info("job_cancelled job_id={} reason={}", job_id, reason)

    @staticmethod
    async def _as_coroutine(awaitable: Awaitable[Any]) -> Any:
        """Normalize Awaitable values to a coroutine for asyncio.create_task typing."""
        return await awaitable

    def create_supervised_task(
        self,
        awaitable: Awaitable[Any],
        *,
        job_type: str,
        bot_instance_id: Optional[str] = None,
        job_id: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        auto_complete: bool = True,
    ) -> asyncio.Task[Any]:
        resolved_job_id = self.create_job(
            job_type=job_type,
            bot_instance_id=bot_instance_id,
            job_id=job_id,
            parameters=parameters,
            metadata=metadata,
        )
        self.mark_running(resolved_job_id)
        started = time.perf_counter()
        if isinstance(awaitable, asyncio.Task):
            task = cast(asyncio.Task[Any], awaitable)
            if task.get_name() != resolved_job_id:
                task.set_name(resolved_job_id)
        elif asyncio.iscoroutine(awaitable):
            task = asyncio.create_task(
                awaitable,
                name=resolved_job_id,
            )
        else:
            task = asyncio.create_task(
                self._as_coroutine(awaitable),
                name=resolved_job_id,
            )
        self.tasks[resolved_job_id] = task

        def _done(completed_task: asyncio.Future[Any]) -> None:
            self.tasks.pop(resolved_job_id, None)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if completed_task.cancelled():
                self.mark_cancelled(resolved_job_id, reason="async task cancelled")
                return
            try:
                exc = completed_task.exception()
            except asyncio.CancelledError:
                self.mark_cancelled(resolved_job_id, reason="async task cancelled")
                return
            if exc is not None:
                tb = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )
                self.mark_failed(resolved_job_id, exc, traceback_summary=tb[-4000:])
                return
            if auto_complete:
                self.mark_completed(
                    resolved_job_id,
                    execution_time_ms=elapsed_ms,
                )

        task.add_done_callback(_done)
        return task

    async def cancel_all(self, reason: str = "application shutdown") -> None:
        pending = [
            (job_id, task) for job_id, task in self.tasks.items() if not task.done()
        ]
        for _, task in pending:
            task.cancel()
        for job_id, task in pending:
            try:
                await task
            except asyncio.CancelledError:
                self.mark_cancelled(job_id, reason=reason)


async_job_manager = AsyncJobManager()
