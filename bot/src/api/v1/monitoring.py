"""Operational monitoring endpoints (DataFrame + database connection pool).

Extracted from ``src/api/server.py`` as the first ``APIRouter``-based route module
(see the monolith-breakup effort). These are low-criticality visibility endpoints —
they report on memory/pool health and do not participate in trading. Auth, middleware,
and the global exception handlers apply automatically because the router is mounted on
the canonical app via ``app.include_router``.

Responses use the shared ``api_response`` envelope from :mod:`src.api.responses`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.responses import api_response
from src.infrastructure.database import db
from src.middleware.auth_middleware import get_current_active_user

router = APIRouter(prefix="/api/v1/monitoring", tags=["Monitoring"])


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
