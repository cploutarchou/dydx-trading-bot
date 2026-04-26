"""Supervised asyncio task helpers with durable job-state persistence."""

from __future__ import annotations

import asyncio
import os
import time
import traceback
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

from loguru import logger

from internal.domain.models import JobStatusEnum
from src.infrastructure.database import db
from src.infrastructure.persistence.repository import UnitOfWork


class AsyncJobManager:
    """Create and supervise asyncio tasks without losing task failures."""

    def __init__(self):
        self.tasks: dict[str, asyncio.Task] = {}

    def _resolve_bot_id(self, uow: UnitOfWork, bot_instance_id: Optional[str]) -> Optional[int]:
        if not bot_instance_id:
            return None
        bot = uow.bots.get_by_instance_id(bot_instance_id)
        return bot.id if bot is not None else None

    def _with_uow(self, operation: Callable[[UnitOfWork], Any]) -> Any:
        if not self._persistence_configured():
            logger.debug("job_persistence_skipped reason=no_explicit_database_target")
            return None
        session = None
        try:
            session = db.get_session()
            uow = UnitOfWork(session)
            return operation(uow)
        except Exception as exc:
            logger.warning("job_persistence_failed error={}", exc)
            if session is not None:
                session.rollback()
            return None
        finally:
            if session is not None:
                session.close()

    @staticmethod
    def _persistence_configured() -> bool:
        return any(
            bool(os.getenv(name, "").strip())
            for name in (
                "BOT_DATABASE_URL",
                "DATABASE_URL",
                "BOT_DB_HOST",
                "DB_HOST",
                "POSTGRES_HOST",
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
        self._with_uow(lambda uow: uow.jobs.start_job(job_id, process_id=process_id))
        logger.info("job_started job_id={} process_id={}", job_id, process_id)

    def mark_progress(
            self,
            job_id: str,
            progress_pct: float,
            *,
            metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self._with_uow(
            lambda uow: uow.jobs.update_progress(
                job_id,
                progress_pct,
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
        message = str(error)
        self._with_uow(
            lambda uow: uow.jobs.fail_job(
                job_id,
                error_message=message,
                error_traceback=traceback_summary,
            )
        )
        logger.error("job_failed job_id={} error={}", job_id, message)

    def mark_cancelled(self, job_id: str, *, reason: Optional[str] = None) -> None:
        self._with_uow(lambda uow: uow.jobs.cancel_job(job_id, reason=reason))
        logger.info("job_cancelled job_id={} reason={}", job_id, reason)

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
    ) -> asyncio.Task:
        resolved_job_id = self.create_job(
            job_type=job_type,
            bot_instance_id=bot_instance_id,
            job_id=job_id,
            parameters=parameters,
            metadata=metadata,
        )
        self.mark_running(resolved_job_id)
        started = time.perf_counter()
        task = asyncio.create_task(awaitable, name=resolved_job_id)
        self.tasks[resolved_job_id] = task

        def _done(completed_task: asyncio.Task) -> None:
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
                tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
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
        pending = [(job_id, task) for job_id, task in self.tasks.items() if not task.done()]
        for _, task in pending:
            task.cancel()
        for job_id, task in pending:
            try:
                await task
            except asyncio.CancelledError:
                self.mark_cancelled(job_id, reason=reason)


async_job_manager = AsyncJobManager()
