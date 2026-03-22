"""
Bot API Server - FastAPI server for controlling multiple bot instances
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Load .env BEFORE importing project modules that initialize config/database.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Import authentication modules
from src.api.v1.auth import router as auth_router

# Import bot models and manager
from src.infrastructure.domain.bot_api_models import (
    BotCredentials,
    BotInstanceConfig,
    BotInstanceList,
    BotInstanceStatus,
    BotOperationResult,
    BotStatus,
    TradingParameters,
)
from src.infrastructure.domain.models.auth_models import User
from src.middleware.auth_middleware import get_current_active_user

try:
    from src.bot_instance_manager import bot_manager
except Exception as bot_manager_import_error:  # pragma: no cover
    logging.getLogger(__name__).warning(
        "Bot instance manager unavailable at startup: %s",
        bot_manager_import_error,
    )
    bot_manager = None

from src.api.realtime_serializers import (
    serialize_market_core,
    serialize_realtime_position,
    serialize_stats_risk_fields,
)
from src.api.websocket_server import WebSocketServer, manager

# Import database utilities
from src.infrastructure.database import db

# Import backtest modules
from src.infrastructure.domain.models_backtest import (
    BacktestConfigRequest,
    BacktestDetailResponse,
    BacktestListResponse,
    BacktestResponse,
)
from src.infrastructure.persistence.repository import UnitOfWork
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.persistence.repository_realtime import UnitOfWorkRealtime
from src.infrastructure.use_cases.service_backtest import BacktestService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_PAIRS = ["BTC-USD", "ETH-USD", "SOL-USD"]


class StrategyRequest(BaseModel):
    """UI-compatible strategy payload."""

    name: str
    category: str = "custom"
    description: str = ""
    is_public: bool = False
    user_id: int = 1
    resolution: str = "1H"
    zscore_threshold: float = 1.5
    stats_window: int = 21
    max_half_life: int = 24
    usd_per_trade: float = 10.0
    usd_min_collateral: float = 100.0
    close_at_zscore_cross: bool = True
    find_cointegrated_pairs: bool = True
    manage_exits: bool = True
    place_trades: bool = True
    abort_all_positions: bool = False
    max_positions: int = 5
    max_drawdown_pct: float = 15.0
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 8.0
    trailing_stop_pct: float = 2.0
    rebalance_interval_hours: int = 24
    position_timeout_hours: int = 72


class StrategyVersionRevertRequest(BaseModel):
    """Placeholder body for strategy version revert."""


class BacktestRunRequestCompat(BaseModel):
    """Frontend-compatible backtest run request."""

    start_date: str
    end_date: str
    strategy_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    initial_balance: float = 1000.0
    max_pairs: int = 3
    trading_parameters: Optional[Dict[str, Any]] = None
    pairs: Optional[List[str]] = None


class BacktestCreateStrategyRequest(BaseModel):
    """Create a strategy from an existing backtest."""

    name: str
    description: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)


class InMemoryStrategyStore:
    """DB-backed strategy storage with the same interface as the prior in-memory store."""

    @classmethod
    def ensure_seeded(cls) -> None:
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            existing = uow.strategies.list(skip=0, limit=1)
            if existing.get("total", 0) > 0:
                return

            uow.strategies.create(
                {
                    "name": "Balanced Mean Reversion",
                    "category": "balanced",
                    "description": "Default balanced strategy for UI smoke tests.",
                    "is_public": True,
                    "zscore_threshold": 1.5,
                    "stats_window": 21,
                    "usd_per_trade": 10.0,
                },
                note="Seeded default strategy",
            )
            uow.strategies.create(
                {
                    "name": "Aggressive Entry",
                    "category": "aggressive",
                    "description": "More active entry profile for quick comparisons.",
                    "is_public": True,
                    "zscore_threshold": 1.0,
                    "stats_window": 14,
                    "usd_per_trade": 25.0,
                },
                note="Seeded default strategy",
            )
        finally:
            session.close()

    @classmethod
    def list(cls, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
        cls.ensure_seeded()
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.list(skip=skip, limit=limit)
        finally:
            session.close()

    @classmethod
    def list_public(cls) -> Dict[str, Any]:
        cls.ensure_seeded()
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.list_public()
        finally:
            session.close()

    @classmethod
    def get(cls, strategy_id: int) -> Optional[Dict[str, Any]]:
        cls.ensure_seeded()
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.get(strategy_id)
        finally:
            session.close()

    @classmethod
    def create(
        cls,
        payload: Dict[str, Any],
        seed: bool = False,
    ) -> Dict[str, Any]:
        if not seed:
            cls.ensure_seeded()
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            note = "Seeded default strategy" if seed else "Initial version"
            return uow.strategies.create(payload, note=note)
        finally:
            session.close()

    @classmethod
    def update(
        cls,
        strategy_id: int,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        cls.ensure_seeded()
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.update(strategy_id, payload, note="Updated strategy")
        finally:
            session.close()

    @classmethod
    def delete(cls, strategy_id: int) -> bool:
        cls.ensure_seeded()
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.delete(strategy_id)
        finally:
            session.close()

    @classmethod
    def versions(cls, strategy_id: int) -> List[Dict[str, Any]]:
        cls.ensure_seeded()
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.versions(strategy_id)
        finally:
            session.close()

    @classmethod
    def revert(
        cls,
        strategy_id: int,
        version_id: int,
    ) -> Optional[Dict[str, Any]]:
        cls.ensure_seeded()
        session = db.get_session()
        try:
            uow = UnitOfWork(session)
            return uow.strategies.revert(strategy_id, version_id)
        finally:
            session.close()


def _bot_manager_ready() -> bool:
    return bot_manager is not None


def _bot_manager_unavailable_response() -> JSONResponse:
    return api_response(
        success=False,
        message="Bot manager unavailable in this environment",
        status_code=503,
    )


def _strategy_to_backtest_request(
    strategy: Dict[str, Any],
    request: BacktestRunRequestCompat,
) -> BacktestConfigRequest:
    pairs = request.pairs or DEFAULT_PAIRS[: max(1, request.max_pairs)]
    trading_parameters = dict(request.trading_parameters or {})
    if not trading_parameters:
        trading_parameters = {
            "zscore_threshold": strategy["zscore_threshold"],
            "stats_window": strategy["stats_window"],
            "max_half_life": strategy["max_half_life"],
            "usd_per_trade": strategy["usd_per_trade"],
            "close_at_zscore_cross": strategy["close_at_zscore_cross"],
            "max_positions": strategy["max_positions"],
            "max_drawdown_pct": strategy["max_drawdown_pct"],
            "stop_loss_pct": strategy["stop_loss_pct"],
            "take_profit_pct": strategy["take_profit_pct"],
            "trailing_stop_pct": strategy["trailing_stop_pct"],
            "transaction_fee": strategy.get("transaction_fee", 0.0005),
            "slippage": strategy.get("slippage", 0.001),
            "risk_free_rate": strategy.get("risk_free_rate", 0.02),
            "resolution": strategy.get(
                "resolution",
                strategy.get("candle_resolution", "1HOUR"),
            ),
        }

    return BacktestConfigRequest(
        name=request.name or f"{strategy['name']} Backtest",
        description=request.description or strategy.get("description", ""),
        start_date=request.start_date,
        end_date=request.end_date,
        initial_balance=float(strategy.get("initial_amount", request.initial_balance)),
        trading_parameters=trading_parameters,
        pairs=pairs,
    )


# Custom OpenAPI schema for JWT Bearer authentication
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="dYdX Trading Bot API",
        version="1.0.0",
        description="API for managing multiple dYdX trading bot instances with JWT Authentication",
        routes=app.routes,
    )

    # Add Bearer authentication scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token",
        }
    }

    # Apply Bearer auth to all endpoints
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                # Skip auth endpoints from requiring authentication
                if not any(
                    skip_path in path
                    for skip_path in ["/auth/", "/docs", "/redoc", "/openapi.json"]
                ):
                    openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Initialize FastAPI app
app = FastAPI(
    title="dYdX Trading Bot API",
    description="API for managing multiple dYdX trading bot instances with JWT Authentication",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Set custom OpenAPI schema
app.openapi = custom_openapi

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication routes
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)

# ============================================================================
# API RESPONSE WRAPPER
# ============================================================================


def api_response(success: bool, data=None, message: str = "", status_code: int = 200):
    """Standardized API response format"""
    response_data = {
        "success": success,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat(),
    }
    return JSONResponse(
        content=jsonable_encoder(response_data),
        status_code=status_code,
    )


# ============================================================================
# BOT INSTANCE MANAGEMENT ENDPOINTS
# ============================================================================


@app.post("/api/v1/bots", response_model=BotOperationResult)
async def create_bot_instance(
    config: BotInstanceConfig, current_user: User = Depends(get_current_active_user)
):
    """Create a new bot instance"""
    try:
        if not _bot_manager_ready():
            return _bot_manager_unavailable_response()
        result = await bot_manager.create_instance(config)

        if result.success:
            # Persist to database
            try:
                session = db.get_session()
                uow = UnitOfWork(session)

                # Create database record
                bot_db = uow.bots.create_bot(
                    instance_id=config.instance_id,
                    network=(
                        "testnet"
                        if (config.trading_params and config.trading_params.is_testnet)
                        else "mainnet"
                    ),
                    strategy=(
                        config.trading_params.strategy if config.trading_params else "default"
                    ),
                    config={
                        "instance_name": config.instance_name,
                        "credentials": (
                            config.credentials.model_dump() if config.credentials else {}
                        ),
                        "trading_params": (
                            config.trading_params.model_dump() if config.trading_params else {}
                        ),
                    },
                )

                # Log creation event
                uow.events.log_event(
                    bot_db.id,
                    "bot_created",
                    "info",
                    f"Bot instance created via API: {config.instance_id}",
                    details={"instance_name": config.instance_name},
                )

                session.close()
                logger.info(f"Bot instance '{config.instance_id}' persisted to database")
            except Exception as db_error:
                logger.warning(f"Failed to persist bot to database: {db_error}")
                # Continue anyway - bot was created in manager

            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{config.instance_id}' created successfully",
            )
        else:
            return api_response(success=False, message=result.message, status_code=400)

    except Exception as e:
        logger.error(f"Error creating bot instance: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/bots", response_model=BotInstanceList)
async def list_bot_instances(current_user: User = Depends(get_current_active_user)):
    """Get list of all bot instances"""
    try:
        if not _bot_manager_ready():
            return api_response(
                success=True,
                data={"bots": [], "total": 0},
                message="Retrieved 0 bot instances (bot manager unavailable)",
            )
        instances = await bot_manager.list_instances()

        return api_response(
            success=True,
            data={
                "bots": [instance.model_dump() for instance in instances],
                "total": len(instances),
            },
            message=f"Retrieved {len(instances)} bot instances",
        )

    except Exception as e:
        logger.error(f"Error listing bot instances: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/bots/{instance_id}", response_model=BotInstanceStatus)
async def get_bot_instance(instance_id: str, current_user: User = Depends(get_current_active_user)):
    """Get specific bot instance status"""
    try:
        if not _bot_manager_ready():
            return _bot_manager_unavailable_response()
        instance = await bot_manager.get_instance_status(instance_id)

        if instance is None:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        return api_response(
            success=True,
            data=instance.model_dump(),
            message=f"Retrieved status for bot instance '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.delete("/api/v1/bots/{instance_id}")
async def delete_bot_instance(
    instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Delete bot instance"""
    try:
        if not _bot_manager_ready():
            return _bot_manager_unavailable_response()
        result = await bot_manager.delete_instance(instance_id)

        if result.success:
            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{instance_id}' deleted successfully",
            )
        else:
            return api_response(success=False, message=result.message, status_code=400)

    except Exception as e:
        logger.error(f"Error deleting bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# BOT CONTROL ENDPOINTS
# ============================================================================


@app.post("/api/v1/bots/{instance_id}/start")
async def start_bot_instance(
    instance_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
):
    """Start bot instance"""
    try:
        if not _bot_manager_ready():
            return _bot_manager_unavailable_response()
        result = await bot_manager.start_instance(instance_id)

        if result.success:
            # Update database
            try:
                session = db.get_session()
                uow = UnitOfWork(session)

                bot = uow.bots.get_by_instance_id(instance_id)
                if bot:
                    from internal.domain import BotStatusEnum

                    uow.bots.update_status(
                        instance_id,
                        BotStatusEnum.RUNNING,
                        process_id=(result.data.get("process_id") if result.data else None),
                    )
                    uow.events.log_event(
                        bot.id,
                        "bot_started",
                        "info",
                        f"Bot started via API (PID: {result.data.get('process_id') if result.data else 'unknown'})",
                    )

                session.close()
            except Exception as db_error:
                logger.warning(f"Failed to update database on bot start: {db_error}")

            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{instance_id}' started successfully",
            )
        else:
            return api_response(success=False, message=result.message, status_code=400)

    except Exception as e:
        logger.error(f"Error starting bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/bots/{instance_id}/stop")
