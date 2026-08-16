"""Database-backed bot history, job, trade, and statistics API routes.

All four handlers offload their synchronous SQLAlchemy work (queries + ORM
serialization) to a worker thread via ``run_db``; the offloaded closures own
their full ``Session`` lifecycle and return plain dicts (see
``src/infrastructure/db_offload.py`` for the seam contract).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from loguru import logger

from src.api.responses import api_response
from src.infrastructure.database import db
from src.infrastructure.db_offload import run_db
from src.infrastructure.domain.models.auth_models import User
from src.infrastructure.persistence.repository import UnitOfWork
from src.middleware.auth_middleware import get_current_active_user

router = APIRouter()


def _pair_notional(price1: Any, size1: Any, price2: Any, size2: Any) -> Optional[float]:
    """Sum both legs' |price × size|; None when any leg is missing."""
    if price1 is None or size1 is None or price2 is None or size2 is None:
        return None
    return float(price1) * float(size1) + float(price2) * float(size2)


def _trade_duration_seconds(created_at: Any, closed_at: Any) -> Optional[float]:
    """Seconds between creation and close; None while open or timestamps missing."""
    if created_at is None or closed_at is None:
        return None
    try:
        return (closed_at - created_at).total_seconds()
    except TypeError:
        return None


@router.get("/api/v1/bots/{instance_id}/history")
async def get_bot_history(
    instance_id: str,
    days: int = 7,
    current_user: User = Depends(get_current_active_user),
):
    """Get bot event history"""

    def _load_history() -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            bot = uow.bots.get_by_instance_id(instance_id)
            if not bot:
                return None
            events = uow.events.get_bot_events(int(bot.id), days=days)  # type: ignore[arg-type]
            return {
                "instance_id": instance_id,
                "total_events": len(events),
                "days_requested": days,
                "events": [
                    {
                        "timestamp": event.created_at.isoformat(),
                        "event_type": event.event_type,
                        "severity": event.severity,
                        "message": event.message,
                        "details": event.details,
                    }
                    for event in events
                ],
            }
        finally:
            session.close()

    try:
        data = await run_db(_load_history)
        if data is None:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )
        return api_response(
            success=True,
            data=data,
            message=f"Retrieved {data['total_events']} events for bot '{instance_id}'",
        )

    except Exception as exc:
        logger.error(f"Error getting bot history for {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.get("/api/v1/bots/{instance_id}/jobs")
async def get_bot_jobs(
    instance_id: str,
    days: int = 7,
    current_user: User = Depends(get_current_active_user),
):
    """Get bot job history"""

    def _load_jobs() -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            bot = uow.bots.get_by_instance_id(instance_id)
            if not bot:
                return None
            jobs = uow.jobs.get_job_history(int(bot.id), days=days)  # type: ignore[arg-type]

            def _job_status_value(job) -> str:
                return str(getattr(job.status, "value", job.status)).lower()

            completed_jobs = len(
                [j for j in jobs if _job_status_value(j) == "completed"]
            )
            failed_jobs = len([j for j in jobs if _job_status_value(j) == "failed"])
            cancelled_jobs = len(
                [j for j in jobs if _job_status_value(j) == "cancelled"]
            )
            pending_jobs = len([j for j in jobs if _job_status_value(j) == "pending"])
            running_jobs = len([j for j in jobs if _job_status_value(j) == "running"])

            return {
                "instance_id": instance_id,
                "statistics": {
                    "total_jobs": len(jobs),
                    "completed": completed_jobs,
                    "failed": failed_jobs,
                    "cancelled": cancelled_jobs,
                    "pending": pending_jobs,
                    "running": running_jobs,
                },
                "jobs": [
                    {
                        "job_id": job.job_id,
                        "job_type": job.job_type,
                        "status": _job_status_value(job),
                        "progress_pct": float(getattr(job, "progress_pct", 0.0) or 0.0),
                        "process_id": getattr(job, "process_id", None),
                        "execution_time_ms": getattr(job, "execution_time_ms", None),
                        "retry_count": f"{job.retry_count}/{job.max_retries}",
                        "created_at": job.created_at.isoformat(),
                        "updated_at": (
                            job.updated_at.isoformat()
                            if getattr(job, "updated_at", None)
                            else None
                        ),
                        "started_at": (
                            job.started_at.isoformat()
                            if job.started_at is not None
                            else None
                        ),
                        "completed_at": (
                            job.completed_at.isoformat()
                            if job.completed_at is not None
                            else None
                        ),
                        "error_message": job.error_message,
                        "cancellation_reason": getattr(
                            job, "cancellation_reason", None
                        ),
                        "metadata": dict(getattr(job, "metadata_json", None) or {}),
                    }
                    for job in jobs
                ],
            }
        finally:
            session.close()

    try:
        data = await run_db(_load_jobs)
        if data is None:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )
        return api_response(
            success=True,
            data=data,
            message=f"Retrieved {data['statistics']['total_jobs']} jobs for bot '{instance_id}'",
        )

    except Exception as exc:
        logger.error(f"Error getting bot jobs for {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.get("/api/v1/bots/{instance_id}/trades")
async def get_bot_trades(
    instance_id: str,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    """Get bot trades"""

    def _load_trades() -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            bot = uow.bots.get_by_instance_id(instance_id)
            if not bot:
                return None
            trades = uow.trades.get_bot_trades(int(bot.id))  # type: ignore[arg-type]

            # Filter by status if requested
            if status:
                trades = [
                    trade for trade in trades if str(trade.status) == status.upper()
                ]

            return {
                "instance_id": instance_id,
                "total_trades": len(trades),
                "filter_status": status,
                "trades": [
                    {
                        "trade_id": trade.trade_id,
                        "pair1": trade.pair1,
                        "pair2": trade.pair2,
                        "status": trade.status,
                        "entry_price1": (
                            float(trade.entry_price1)  # type: ignore[arg-type]
                            if trade.entry_price1 is not None
                            else None
                        ),
                        "entry_price2": (
                            float(trade.entry_price2)  # type: ignore[arg-type]
                            if trade.entry_price2 is not None
                            else None
                        ),
                        "exit_price1": (
                            float(trade.exit_price1)
                            if trade.exit_price1 is not None
                            else None
                        ),
                        # type: ignore[arg-type]
                        "exit_price2": (
                            float(trade.exit_price2)
                            if trade.exit_price2 is not None
                            else None
                        ),
                        # Derived from real columns (the Trade model has no
                        # entry_cost/exit_proceeds columns).
                        "entry_cost": _pair_notional(
                            trade.entry_price1,
                            trade.entry_size1,
                            trade.entry_price2,
                            trade.entry_size2,
                        ),
                        "exit_proceeds": _pair_notional(
                            trade.exit_price1,
                            trade.exit_size1,
                            trade.exit_price2,
                            trade.exit_size2,
                        ),
                        "profit_loss": (
                            float(trade.profit_loss)
                            if trade.profit_loss is not None
                            else None
                        ),
                        # type: ignore[arg-type]
                        "profit_loss_percentage": (
                            float(trade.profit_loss_percentage)
                            if trade.profit_loss_percentage is not None
                            else None
                        ),
                        "opened_at": (
                            trade.created_at.isoformat()
                            if trade.created_at is not None
                            else None
                        ),
                        "closed_at": (
                            trade.closed_at.isoformat()
                            if trade.closed_at is not None
                            else None
                        ),
                        "duration_seconds": _trade_duration_seconds(
                            trade.created_at, trade.closed_at
                        ),
                    }
                    for trade in trades
                ],
            }
        finally:
            session.close()

    try:
        data = await run_db(_load_trades)
        if data is None:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )
        return api_response(
            success=True,
            data=data,
            message=f"Retrieved {data['total_trades']} trades for bot '{instance_id}'",
        )

    except Exception as exc:
        logger.error(f"Error getting bot trades for {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.get("/api/v1/bots/{instance_id}/stats")
async def get_bot_stats(
    instance_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get bot statistics"""

    def _load_stats() -> Optional[Dict[str, Any]]:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            bot = uow.bots.get_by_instance_id(instance_id)
            if not bot:
                return None
            bot_stats = uow.bots.get_statistics(instance_id)
            trade_stats = uow.trades.get_trade_statistics(int(bot.id))  # type: ignore[arg-type]
            return {
                "instance_id": instance_id,
                "bot_statistics": {
                    "total_trades": bot_stats.get("total_trades", 0),
                    "successful_trades": bot_stats.get("successful_trades", 0),
                    "failed_trades": bot_stats.get("failed_trades", 0),
                    "total_profit_loss": float(bot_stats.get("total_profit_loss", 0)),
                    "win_rate": float(bot_stats.get("win_rate", 0)),
                    "uptime_seconds": (
                        bot.uptime_seconds if hasattr(bot, "uptime_seconds") else None
                    ),
                },
                "trade_statistics": {
                    "total_trades": trade_stats.get("total_trades", 0),
                    "winning_trades": trade_stats.get("winning_trades", 0),
                    "losing_trades": trade_stats.get("losing_trades", 0),
                    "total_profit": float(trade_stats.get("total_profit", 0)),
                    "total_loss": float(trade_stats.get("total_loss", 0)),
                    "net_profit": float(trade_stats.get("net_profit", 0)),
                    "average_profit": float(trade_stats.get("average_profit", 0)),
                    "win_rate": float(trade_stats.get("win_rate", 0)),
                    "average_duration_seconds": trade_stats.get(
                        "average_duration_seconds", 0
                    ),
                },
            }
        finally:
            session.close()

    try:
        data = await run_db(_load_stats)
        if data is None:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )
        return api_response(
            success=True,
            data=data,
            message=f"Retrieved statistics for bot '{instance_id}'",
        )

    except Exception as exc:
        logger.error(f"Error getting bot statistics for {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


__all__ = [
    "get_bot_history",
    "get_bot_jobs",
    "get_bot_stats",
    "get_bot_trades",
    "router",
]
