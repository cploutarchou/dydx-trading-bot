"""Admin-only Celery inspection endpoints.

Extracted from ``src/api/server.py`` (monolith-breakup Phase 2). All routes require
the admin dependency (``get_admin_user``). Auth, middleware, and the global exception
handlers apply automatically because the router is mounted on the canonical app via
``app.include_router``.

Responses use the shared ``api_response`` envelope; timing uses
:mod:`src.api.endpoint_timing`.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from src.api.endpoint_timing import endpoint_perf_headers, log_endpoint_timing
from src.api.responses import api_response
from src.infrastructure.workers.celery_monitor import (
    celery_health,
    get_celery_task,
    list_celery_queues,
    list_celery_tasks,
    list_celery_workers,
    retry_celery_task,
    revoke_celery_task,
)
from src.middleware.auth_middleware import get_admin_user

router = APIRouter(prefix="/api/v1/celery", tags=["Celery (admin)"])


class CeleryTaskRevokeRequest(BaseModel):
    """Validated body for the admin Celery revoke endpoint.

    ``terminate=True`` escalates the revoke to a SIGTERM of the executing task, so
    the flag must be a real boolean — the previous raw-dict ``bool(payload.get(...))``
    coerced JSON strings like ``"false"``/``"0"`` to ``True``. Unknown keys are
    ignored so existing clients sending unrelated fields keep working.
    """

    model_config = ConfigDict(extra="ignore")

    terminate: bool = Field(default=False)


@router.get("/tasks")
async def celery_tasks(
    status: Optional[str] = Query(default=None),
    task_name: Optional[str] = Query(default=None),
    queue: Optional[str] = Query(default=None),
    strategy_id: Optional[str] = Query(default=None),
    backtest_run_id: Optional[str] = Query(default=None),
    bot_id: Optional[str] = Query(default=None),
    environment: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current_user=Depends(get_admin_user),
):
    """Admin-only Celery task list with safe metadata redaction."""
    _ = current_user
    started_at = time.perf_counter()
    payload = list_celery_tasks(
        {
            "status": status,
            "task_name": task_name,
            "queue": queue,
            "strategy_id": strategy_id,
            "backtest_run_id": backtest_run_id,
            "bot_id": bot_id,
            "environment": environment,
        },
        limit,
    )
    task_count = (
        len(payload.get("tasks", []))
        if isinstance(payload, dict) and isinstance(payload.get("tasks"), list)
        else None
    )
    log_endpoint_timing(
        "/api/v1/celery/tasks",
        started_at,
        payload,
        payload_items=task_count,
        extra={"limit": limit},
    )
    return api_response(
        True,
        payload,
        "Celery tasks fetched successfully",
        headers=endpoint_perf_headers(started_at),
    )


@router.get("/tasks/{task_id}")
async def celery_task_detail(
    task_id: str,
    current_user=Depends(get_admin_user),
):
    """Admin-only Celery task detail including failure traceback when available."""
    _ = current_user
    started_at = time.perf_counter()
    task = get_celery_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Celery task not found")
    log_endpoint_timing(
        "/api/v1/celery/tasks/{task_id}",
        started_at,
        {"task": task},
        payload_items=1,
    )
    return api_response(
        True,
        {"task": task},
        "Celery task fetched successfully",
        headers=endpoint_perf_headers(started_at),
    )


@router.post("/tasks/{task_id}/revoke")
async def celery_task_revoke(
    task_id: str,
    # Optional so clients that POST with no body at all keep the graceful-revoke
    # default (the previous Body(default_factory=dict) contract).
    payload: Optional[CeleryTaskRevokeRequest] = None,
    current_user=Depends(get_admin_user),
):
    """Admin-only Celery revoke/cancel endpoint."""
    _ = current_user
    terminate = payload.terminate if payload is not None else False
    return api_response(
        True,
        revoke_celery_task(task_id, terminate=terminate),
        "Celery task revoke requested",
    )


@router.post("/tasks/{task_id}/retry")
async def celery_task_retry(
    task_id: str,
    current_user=Depends(get_admin_user),
):
    """Admin-only retry for supported failed tasks."""
    _ = current_user
    try:
        result = await retry_celery_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return api_response(True, result, "Celery task retry requested")


@router.get("/workers")
async def celery_workers(current_user=Depends(get_admin_user)):
    """Admin-only Celery worker inspection."""
    _ = current_user
    started_at = time.perf_counter()
    payload = list_celery_workers()
    worker_count = len(payload) if isinstance(payload, dict) else None
    log_endpoint_timing(
        "/api/v1/celery/workers",
        started_at,
        payload,
        payload_items=worker_count,
    )
    return api_response(
        True,
        payload,
        "Celery workers fetched successfully",
        headers=endpoint_perf_headers(started_at),
    )


@router.get("/queues")
async def celery_queues(current_user=Depends(get_admin_user)):
    """Admin-only Celery queue overview."""
    _ = current_user
    started_at = time.perf_counter()
    payload = list_celery_queues()
    queue_count = len(payload) if isinstance(payload, dict) else None
    log_endpoint_timing(
        "/api/v1/celery/queues",
        started_at,
        payload,
        payload_items=queue_count,
    )
    return api_response(
        True,
        payload,
        "Celery queues fetched successfully",
        headers=endpoint_perf_headers(started_at),
    )


@router.get("/health")
async def celery_monitor_health(current_user=Depends(get_admin_user)):
    """Admin-only Celery broker/backend/worker health."""
    _ = current_user
    started_at = time.perf_counter()
    payload = celery_health()
    log_endpoint_timing(
        "/api/v1/celery/health",
        started_at,
        payload,
        payload_items=1,
    )
    return api_response(
        True,
        payload,
        "Celery health fetched successfully",
        headers=endpoint_perf_headers(started_at),
    )