async def stop_bot_instance(
    instance_id: str,
    force: bool = False,
    current_user: User = Depends(get_current_active_user),
):
    """Stop bot instance"""
    try:
        if not _bot_manager_ready():
            return _bot_manager_unavailable_response()
        result = await bot_manager.stop_instance(instance_id, force=force)

        if result.success:
            # Update database
            try:
                session = db.get_session()
                uow = UnitOfWork(session)

                bot = uow.bots.get_by_instance_id(instance_id)
                if bot:
                    from internal.domain import BotStatusEnum

                    uow.bots.update_status(instance_id, BotStatusEnum.STOPPED)
                    uow.events.log_event(
                        bot.id,
                        "bot_stopped",
                        "info",
                        f"Bot stopped via API (force={force})",
                    )

                session.close()
            except Exception as db_error:
                logger.warning(f"Failed to update database on bot stop: {db_error}")

            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{instance_id}' stopped successfully",
            )
        else:
            return api_response(success=False, message=result.message, status_code=400)

    except Exception as e:
        logger.error(f"Error stopping bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/bots/{instance_id}/restart")
async def restart_bot_instance(
    instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Restart bot instance"""
    try:
        if not _bot_manager_ready():
            return _bot_manager_unavailable_response()
        # Stop first
        stop_result = await bot_manager.stop_instance(instance_id, force=False)
        if not stop_result.success:
            return api_response(
                success=False,
                message=f"Failed to stop instance: {stop_result.message}",
                status_code=400,
            )

        # Wait a moment
        await asyncio.sleep(2)

        # Start again
        start_result = await bot_manager.start_instance(instance_id)

        if start_result.success:
            return api_response(
                success=True,
                data=start_result.model_dump(),
                message=f"Bot instance '{instance_id}' restarted successfully",
            )
        else:
            return api_response(
                success=False,
                message=f"Failed to start instance: {start_result.message}",
                status_code=400,
            )

    except Exception as e:
        logger.error(f"Error restarting bot instance {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# DATABASE & HISTORY ENDPOINTS
# ============================================================================


@app.get("/api/v1/bots/{instance_id}/history")
async def get_bot_history(
    instance_id: str,
    days: int = 7,
    current_user: User = Depends(get_current_active_user),
):
    """Get bot event history"""
    try:
        session = db.get_session()
        uow = UnitOfWork(session)

        # Get bot first to verify it exists
        bot = uow.bots.get_by_instance_id(instance_id)
        if not bot:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        # Get events
        events = uow.events.get_bot_events(bot.id, days=days)

        return api_response(
            success=True,
            data={
                "instance_id": instance_id,
                "total_events": len(events),
                "days_requested": days,
                "events": [
                    {
                        "timestamp": e.created_at.isoformat(),
                        "event_type": e.event_type,
                        "severity": e.severity,
                        "message": e.message,
                        "details": e.details,
                    }
                    for e in events
                ],
            },
            message=f"Retrieved {len(events)} events for bot '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot history for {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )
    finally:
        session.close()


@app.get("/api/v1/bots/{instance_id}/jobs")
async def get_bot_jobs(
    instance_id: str,
    days: int = 7,
    current_user: User = Depends(get_current_active_user),
):
    """Get bot job history"""
    try:
        session = db.get_session()
        uow = UnitOfWork(session)

        # Get bot first
        bot = uow.bots.get_by_instance_id(instance_id)
        if not bot:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        # Get jobs
        jobs = uow.jobs.get_job_history(bot.id, days=days)

        # Calculate job statistics
        total_jobs = len(jobs)
        completed_jobs = len([j for j in jobs if j.status == "COMPLETED"])
        failed_jobs = len([j for j in jobs if j.status == "FAILED"])
        retry_jobs = len([j for j in jobs if j.status == "RETRY"])
        queued_jobs = len([j for j in jobs if j.status == "QUEUED"])

        return api_response(
            success=True,
            data={
                "instance_id": instance_id,
                "statistics": {
                    "total_jobs": total_jobs,
                    "completed": completed_jobs,
                    "failed": failed_jobs,
                    "retry": retry_jobs,
                    "queued": queued_jobs,
                },
                "jobs": [
                    {
                        "job_id": j.job_id,
                        "job_type": j.job_type,
                        "status": j.status,
                        "process_id": j.process_id,
                        "execution_time_ms": j.execution_time_ms,
                        "retry_count": f"{j.retry_count}/{j.max_retries}",
                        "created_at": j.created_at.isoformat(),
                        "started_at": (j.started_at.isoformat() if j.started_at else None),
                        "completed_at": (j.completed_at.isoformat() if j.completed_at else None),
                        "error_message": j.error_message,
                    }
                    for j in jobs
                ],
            },
            message=f"Retrieved {total_jobs} jobs for bot '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot jobs for {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )
    finally:
        session.close()


@app.get("/api/v1/bots/{instance_id}/trades")
async def get_bot_trades(
    instance_id: str,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    """Get bot trades"""
    try:
        session = db.get_session()
        uow = UnitOfWork(session)

        # Get bot first
        bot = uow.bots.get_by_instance_id(instance_id)
        if not bot:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        # Get trades
        trades = uow.trades.get_bot_trades(bot.id)

        # Filter by status if requested
        if status:
            trades = [t for t in trades if t.status == status.upper()]

        return api_response(
            success=True,
            data={
                "instance_id": instance_id,
                "total_trades": len(trades),
                "filter_status": status,
                "trades": [
                    {
                        "trade_id": t.trade_id,
                        "pair1": t.pair1,
                        "pair2": t.pair2,
                        "status": t.status,
                        "entry_price1": (float(t.entry_price1) if t.entry_price1 else None),
                        "entry_price2": (float(t.entry_price2) if t.entry_price2 else None),
                        "exit_price1": float(t.exit_price1) if t.exit_price1 else None,
                        "exit_price2": float(t.exit_price2) if t.exit_price2 else None,
                        "entry_cost": float(t.entry_cost) if t.entry_cost else None,
                        "exit_proceeds": (float(t.exit_proceeds) if t.exit_proceeds else None),
                        "profit_loss": float(t.profit_loss) if t.profit_loss else None,
                        "profit_loss_percentage": (
                            float(t.profit_loss_percentage) if t.profit_loss_percentage else None
                        ),
                        "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                        "duration_seconds": t.duration_seconds,
                    }
                    for t in trades
                ],
            },
            message=f"Retrieved {len(trades)} trades for bot '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot trades for {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )
    finally:
        session.close()


@app.get("/api/v1/bots/{instance_id}/stats")
async def get_bot_stats(instance_id: str, current_user: User = Depends(get_current_active_user)):
    """Get bot statistics"""
    try:
        session = db.get_session()
        uow = UnitOfWork(session)

        # Get bot first
        bot = uow.bots.get_by_instance_id(instance_id)
        if not bot:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        # Get bot statistics
        bot_stats = uow.bots.get_statistics(instance_id)

        # Get trade statistics
        trade_stats = uow.trades.get_trade_statistics(bot.id)

        return api_response(
            success=True,
            data={
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
                    "average_duration_seconds": trade_stats.get("average_duration_seconds", 0),
                },
            },
            message=f"Retrieved statistics for bot '{instance_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting bot statistics for {instance_id}: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )
    finally:
        session.close()


# ============================================================================
# QUICK DEPLOYMENT ENDPOINTS
# ============================================================================


@app.post("/api/v1/bots/quick-deploy")
async def quick_deploy_bot(
    instance_name: str,
    credentials: BotCredentials,
    trading_params: TradingParameters,
    auto_start: bool = True,
    current_user: User = Depends(get_current_active_user),
):
    """Quick deploy and optionally start a new bot instance"""
    try:
        if not _bot_manager_ready():
            return _bot_manager_unavailable_response()
        # Generate instance ID from name
        import re

        instance_id = re.sub(r"[^a-zA-Z0-9_-]", "-", instance_name.lower())
        instance_id = f"{instance_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Create configuration
        config = BotInstanceConfig(
            instance_id=instance_id,
            instance_name=instance_name,
            credentials=credentials,
            trading_params=trading_params,
        )

        # Create instance
        create_result = await bot_manager.create_instance(config)
        if not create_result.success:
            return api_response(success=False, message=create_result.message, status_code=400)

        # Auto-start if requested
        if auto_start:
            await asyncio.sleep(1)  # Brief pause
            start_result = await bot_manager.start_instance(instance_id)

            if start_result.success:
                return api_response(
                    success=True,
                    data={
                        "instance_id": instance_id,
                        "created": create_result.success,
                        "started": start_result.success,
                        "status": "running",
                    },
                    message=f"Bot '{instance_name}' deployed and started successfully",
                )
            else:
                return api_response(
                    success=True,
                    data={
                        "instance_id": instance_id,
                        "created": create_result.success,
                        "started": False,
                        "status": "stopped",
                        "start_error": start_result.message,
                    },
                    message=f"Bot '{instance_name}' deployed but failed to start: {start_result.message}",
                )
        else:
            return api_response(
                success=True,
                data={
                    "instance_id": instance_id,
                    "created": create_result.success,
                    "started": False,
                    "status": "stopped",
                },
                message=f"Bot '{instance_name}' deployed successfully (not started)",
            )

    except Exception as e:
        logger.error(f"Error in quick deploy: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# HEALTH AND STATUS ENDPOINTS
# ============================================================================


@app.get("/health")
async def health_check():
    """API health check"""
    return api_response(
        success=True,
        data={
            "status": "healthy",
            "api_version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
        },
        message="API is healthy",
    )


@app.get("/api/v1/users/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    """Frontend-compatible current user endpoint used after login."""
    return api_response(
        success=True,
        data={
            "id": int(getattr(current_user, "id", 1) or 1),
            "username": str(getattr(current_user, "username", "admin")),
            "email": str(getattr(current_user, "email", "admin@example.local")),
            "is_active": bool(getattr(current_user, "is_active", True)),
            "is_admin": bool(
                getattr(
                    current_user,
                    "is_admin",
                    getattr(current_user, "is_superuser", False),
                )
            ),
            "created_at": (getattr(current_user, "created_at", datetime.now())).isoformat(),
        },
        message="Current user profile retrieved",
    )


@app.get("/api/v1/system/status")
async def system_status(current_user: User = Depends(get_current_active_user)):
    """Get system status and statistics"""
    try:
        if not _bot_manager_ready():
            return api_response(
                success=True,
                data={
                    "bot_instances": {"total": 0, "running": 0, "max_allowed": 0},
                    "system_resources": {
                        "cpu_usage_percent": 0,
                        "memory_usage_percent": 0,
                        "memory_available_gb": 0,
                    },
                    "api_info": {"version": "1.0.0", "uptime_hours": "N/A"},
                },
                message="System status available; bot manager unavailable",
            )
        instances = await bot_manager.list_instances()

        # Cleanup any dead processes
        await bot_manager.cleanup_dead_processes()

        # Calculate system stats
        total_instances = len(instances)
        running_instances = len([i for i in instances if i.status == BotStatus.RUNNING])

        # System resource usage
        import psutil

        cpu_usage = psutil.cpu_percent()
        memory = psutil.virtual_memory()

        return api_response(
            success=True,
            data={
                "bot_instances": {
                    "total": total_instances,
                    "running": running_instances,
                    "max_allowed": bot_manager.max_instances,
                },
                "system_resources": {
                    "cpu_usage_percent": cpu_usage,
                    "memory_usage_percent": memory.percent,
                    "memory_available_gb": round(memory.available / (1024**3), 2),
                },
                "api_info": {
                    "version": "1.0.0",
                    "uptime_hours": "N/A",  # Could implement uptime tracking
                },
            },
            message="System status retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# REAL-TIME DATA ENDPOINTS
# ============================================================================


@app.get("/api/v1/bots/{bot_instance_id}/positions/current")
async def get_current_positions(
    bot_instance_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get all currently open positions for a bot"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        positions = uow.positions.get_open_positions(int(bot_instance_id))

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "positions": [
                    serialize_realtime_position(p, include_updated_at=True) for p in positions
                ],
                "count": len(positions),
            },
        )

    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/positions/{position_id}")
async def get_position(bot_instance_id: int, position_id: str):
    """Get specific position details"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        position = uow.positions.get_position_by_id(position_id)

        if not position or position.bot_instance_id != bot_instance_id:
            return api_response(success=False, message="Position not found", status_code=404)

        return api_response(
            success=True,
            data={
                "position_id": position.position_id,
                "pair1": position.pair1,
                "pair2": position.pair2,
                "side1": position.side1,
                "side2": position.side2,
                "status": position.status.value,
                "entry_price1": float(position.entry_price1),
                "entry_price2": float(position.entry_price2),
                "current_price1": float(position.current_price1),
                "current_price2": float(position.current_price2),
                "current_size1": float(position.current_size1),
                "current_size2": float(position.current_size2),
                "entry_cost": float(position.entry_cost),
                "current_value": float(position.current_value),
                "unrealized_pnl": float(position.unrealized_pnl),
                "unrealized_pnl_pct": float(position.unrealized_pnl_pct),
                "realized_pnl": (float(position.realized_pnl) if position.realized_pnl else 0),
                "z_score_entry": (
                    float(position.z_score_entry) if position.z_score_entry else None
                ),
                "z_score_current": (
                    float(position.z_score_current) if position.z_score_current else None
                ),
                "hedge_ratio": (float(position.hedge_ratio) if position.hedge_ratio else None),
                "correlation": (float(position.correlation) if position.correlation else None),
                "half_life": float(position.half_life) if position.half_life else None,
                "entered_at": position.entry_time.isoformat(),
                "updated_at": (position.updated_at.isoformat() if position.updated_at else None),
                "closed_at": (position.closed_at.isoformat() if position.closed_at else None),
            },
        )

    except Exception as e:
        logger.error(f"Error getting position: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/market-data")
async def get_market_data(bot_instance_id: int):
    """Get latest market data for all symbols tracked by bot"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        market_data = uow.market_data.get_all_market_data(bot_instance_id)

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "market_data": [
                    {
                        **serialize_market_core(m, include_volatility=True),
                        "rsi": float(m.rsi) if m.rsi else None,
                        "macd": float(m.macd) if m.macd else None,
                        "moving_avg_20": (float(m.moving_avg_20) if m.moving_avg_20 else None),
                        "moving_avg_50": (float(m.moving_avg_50) if m.moving_avg_50 else None),
                        "funding_rate": (float(m.funding_rate) if m.funding_rate else None),
                        "updated_at": m.timestamp.isoformat() if m.timestamp else None,
                    }
                    for m in market_data
                ],
                "count": len(market_data),
            },
        )

    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/realtime-stats")
async def get_realtime_stats(bot_instance_id: int):
    """Get real-time bot statistics"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        stats = uow.stats.get_stats(bot_instance_id)

        if not stats:
            return api_response(
                success=True,
                data={
                    "bot_instance_id": bot_instance_id,
                    "stats": {
                        "total_open_positions": 0,
                        "total_unrealized_pnl": 0,
                        "total_unrealized_pnl_pct": 0,
                        "daily_pnl": 0,
                        "daily_pnl_pct": 0,
                        "daily_trades_opened": 0,
                        "daily_trades_closed": 0,
                        "daily_wins": 0,
                        "daily_losses": 0,
                        "daily_win_rate": 0,
                        "max_drawdown": 0,
                        "current_drawdown": 0,
                    },
                },
            )

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "stats": {
                    "total_open_positions": stats.total_open_positions,
                    "total_unrealized_pnl": float(stats.total_unrealized_pnl),
                    "total_unrealized_pnl_pct": float(stats.total_unrealized_pnl_pct),
                    "daily_pnl": float(stats.daily_pnl),
                    "daily_pnl_pct": float(stats.daily_pnl_pct),
                    "daily_trades_opened": stats.daily_trades_opened,
                    "daily_trades_closed": stats.daily_trades_closed,
                    "daily_wins": (stats.daily_wins if hasattr(stats, "daily_wins") else 0),
                    "daily_losses": (stats.daily_losses if hasattr(stats, "daily_losses") else 0),
                    **serialize_stats_risk_fields(stats),
                    "var_95": float(stats.var_95) if stats.var_95 else None,
                    "avg_trade_duration": (
                        stats.avg_trade_duration_seconds
                        if hasattr(stats, "avg_trade_duration_seconds")
                        else None
                    ),
                    "is_healthy": (stats.is_healthy if hasattr(stats, "is_healthy") else True),
                    "updated_at": (
                        stats.updated_at.isoformat()
                        if hasattr(stats, "updated_at") and stats.updated_at
                        else None
                    ),
                },
            },
        )

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/alerts")
async def get_alerts(bot_instance_id: int, limit: int = 50):
    """Get recent alerts for a bot"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        alerts = uow.alerts.get_unnotified_alerts(bot_instance_id)
        # Limit to most recent
        alerts = alerts[:limit]

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "alerts": [
                    {
                        "id": a.id,
                        "type": a.alert_type,
                        "severity": a.severity,
                        "message": a.message,
                        "notified": a.notified,
                        "notified_via": a.notified_via if a.notified_via else {},
                        "created_at": a.timestamp.isoformat() if a.timestamp else None,
                        "details": a.details if a.details else {},
                    }
                    for a in alerts
                ],
                "count": len(alerts),
            },
        )

    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


@app.get("/api/v1/bots/{bot_instance_id}/position-history/{position_id}")
async def get_position_history(bot_instance_id: int, position_id: str, hours: int = 24):
    """Get historical P&L snapshots for a position"""
    try:
        session = db.get_session()
        uow = UnitOfWorkRealtime(session)

        snapshots = uow.snapshots.get_position_history(position_id, hours=hours)

        return api_response(
            success=True,
            data={
                "bot_instance_id": bot_instance_id,
                "position_id": position_id,
                "hours": hours,
                "snapshots": [
                    {
                        "pair1": s.pair1,
                        "pair2": s.pair2,
                        "unrealized_pnl": float(s.unrealized_pnl),
                        "unrealized_pnl_pct": float(s.unrealized_pnl_pct),
                        "current_price1": (float(s.current_price1) if s.current_price1 else None),
                        "current_price2": (float(s.current_price2) if s.current_price2 else None),
                        "z_score": float(s.z_score) if s.z_score else None,
                        "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                    }
                    for s in snapshots
                ],
                "count": len(snapshots),
            },
        )

    except Exception as e:
        logger.error(f"Error getting position history: {e}")
        return api_response(success=False, message=f"Error: {str(e)}", status_code=500)
    finally:
        session.close()


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================


@app.websocket("/api/v1/bots/{bot_instance_id}/positions/live")
async def websocket_positions(websocket: WebSocket, bot_instance_id: int):
    """WebSocket endpoint for live position updates"""
    await WebSocketServer.handle_connection(websocket, str(bot_instance_id))


@app.websocket("/api/v1/bots/{bot_instance_id}/market/live")
async def websocket_market(websocket: WebSocket, bot_instance_id: int):
    """WebSocket endpoint for live market data"""
    await WebSocketServer.handle_connection(websocket, str(bot_instance_id))


@app.websocket("/api/v1/bots/{bot_instance_id}/alerts/live")
async def websocket_alerts(websocket: WebSocket, bot_instance_id: int):
    """WebSocket endpoint for live alerts"""
    await WebSocketServer.handle_connection(websocket, str(bot_instance_id))


@app.websocket("/api/v1/backtests/{run_id}/live")
async def websocket_backtest_progress(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for live backtest progress updates."""
    await WebSocketServer.handle_connection(websocket, f"backtest-{run_id}")


