"""Operational monitoring endpoints (DataFrame + database connection pool).

Extracted from ``src/api/server.py`` as the first ``APIRouter``-based route module
(see the monolith-breakup effort). These are low-criticality visibility endpoints —
they report on memory/pool health and do not participate in trading. Auth, middleware,
and the global exception handlers apply automatically because the router is mounted on
the canonical app via ``app.include_router``.

Responses use the shared ``api_response`` envelope from :mod:`src.api.responses`.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.responses import api_response
from src.infrastructure.database import db
from src.middleware.auth_middleware import get_current_active_user
from src.shared.time_utils import utc_now_iso

router = APIRouter(prefix="/api/v1/monitoring", tags=["Monitoring"])


class WsBroadcastPublishRequest(BaseModel):
    """Diagnostic broadcast request for the cross-worker WS bus smoke test."""

    channel: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9._-]+$",
        description=(
            "Target broadcast channel (a bot instance id, 'backtest-<run_id>', "
            "or 'strategies')."
        ),
    )


@router.get("/dataframe/memory")
async def get_dataframe_memory_stats(
    current_user=Depends(get_current_active_user),
):
    """Get DataFrame memory usage statistics."""
    _ = current_user
    try:
        from src.shared.dataframe_utils import (
            get_dataframe_cleanup_stats,
            get_memory_summary,
        )

        return api_response(
            success=True,
            data={
                "memory_summary": get_memory_summary(),
                "cleanup_stats": get_dataframe_cleanup_stats(),
            },
            message="DataFrame memory statistics retrieved",
        )
    except Exception as e:
        return api_response(
            success=False,
            data={"error": str(e)},
            message="Failed to retrieve DataFrame memory statistics",
        )


@router.post("/dataframe/cleanup")
async def cleanup_all_dataframes(
    current_user=Depends(get_current_active_user),
):
    """Force cleanup of all tracked DataFrames."""
    _ = current_user
    try:
        from src.shared.dataframe_utils import force_cleanup_all

        cleaned_count = force_cleanup_all()

        return api_response(
            success=True,
            data={"cleaned_dataframes": cleaned_count},
            message=f"Cleaned up {cleaned_count} DataFrames",
        )
    except Exception as e:
        return api_response(
            success=False,
            data={"error": str(e)},
            message="Failed to cleanup DataFrames",
        )


@router.get("/database/pool")
async def get_database_pool_metrics(
    current_user=Depends(get_current_active_user),
):
    """Get current database connection pool metrics."""
    _ = current_user
    metrics = db.get_pool_metrics()
    return api_response(
        success=True,
        data=metrics,
        message="Database pool metrics retrieved",
    )


@router.get("/database/pool/health")
async def get_database_pool_health(
    current_user=Depends(get_current_active_user),
):
    """Get database connection pool health status."""
    _ = current_user
    health = db.get_pool_health_status()
    return api_response(
        success=True,
        data=health,
        message="Database pool health status retrieved",
    )


@router.get("/database/pool/history")
async def get_database_pool_history(
    limit: int = 50,
    current_user=Depends(get_current_active_user),
):
    """Get historical database connection pool metrics."""
    _ = current_user
    safe_limit = max(1, min(int(limit or 50), 500))
    history = db.get_pool_metrics_history(limit=safe_limit)
    return api_response(
        success=True,
        data={"history": history, "count": len(history)},
        message=f"Retrieved {len(history)} database pool metrics samples",
    )


@router.get("/database/diagnostics")
async def get_database_diagnostics(
    current_user=Depends(get_current_active_user),
):
    """Get comprehensive database diagnostics including pool metrics."""
    _ = current_user
    diagnostics = db.get_diagnostics()
    return api_response(
        success=True,
        data=diagnostics,
        message="Database diagnostics retrieved",
    )


@router.get("/circuit-breakers")
async def get_circuit_breaker_states(
    current_user=Depends(get_current_active_user),
):
    """Get live circuit-breaker states for all registered external services.

    Reports the state (closed/open/half-open), failure counters, and thresholds
    for every named breaker (``dydx_indexer``, ``telegram``, ``loki``) in
    ``src/infrastructure/resilience``. Pure in-memory read — no external I/O.
    """
    _ = current_user
    from src.infrastructure import resilience

    states = resilience.breaker_states()
    return api_response(
        success=True,
        data={"breakers": states, "count": len(states)},
        message="Circuit breaker states retrieved",
    )


@router.get("/ws-broadcast")
async def get_ws_broadcast_health(
    current_user=Depends(get_current_active_user),
):
    """Get health of the cross-worker WebSocket broadcast bus.

    Reports whether the Redis pub/sub bus is enabled, its backend (``redis`` /
    ``noop``), reachability (``healthy``), the worker's subscriber identity
    (``worker_id``), and whether the listener task is running (``listening``).
    When the bus is disabled (the default, ``WS_BROADCAST_ENABLED=false``) this
    returns the noop shape. See ``src/infrastructure/broadcast``.
    """
    _ = current_user
    from src.infrastructure.broadcast import get_broadcast_bus

    health = await get_broadcast_bus().health()
    return api_response(
        success=True,
        data=health,
        message="WebSocket broadcast bus health retrieved",
    )


@router.post("/ws-broadcast/publish")
async def publish_ws_broadcast_test(
    request: WsBroadcastPublishRequest,
    current_user=Depends(get_current_active_user),
):
    """Publish a diagnostic broadcast to a channel via ``broadcast_to_bot``.

    Operator smoke test for the cross-worker bus: emits a fixed, server-built
    ``broadcast_test`` message (callers cannot inject arbitrary payloads) through
    the same path the runtime uses — local delivery on this worker, then a
    best-effort fan-out publish so other workers deliver to their own clients.
    Use it to verify that a client attached to a *different* worker receives the
    message exactly once (``test_id`` correlates the copies) after
    ``WS_BROADCAST_ENABLED=true`` is enabled. Complements the read-only
    ``GET /api/v1/monitoring/ws-broadcast`` health probe.
    """
    _ = current_user
    from src.api.websocket_server import manager as ws_manager
    from src.infrastructure.broadcast import get_broadcast_bus

    test_id = uuid4().hex
    message = {
        "type": "broadcast_test",
        "timestamp": utc_now_iso(),
        "bot_instance_id": request.channel,
        "data": {"test_id": test_id},
    }
    await ws_manager.broadcast_to_bot(request.channel, message)
    bus_health = await get_broadcast_bus().health()
    return api_response(
        success=True,
        data={
            "channel": request.channel,
            "test_id": test_id,
            "bus": bus_health,
        },
        message="Diagnostic broadcast published",
    )
