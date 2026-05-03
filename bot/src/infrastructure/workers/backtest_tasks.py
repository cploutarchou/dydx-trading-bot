"""Celery tasks for durable backtest execution."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timezone
from typing import Any, Dict

from celery.exceptions import SoftTimeLimitExceeded

from src.infrastructure.database import db
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.use_cases.service_backtest import BacktestService
from src.infrastructure.workers.celery_app import celery_app
from src.infrastructure.workers.celery_monitor import build_progress_meta, failure_meta

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


def _selected_pairs(data: Dict[str, Any]) -> list[str]:
    request = data.get("request") if isinstance(data.get("request"), dict) else {}
    raw = data.get("selected_pairs") or request.get("selected_pairs") or request.get("pairs") or []
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return []


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
        task_id = str(self.request.id or run_id)
        request_payload = data.get("request") if isinstance(data.get("request"), dict) else {}
        selected_pairs = _selected_pairs(data)
        self.update_state(
            state="STARTED",
            meta={
                "task_id": task_id,
                "task_name": "backtests.run",
                "queue": getattr(self.request, "delivery_info", {}).get("routing_key", "celery"),
                "status": "STARTED",
                "started_at": _now_iso(),
                "worker_hostname": socket.gethostname(),
                "backtest_run_id": run_id,
                "strategy_id": data.get("strategy_id") or request_payload.get("strategy_id"),
                "bot_id": data.get("bot_id") or request_payload.get("bot_id"),
                "environment": data.get("environment")
                or request_payload.get("environment")
                or os.getenv("ENVIRONMENT")
                or os.getenv("APP_ENV")
                or "local",
                "selected_pairs": selected_pairs,
                "retry_count": int(getattr(self.request, "retries", 0) or 0),
            },
        )
        data["worker_backend"] = "celery"
        data["worker_task_id"] = task_id
        service._set_runtime_control(
            data,
            status="started",
            action="start",
            pause_requested=False,
            resume_requested=False,
            cancel_requested=False,
            worker_backend="celery",
            worker_task_id=task_id,
            started_at=_now_iso(),
        )
        repository.save_run(data)

        async def _progress_callback(
            callback_run_id: str, progress: float, current_pair: str, eta: float
        ) -> None:
            completed_pairs = None
            total_pairs = len(selected_pairs) if selected_pairs else None
            if total_pairs:
                completed_pairs = min(total_pairs, int((float(progress) / 100.0) * total_pairs))
            self.update_state(
                state="PROGRESS",
                meta=build_progress_meta(
                    run_id=callback_run_id,
                    progress_percent=progress,
                    current_pair=current_pair,
                    current_step="processing pair" if current_pair != "complete" else "complete",
                    total_pairs=total_pairs,
                    completed_pairs=completed_pairs,
                    current_phase="backtest",
                    eta_seconds=eta,
                    strategy_id=data.get("strategy_id") or request_payload.get("strategy_id"),
                    bot_id=data.get("bot_id") or request_payload.get("bot_id"),
                    environment=data.get("environment")
                    or request_payload.get("environment")
                    or os.getenv("ENVIRONMENT")
                    or os.getenv("APP_ENV")
                    or "local",
                    selected_pairs=selected_pairs,
                ),
            )

        asyncio.run(service.execute_existing_backtest(run_id, _progress_callback))
        return {"run_id": run_id, "status": "completed"}
    except SoftTimeLimitExceeded:
        message = "Backtest Celery task exceeded soft time limit"
        _mark_worker_failure(run_id, message)
        self.update_state(state="FAILURE", meta=failure_meta(SoftTimeLimitExceeded(message), str(self.request.id or run_id), run_id))
        raise
    except Exception as exc:
        logger.exception("Celery backtest task failed for %s", run_id)
        _mark_worker_failure(run_id, str(exc) or "Backtest Celery task failed")
        self.update_state(state="FAILURE", meta=failure_meta(exc, str(self.request.id or run_id), run_id))
        raise
    finally:
        session.close()
