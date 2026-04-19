"""Celery tasks for durable backtest execution."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from celery.exceptions import SoftTimeLimitExceeded

from src.infrastructure.database import db
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.use_cases.service_backtest import BacktestService
from src.infrastructure.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mark_worker_failure(run_id: str, message: str) -> None:
    session = db.get_session()
    try:
        repository = BacktestRepository(session)
        data = repository.get_run(run_id)
        if not data:
            return
        data.update(
            {
                "status": "failed",
                "current_task": "failed",
                "error": message,
                "error_message": message,
                "finished_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        service = BacktestService(repository)
        service._set_runtime_control(
            data,
            status="failed",
            action="fail",
            pause_requested=False,
            resume_requested=False,
            cancel_requested=False,
            worker_backend="celery",
            worker_task_id=run_id,
        )
        repository.save_run(data)
    finally:
        session.close()


@celery_app.task(
    name="backtests.run",
    bind=True,
    autoretry_for=(),
)
def run_backtest_task(self: Any, run_id: str) -> Dict[str, Any]:
    """Run a persisted backtest by id inside a Celery worker process."""
    session = db.get_session()
    try:
        repository = BacktestRepository(session)
        data = repository.get_run(run_id)
        if not data:
            raise ValueError(f"Backtest run '{run_id}' not found")

        service = BacktestService(repository)
        data["worker_backend"] = "celery"
        data["worker_task_id"] = str(self.request.id or run_id)
        service._set_runtime_control(
            data,
            status="started",
            action="start",
            pause_requested=False,
            resume_requested=False,
            cancel_requested=False,
            worker_backend="celery",
            worker_task_id=str(self.request.id or run_id),
            started_at=_now_iso(),
        )
        repository.save_run(data)

        asyncio.run(service.execute_existing_backtest(run_id))
        return {"run_id": run_id, "status": "completed"}
    except SoftTimeLimitExceeded:
        message = "Backtest Celery task exceeded soft time limit"
        _mark_worker_failure(run_id, message)
        raise
    except Exception as exc:
        logger.exception("Celery backtest task failed for %s", run_id)
        _mark_worker_failure(run_id, str(exc) or "Backtest Celery task failed")
        raise
    finally:
        session.close()