# ============================================================================
# BACKTESTING ENDPOINTS
# ============================================================================


# Initialize backtest service
def get_backtest_service():
    """Dependency to get backtest service"""
    db_session = db.get_session()
    repository = BacktestRepository(db_session)
    # Ensure repository has access to session for service operations
    repository.db = db_session
    service = BacktestService(repository)
    return service


@app.post("/api/v1/backtests", response_model=BacktestResponse)
async def create_backtest(
    request: Union[BacktestConfigRequest, BacktestRunRequestCompat],
):
    """Create and start a new backtest"""
    try:
        service = get_backtest_service()

        if isinstance(request, BacktestRunRequestCompat):
            if request.strategy_id is not None:
                strategy = InMemoryStrategyStore.get(request.strategy_id)
                if strategy:
                    normalized_request = _strategy_to_backtest_request(strategy, request)
                else:
                    logger.warning(
                        "Strategy '%s' not found; falling back to manual backtest payload",
                        request.strategy_id,
                    )
                    normalized_request = BacktestConfigRequest(
                        name=request.name or "manual-backtest",
                        description=request.description or "Manual backtest run",
                        start_date=request.start_date,
                        end_date=request.end_date,
                        initial_balance=request.initial_balance,
                        trading_parameters=request.trading_parameters
                        or {
                            "zscore_threshold": 1.5,
                            "stats_window": 21,
                            "usd_per_trade": 10.0,
                            "close_at_zscore_cross": True,
                        },
                        pairs=request.pairs or DEFAULT_PAIRS[: max(1, request.max_pairs)],
                    )
            else:
                normalized_request = BacktestConfigRequest(
                    name=request.name or "manual-backtest",
                    description=request.description or "Manual backtest run",
                    start_date=request.start_date,
                    end_date=request.end_date,
                    initial_balance=request.initial_balance,
                    trading_parameters=request.trading_parameters
                    or {
                        "zscore_threshold": 1.5,
                        "stats_window": 21,
                        "usd_per_trade": 10.0,
                        "close_at_zscore_cross": True,
                    },
                    pairs=request.pairs or DEFAULT_PAIRS[: max(1, request.max_pairs)],
                )
        else:
            normalized_request = request

        # Create WebSocket progress callback (if needed)
        async def progress_callback(run_id: str, progress: float, current_pair: str, eta: int):
            message = {
                "type": "backtest_progress",
                "timestamp": datetime.utcnow().isoformat(),
                "run_id": run_id,
                "progress_pct": progress,
                "current_pair": current_pair,
                "eta_seconds": eta,
            }
            await manager.broadcast_to_bot(f"backtest-{run_id}", message)
            logger.debug(
                f"Backtest {run_id} progress: {progress:.1f}% ({current_pair}), ETA: {eta}s"
            )

        result = await service.create_and_run_backtest(normalized_request, progress_callback)

        return api_response(
            success=True,
            data=result.model_dump(),
            message=f"Backtest '{normalized_request.name}' created and started",
        )

    except ValueError as e:
        return api_response(success=False, message=f"Validation error: {str(e)}", status_code=400)
    except Exception as e:
        logger.error(f"Error creating backtest: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/backtests/run")
