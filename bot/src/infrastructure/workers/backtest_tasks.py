"""Celery tasks for durable backtest execution."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import traceback as traceback_module
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


def _mark_worker_failure(
    run_id: str,
    message: str,
    *,
    error_code: str | None = None,
    traceback_text: str | None = None,
    worker_hostname: str | None = None,
    retry_count: int | None = None,
) -> None:
    session = db.get_session()
    try:
        repository = BacktestRepository(session)
        data = repository.get_run(run_id)
        if not data:
            return
        request_payload = (
            data.get("request") if isinstance(data.get("request"), dict) else {}
        )
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
        task_context = service._build_task_context(
            request_payload,
            worker_hostname=worker_hostname or socket.gethostname(),
            retry_count=retry_count,
        )
        data["request"] = service._set_task_failure(
            service._set_task_context(request_payload, task_context),
            {
                "error_code": error_code
                or service._error_code_from_message(
                    message, "BACKTEST_EXECUTION_FAILED"
                ),
                "error_message": message,
                "traceback": traceback_text,
            },
        )
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
    raw = (
        data.get("selected_pairs")
        or request.get("selected_pairs")
        or request.get("pairs")
        or []
    )
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return []


@celery_app.task(
    name="backtests.run",
    bind=True,
    autoretry_for=(),
)
def run_backtest_task(
    self: Any,
    run_id: str,
    task_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run a persisted backtest by id inside a Celery worker process."""
    session = db.get_session()
    try:
        repository = BacktestRepository(session)
        data = repository.get_run(run_id)
        if not data:
            raise ValueError(f"Backtest run '{run_id}' not found")

        service = BacktestService(repository)
        task_id = str(self.request.id or run_id)
        request_payload = (
            data.get("request") if isinstance(data.get("request"), dict) else {}
        )
        task_context = service._build_task_context(
            request_payload,
            **(task_context or {}),
            worker_hostname=socket.gethostname(),
            retry_count=int(getattr(self.request, "retries", 0) or 0),
        )
        request_payload = service._clear_task_failure(
            service._set_task_context(request_payload, task_context)
        )
        data["request"] = request_payload
        selected_pairs = _selected_pairs(data)
        strategy_snapshot = (
            request_payload.get("strategy_payload_snapshot")
            if isinstance(request_payload.get("strategy_payload_snapshot"), dict)
            else None
        )
        strategy_id = task_context.get("strategy_id") or request_payload.get(
            "strategy_id"
        )
        if strategy_snapshot and strategy_id is None:
            raise ValueError(
                "STRATEGY_ID_MISSING: strategy-linked backtest requires strategy_id"
            )
        if strategy_id is not None and not strategy_snapshot:
            raise ValueError(
                "STRATEGY_PAYLOAD_MISSING: strategy-linked backtest requires strategy_payload_snapshot"
            )
        if not selected_pairs:
            raise ValueError(
                "SELECTED_PAIRS_MISSING: explicit selected_pairs are required"
            )
        self.update_state(
            state="STARTED",
            meta={
                "task_id": task_id,
                "task_name": "backtests.run",
                "queue": getattr(self.request, "delivery_info", {}).get(
                    "routing_key", "celery"
                ),
                "status": "STARTED",
                "started_at": _now_iso(),
                "worker_hostname": socket.gethostname(),
                "backtest_run_id": run_id,
                "strategy_id": strategy_id,
                "bot_id": task_context.get("bot_id") or request_payload.get("bot_id"),
                "environment": task_context.get("environment")
                or request_payload.get("environment")
                or os.getenv("ENVIRONMENT")
                or os.getenv("APP_ENV")
                or "local",
                "selected_pairs": selected_pairs,
                "retry_count": int(getattr(self.request, "retries", 0) or 0),
                "source": task_context.get("source"),
                "metadata": task_context.get("metadata") or {},
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
                completed_pairs = min(
                    total_pairs, int((float(progress) / 100.0) * total_pairs)
                )
            self.update_state(
                state="PROGRESS",
                meta=build_progress_meta(
                    run_id=callback_run_id,
                    progress_percent=progress,
                    current_pair=current_pair,
                    current_step=(
                        "processing pair" if current_pair != "complete" else "complete"
                    ),
                    total_pairs=total_pairs,
                    completed_pairs=completed_pairs,
                    current_phase="backtest",
                    eta_seconds=eta,
                    strategy_id=strategy_id,
                    bot_id=task_context.get("bot_id") or request_payload.get("bot_id"),
                    environment=task_context.get("environment")
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
        _mark_worker_failure(
            run_id,
            message,
            error_code="BACKTEST_TIMEOUT",
            traceback_text=traceback_module.format_exc(),
            worker_hostname=socket.gethostname(),
            retry_count=int(getattr(self.request, "retries", 0) or 0),
        )
        self.update_state(
            state="FAILURE",
            meta=failure_meta(
                SoftTimeLimitExceeded(message),
                str(self.request.id or run_id),
                run_id,
                error_code="BACKTEST_TIMEOUT",
            ),
        )
        raise
    except Exception as exc:
        logger.exception("Celery backtest task failed for %s", run_id)
        _mark_worker_failure(
            run_id,
            str(exc) or "Backtest Celery task failed",
            error_code=BacktestService._error_code_from_message(
                str(exc), "BACKTEST_EXECUTION_FAILED"
            ),
            traceback_text=traceback_module.format_exc(),
            worker_hostname=socket.gethostname(),
            retry_count=int(getattr(self.request, "retries", 0) or 0),
        )
        self.update_state(
            state="FAILURE",
            meta=failure_meta(
                exc,
                str(self.request.id or run_id),
                run_id,
                error_code=BacktestService._error_code_from_message(
                    str(exc), "BACKTEST_EXECUTION_FAILED"
                ),
            ),
        )
        raise
    finally:
        session.close()