async def run_backtest_compat(
    request: BacktestRunRequestCompat,
):
    """Frontend-compatible backtest execution route."""
    try:
        if request.strategy_id is not None:
            strategy = InMemoryStrategyStore.get(request.strategy_id)
            if strategy:
                backtest_request = _strategy_to_backtest_request(strategy, request)
            else:
                logger.warning(
                    "Strategy '%s' not found in /backtests/run; falling back to manual payload",
                    request.strategy_id,
                )
                backtest_request = BacktestConfigRequest(
                    name=request.name or "manual-backtest",
                    description=request.description or "Manual backtest run",
                    start_date=request.start_date,
                    end_date=request.end_date,
                    initial_balance=request.initial_balance,
                    trading_parameters=request.trading_parameters
                    or {
                        "zscore_threshold": 1.5,
                        "stats_window": 21,
                        "usd_per_trade": 10.0,
                        "close_at_zscore_cross": True,
                    },
                    pairs=request.pairs or DEFAULT_PAIRS[: max(1, request.max_pairs)],
                )
        else:
            backtest_request = BacktestConfigRequest(
                name=request.name or "manual-backtest",
                description=request.description or "Manual backtest run",
                start_date=request.start_date,
                end_date=request.end_date,
                initial_balance=request.initial_balance,
                trading_parameters=request.trading_parameters
                or {
                    "zscore_threshold": 1.5,
                    "stats_window": 21,
                    "usd_per_trade": 10.0,
                    "close_at_zscore_cross": True,
                },
                pairs=request.pairs or DEFAULT_PAIRS[: max(1, request.max_pairs)],
            )

        service = get_backtest_service()
        result = await service.create_and_run_backtest(backtest_request)
        return api_response(
            success=True,
            data=result.model_dump(),
            message=f"Backtest '{result.name}' completed",
        )
    except Exception as e:
        logger.error(f"Error running compatibility backtest: {e}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(e)}",
            status_code=500,
        )


@app.get("/api/v1/backtests", response_model=BacktestListResponse)
async def list_backtests(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    days: Optional[int] = None,
):
    """List backtest runs with filtering"""
    try:
        service = get_backtest_service()

        result = service.list_backtest_runs(
            limit=limit, offset=offset, status_filter=status, days_filter=days
        )

        return api_response(
            success=True,
            data=result.model_dump(),
            message=f"Retrieved {len(result.runs)} backtest runs",
        )

    except Exception as e:
        logger.error(f"Error listing backtests: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}", response_model=BacktestDetailResponse)
async def get_backtest_details(
    run_id: str,
):
    """Get detailed backtest results"""
    try:
        service = get_backtest_service()

        result = service.get_backtest_details(run_id)
        if not result:
            return api_response(
                success=False,
                message=f"Backtest run '{run_id}' not found",
                status_code=404,
            )

        return api_response(
            success=True,
            data=result.model_dump(),
            message=f"Retrieved details for backtest '{run_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting backtest details: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}/status")
async def get_backtest_status(
    run_id: str,
):
    """Get current backtest status and progress"""
    try:
        service = get_backtest_service()

        result = service.get_backtest_status(run_id)
        if not result:
            return api_response(
                success=False,
                message=f"Backtest run '{run_id}' not found",
                status_code=404,
            )

        return api_response(
            success=True,
            data=result.model_dump(),
            message=f"Retrieved status for backtest '{run_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting backtest status: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/backtests/{run_id}/create-strategy")
async def create_strategy_from_backtest(
    run_id: str,
    request: BacktestCreateStrategyRequest,
):
    """Create a strategy snapshot from an existing backtest."""
    service = get_backtest_service()
    details = service.get_backtest_details(run_id)
    if not details:
        return api_response(
            success=False,
            message=f"Backtest '{run_id}' not found",
            status_code=404,
        )

    payload = {
        "name": request.name,
        "description": request.description,
        **request.config,
        "is_public": False,
    }
    strategy = InMemoryStrategyStore.create(payload)
    return api_response(
        success=True,
        data={
            **strategy,
            "source_backtest_run_id": run_id,
        },
        message="Strategy created from backtest",
    )


@app.get("/api/v1/backtests/{run_id}/trades")
async def get_backtest_trades(
    run_id: str,
    limit: int = 100,
    offset: int = 0,
    winning_only: bool = False,
):
    """Get trades for specific backtest run"""
    try:
        service = get_backtest_service()

        trades = service.get_backtest_trades(
            run_id=run_id, limit=limit, offset=offset, winning_only=winning_only
        )

        return api_response(
            success=True,
            data={"trades": [trade.model_dump() for trade in trades]},
            message=f"Retrieved {len(trades)} trades for backtest '{run_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting backtest trades: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/backtests/{run_id}/cancel")
async def cancel_backtest(
    run_id: str,
):
    """Cancel running backtest"""
    try:
        service = get_backtest_service()

        success = service.cancel_backtest(run_id)
        if not success:
            return api_response(
                success=False,
                message=f"Backtest '{run_id}' not found or not running",
                status_code=404,
            )

        return api_response(success=True, message=f"Backtest '{run_id}' cancelled successfully")

    except Exception as e:
        logger.error(f"Error cancelling backtest: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.delete("/api/v1/backtests/{run_id}")
async def delete_backtest(
    run_id: str,
):
    """Delete backtest run and all associated data"""
    try:
        service = get_backtest_service()

        success = service.delete_backtest(run_id)
        if not success:
            return api_response(
                success=False, message=f"Backtest '{run_id}' not found", status_code=404
            )

        return api_response(success=True, message=f"Backtest '{run_id}' deleted successfully")

    except Exception as e:
        logger.error(f"Error deleting backtest: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/stats/summary")
async def get_backtest_summary_stats(
    days: int = 30,
):
    """Get backtest system summary statistics"""
    try:
        service = get_backtest_service()

        stats = service.get_summary_stats(days)

        return api_response(
            success=True,
            data=stats,
            message=f"Retrieved backtest statistics for last {days} days",
        )

    except Exception as e:
        logger.error(f"Error getting backtest stats: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}/analytics")
async def get_backtest_analytics(
    run_id: str,
):
    """Get comprehensive analytics for a backtest run"""
    try:
        service = get_backtest_service()

        analytics = service.get_comprehensive_analytics(run_id)
        if not analytics:
            return api_response(
                success=False,
                message=f"Backtest run '{run_id}' not found",
                status_code=404,
            )

        return api_response(
            success=True,
            data=analytics,  # Already a dict
            message=f"Retrieved analytics for backtest '{run_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting backtest analytics: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}/position-snapshots")
async def get_position_snapshots(
    run_id: str,
    limit: int = 100,
    offset: int = 0,
    market_pair: Optional[str] = None,
):
    """Get position snapshots for real-time backtest tracking"""
    try:
        service = get_backtest_service()

        snapshots = service.get_position_snapshots(
            run_id=run_id, limit=limit, offset=offset, market_pair=market_pair
        )

        return api_response(
            success=True,
            data={"snapshots": snapshots},  # Already a list of dicts
            message=f"Retrieved {len(snapshots)} position snapshots for '{run_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting position snapshots: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.post("/api/v1/backtests/compare")
async def compare_backtests(
    request: dict,  # BacktestComparisonRequest - simplified for now
):
    """Compare multiple backtest runs with advanced analytics"""
    try:
        service = get_backtest_service()

        run_ids = request.get("run_ids", [])
        metrics = request.get("metrics", ["total_return_pct", "sharpe_ratio", "win_rate"])

        if len(run_ids) < 2:
            return api_response(
                success=False,
                message="At least 2 backtest runs required for comparison",
                status_code=400,
            )

        comparison = service.compare_backtests(run_ids, metrics)

        return api_response(
            success=True,
            data=comparison,  # Already a dict
            message=f"Compared {len(run_ids)} backtest runs",
        )

    except Exception as e:
        logger.error(f"Error comparing backtests: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}/dydx-validation")
async def validate_against_dydx_data(
    run_id: str,
):
    """Validate backtest results against real dYdX market data"""
    try:
        service = get_backtest_service()

        validation_result = await service.validate_against_dydx_data(run_id)
        if not validation_result:
            return api_response(
                success=False,
                message=f"Could not validate backtest '{run_id}' against dYdX data",
                status_code=404,
            )

        return api_response(
            success=True,
            data=validation_result,
            message=f"Validated backtest '{run_id}' against dYdX historical data",
        )

    except Exception as e:
        logger.error(f"Error validating against dYdX data: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}/performance-metrics")
async def get_advanced_performance_metrics(
    run_id: str,
    benchmark: str = "BTC-USD",
):
    """Get advanced performance metrics with market benchmarking"""
    try:
        service = get_backtest_service()

        metrics = await service.get_advanced_performance_metrics(run_id, benchmark)
        if not metrics:
            return api_response(
                success=False,
                message=f"Could not calculate metrics for backtest '{run_id}'",
                status_code=404,
            )

        return api_response(
            success=True,
            data=metrics,
            message=f"Retrieved advanced performance metrics for '{run_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


@app.get("/api/v1/backtests/{run_id}/live-progress")
async def get_live_progress(
    run_id: str,
):
    """Get real-time backtest progress with current positions"""
    try:
        service = get_backtest_service()

        progress = service.get_live_progress(run_id)
        if not progress:
            return api_response(
                success=False,
                message=f"Backtest run '{run_id}' not found",
                status_code=404,
            )

        return api_response(
            success=True,
            data=progress,
            message=f"Retrieved live progress for backtest '{run_id}'",
        )

    except Exception as e:
        logger.error(f"Error getting live progress: {e}")
        return api_response(
            success=False, message=f"Internal server error: {str(e)}", status_code=500
        )


# ============================================================================
# BACKGROUND TASKS
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize bot manager on startup"""
    logger.info("Starting Bot API Server...")
    logger.info(
        "Runtime DB target: type=%s host=%s port=%s name=%s",
        os.getenv("DB_TYPE", "sqlite"),
        os.getenv("DB_HOST", "localhost"),
        os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "trading_bot.db"),
    )
    db.create_all_tables()
    InMemoryStrategyStore.ensure_seeded()
    if bot_manager is not None:
        await bot_manager.cleanup_dead_processes()
    else:
        logger.warning("Bot manager unavailable; bot-instance endpoints may be degraded")
    logger.info("Bot API Server ready")


# ============================================================================
# STRATEGY ENDPOINTS
# ============================================================================


@app.get("/api/v1/strategies")
async def list_strategies(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
):
    """List stored strategies for the UI."""
    del current_user
    data = InMemoryStrategyStore.list(skip=skip, limit=limit)
    return api_response(
        success=True,
        data=data,
        message=f"Retrieved {len(data['strategies'])} strategies",
    )


@app.get("/api/v1/strategies/public")
async def list_public_strategies():
    """List public strategies."""
    data = InMemoryStrategyStore.list_public()
    return api_response(
        success=True,
        data=data,
        message=f"Retrieved {len(data['strategies'])} public strategies",
    )


@app.post("/api/v1/strategies")
async def create_strategy(
    request: StrategyRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Create a strategy."""
    del current_user
    strategy = InMemoryStrategyStore.create(request.model_dump())
    return api_response(
        success=True,
        data=strategy,
        message=f"Strategy '{strategy['name']}' created successfully",
    )


@app.get("/api/v1/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
):
    """Get one strategy."""
    del current_user
    strategy = InMemoryStrategyStore.get(strategy_id)
    if not strategy:
        return api_response(
            success=False,
            message=f"Strategy '{strategy_id}' not found",
            status_code=404,
        )
    return api_response(success=True, data=strategy, message="Strategy retrieved")


@app.put("/api/v1/strategies/{strategy_id}")
async def update_strategy(
    strategy_id: int,
    request: StrategyRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Update one strategy."""
    del current_user
    strategy = InMemoryStrategyStore.update(strategy_id, request.model_dump())
    if not strategy:
        return api_response(
            success=False,
            message=f"Strategy '{strategy_id}' not found",
            status_code=404,
        )
    return api_response(success=True, data=strategy, message="Strategy updated")


@app.delete("/api/v1/strategies/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
):
    """Delete one strategy."""
    del current_user
    if not InMemoryStrategyStore.delete(strategy_id):
        return api_response(
            success=False,
            message=f"Strategy '{strategy_id}' not found",
            status_code=404,
        )
    return api_response(success=True, message="Strategy deleted")


@app.get("/api/v1/strategies/{strategy_id}/versions")
async def get_strategy_versions(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
):
    """Get in-memory version history for a strategy."""
    del current_user
    return api_response(
        success=True,
        data={"versions": InMemoryStrategyStore.versions(strategy_id)},
        message="Strategy version history retrieved",
    )


@app.post("/api/v1/strategies/{strategy_id}/versions/{version_id}/revert")
async def revert_strategy_version(
    strategy_id: int,
    version_id: int,
    request: StrategyVersionRevertRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Revert a strategy to a prior stored version."""
    del request, current_user
    strategy = InMemoryStrategyStore.revert(strategy_id, version_id)
    if not strategy:
        return api_response(
            success=False,
            message="Strategy version not found",
            status_code=404,
        )
    return api_response(success=True, data=strategy, message="Strategy reverted")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Bot API Server...")
    # Optionally stop all running instances on shutdown
    # This could be configurable behavior


# ============================================================================
# MAIN SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    # Configuration from environment
    host = os.getenv("BOT_API_HOST", "0.0.0.0")
    port = int(os.getenv("BOT_API_PORT", 8889))
    workers = int(os.getenv("BOT_API_WORKERS", 1))

    # Run server
    uvicorn.run(
        "src.api.server:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,  # Set to True for development
        log_level="info",
    )
