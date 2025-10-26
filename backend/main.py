"""
FastAPI backend server for dYdX Backtest System.
Provides REST API and WebSocket for real-time backtest monitoring.
"""
import datetime
import logging
import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import config
from auth import (
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    create_access_token,
    create_refresh_token,
    extract_user_from_token,
    verify_token,
)
from db_services import (
    AuditLogService,
    BacktestRunService,
    UserService,
    BacktestStrategyService,
    TradeLogService,
)
from services.settings_service import SettingsService

current_path = os.path.dirname(os.path.abspath(__file__))
config.load_dotenv(os.path.join(current_path, ".env"))

logger = logging.getLogger(__name__)

# Configure logging immediately at module load
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Configuration
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:8000"
).split(",")
WS_ACTIVE_CONNECTIONS: List[WebSocket] = []


# Request/Response models
class BacktestStartRequest(BaseModel):
    """Request to start a backtest.

    Can use either:
    - strategy_id (load from database)
    - inline parameters (custom configuration)
    """

    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    num_pairs: Optional[int] = Field(None, description="Number of pairs")

    # Strategy selection (mutually exclusive with inline params)
    strategy_id: Optional[int] = Field(None, description="Strategy ID from database")

    # Existing inline parameters (used if strategy_id not provided)
    resolution: Optional[str] = Field(
        "1HOUR",
        description="Candle resolution (1MIN, 5MINS, 15MINS, 1HOUR, 4HOURS, 1DAY)",
    )
    zscore_threshold: Optional[float] = Field(1.2)
    stats_window: Optional[int] = Field(14)
    usd_per_trade: Optional[float] = Field(25.0)
    usd_min_collateral: Optional[float] = Field(100.0)
    close_at_zscore_cross: Optional[bool] = Field(True)
    find_cointegrated_pairs: Optional[bool] = Field(True)
    manage_exits: Optional[bool] = Field(True)
    place_trades: Optional[bool] = Field(True)
    abort_all_positions: Optional[bool] = Field(False)

    # Additional strategy parameters (sent from frontend but may not be used)
    max_half_life: Optional[int] = Field(None)
    max_positions: Optional[int] = Field(None)
    max_drawdown_pct: Optional[float] = Field(None)
    stop_loss_pct: Optional[float] = Field(None)
    take_profit_pct: Optional[float] = Field(None)
    trailing_stop_pct: Optional[float] = Field(None)
    rebalance_interval_hours: Optional[int] = Field(None)
    position_timeout_hours: Optional[int] = Field(None)

    class Config:
        # Allow extra fields from frontend (they'll be ignored if not used)
        extra = "allow"


class BacktestStatusUpdate(BaseModel):
    """Real-time backtest status update."""

    run_id: str
    status: str  # running, completed, failed
    progress: Optional[float] = None  # 0-100
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))


class ProfileUpdate(BaseModel):
    """Profile update request."""

    full_name: Optional[str] = Field(None, description="Full name (max 100 chars)")
    email: Optional[str] = Field(None, description="Email address")
    avatar: Optional[str] = Field(None, description="Base64 encoded image")


class ApiResponse(BaseModel):
    """Standard API response."""

    success: bool
    message: str
    data: Optional[dict] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))


# Startup/Shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown event handler."""
    # Startup
    logger.info("Starting dYdX Backtest API Server")
    # No init_db needed, handled by migration or elsewhere
    yield
    # Shutdown
    logger.info("Shutting down dYdX Backtest API Server")
    # Cleanup active WebSocket connections
    for connection in WS_ACTIVE_CONNECTIONS:
        try:
            await connection.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")


# FastAPI app
app = FastAPI(
    title="dYdX Backtest API",
    description="REST API and WebSocket server for backtest results",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware (added FIRST so it wraps all other middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler that logs errors and returns proper response."""
    # Log the full exception with traceback
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")

    # Return error response with proper status code and CORS headers
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": str(exc) if not isinstance(exc, HTTPException) else exc.detail,
            "error_type": type(exc).__name__,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )


# Security
security = HTTPBearer()


# Dependency: Get current user
async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify JWT token and get current user."""
    token = credentials.credentials

    if not verify_token(token, token_type="access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    subject = extract_user_from_token(token)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not extract user from token",
        )

    # Handle both numeric user IDs and usernames in token subject
    user = None
    try:
        # Try parsing as numeric ID first
        user_id_int = int(subject)
        user = UserService.get_user_by_id(user_id_int)
    except (ValueError, TypeError):
        # Fall back to username lookup
        user = UserService.get_user_by_username(subject)

    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return {
        "user_id": user["id"],
        "username": user["username"],
        "is_admin": user.get("is_admin", False),
    }


# ==================== AUTHENTICATION ENDPOINTS ====================


@app.post("/api/v1/auth/register", response_model=ApiResponse)
async def register(user_data: UserCreate):
    """Register new user account."""
    try:
        user = UserService.create_user(
            str(user_data.username), str(user_data.email), user_data.password
        )
        AuditLogService.log_action(
            action="user_registration", resource_type="user", user_id=user["id"]
        )
        return ApiResponse(
            success=True,
            message="User registered successfully",
            data={"user_id": user["id"], "username": user["username"]},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/v1/auth/login", response_model=Token)
async def login(login_data: UserLogin):
    """Authenticate user and return JWT tokens."""
    user = UserService.authenticate_user(login_data.username, login_data.password)

    if not user:
        AuditLogService.log_action(
            action="login_failed", resource_type="user", user_id=None, details={"username": login_data.username},
            status="failure"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    access_token = create_access_token(subject=str(user["id"]))
    refresh_token = create_refresh_token(subject=str(user["id"]))

    AuditLogService.log_action(
        action="login_success", resource_type="user", user_id=user["id"]
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,  # 30 minutes in seconds
    )


@app.post("/api/v1/auth/refresh", response_model=Token)
async def refresh_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Refresh access token using refresh token."""
    token = credentials.credentials

    if not verify_token(token, token_type="refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = extract_user_from_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    new_access_token = create_access_token(subject=user_id)
    return Token(access_token=new_access_token, token_type="bearer", expires_in=30 * 60)


# ==================== USER ENDPOINTS ====================


@app.get("/api/v1/users/me", response_model=UserResponse)
async def get_current_user_info(
        current_user: dict = Depends(get_current_user),
):
    """Get current user profile."""
    user = UserService.get_user_by_id(current_user["user_id"])
    return user


@app.put("/api/v1/profile", response_model=ApiResponse)
async def update_profile(
        profile_data: ProfileUpdate,
        current_user: dict = Depends(get_current_user),
):
    """Update current user profile (full_name, email, avatar)."""
    try:
        user = UserService.get_user_by_id(current_user["user_id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        # Update fields if provided
        update_data = {}
        if profile_data.full_name is not None:
            update_data["full_name"] = profile_data.full_name.strip()[:100]
        if profile_data.email is not None:
            update_data["email"] = profile_data.email
        if profile_data.avatar is not None:
            update_data["avatar"] = profile_data.avatar
        if update_data:
            AuditLogService.log_action(
                action="profile_update",
                resource_type="user",
                user_id=user["id"],
                details=update_data,
            )
        return ApiResponse(
            success=True,
            message="Profile updated successfully",
            data={"user": user},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# ==================== BACKTEST ENDPOINTS ====================


@app.get("/api/v1/backtests")
async def list_backtests(
        skip: int = 0,
        limit: int = 50,
        current_user: dict = Depends(get_current_user),
):
    """List backtest runs for current user."""
    runs = BacktestRunService.get_user_runs(current_user["user_id"], skip, limit)
    return ApiResponse(
        success=True,
        message="Backtests retrieved",
        data={
            "backtests": [run for run in runs]
        },
    )


@app.get("/api/v1/backtests/{run_id}")
async def get_backtest(
        run_id: str,
        current_user: dict = Depends(get_current_user),
):
    """Get backtest details with trades and results."""
    run = BacktestRunService.get_run_by_run_id(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found"
        )
    # Check authorization
    if run["user_id"] != current_user["user_id"] and not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    # Get all results for this backtest run
    from db_services import BacktestResultService
    results = BacktestResultService.get_run_results(run["id"])
    formatted_results = []
    all_trades = []
    for result in results:
        trades = TradeLogService.get_result_trades(result["id"])
        formatted_trades = []
        for trade in trades:
            formatted_trades.append(trade)
            all_trades.append(trade)
        formatted_results.append({**result, "trades": formatted_trades})
    return ApiResponse(
        success=True,
        message="Backtest retrieved",
        data={
            **run,
            "results": formatted_results,
            "all_trades": all_trades,
        },
    )


@app.post("/api/v1/backtests/run")
async def run_backtest(
        request: BacktestStartRequest,
        current_user: dict = Depends(get_current_user),
):
    """Start a new backtest run.

    Supports two modes:
    1. With strategy_id: Load strategy from database and use its parameters
    2. With inline parameters: Use custom configuration
    """
    try:
        logger.info(f"Starting backtest for user {current_user['user_id']}: {request}")

        # ========== STRATEGY SELECTION ==========
        strategy = None
        strategy_params = {}

        if request.strategy_id is not None:
            # Load strategy from database
            strategy = BacktestStrategyService.get_strategy_by_id(request.strategy_id)

            if not strategy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Strategy {request.strategy_id} not found",
                )

            # Check ownership or public access
            if strategy.user_id != current_user["user_id"] and not strategy.is_public:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to use this strategy",
                )

            # Extract all strategy parameters for engine
            strategy_params = {
                "zscore_threshold": strategy.zscore_threshold,
                "stats_window": strategy.stats_window,
                "usd_per_trade": strategy.usd_per_trade,
                "usd_min_collateral": strategy.usd_min_collateral,
                "close_at_zscore_cross": strategy.close_at_zscore_cross,
                "find_cointegrated_pairs": strategy.find_cointegrated_pairs,
                "manage_exits": strategy.manage_exits,
                "place_trades": strategy.place_trades,
                "abort_all_positions": strategy.abort_all_positions,
                "max_positions": strategy.max_positions,
                "max_drawdown_pct": strategy.max_drawdown_pct,
                "stop_loss_pct": strategy.stop_loss_pct,
                "take_profit_pct": strategy.take_profit_pct,
                "trailing_stop_pct": strategy.trailing_stop_pct,
                "rebalance_interval_hours": strategy.rebalance_interval_hours,
                "position_timeout_hours": strategy.position_timeout_hours,
                "resolution": strategy.candle_resolution,
            }

            logger.info(f"Using strategy {strategy.id} ({strategy.name})")

            # Update last_used_at timestamp
            # UserService.update_strategy_last_used_at(strategy.id)
        else:
            # Use inline parameters
            strategy_params = {
                "resolution": request.resolution,
                "zscore_threshold": request.zscore_threshold,
                "stats_window": request.stats_window,
                "usd_per_trade": request.usd_per_trade,
                "usd_min_collateral": request.usd_min_collateral,
                "close_at_zscore_cross": request.close_at_zscore_cross,
                "find_cointegrated_pairs": request.find_cointegrated_pairs,
                "manage_exits": request.manage_exits,
                "place_trades": request.place_trades,
                "abort_all_positions": request.abort_all_positions,
            }
            logger.info("Using inline parameters")

        # ========== CREATE BACKTEST RUN RECORD ==========
        import uuid

        run_id = str(uuid.uuid4())

        # Create strategy_snapshot (for reproducibility)
        strategy_snapshot = strategy_params.copy() if strategy_params else None

        BacktestRunService.create_run(
            run_id=run_id,
            start_date=request.start_date,
            end_date=request.end_date,
            num_pairs=request.num_pairs or 999,
            total_markets=0,  # Will be updated when backtest runs
            user_id=current_user["user_id"],
            config=strategy_snapshot,  # Store parameters used
            strategy_id=strategy.id if strategy else None,  # Link to strategy
            strategy_snapshot=strategy_snapshot,  # Store full snapshot in JSON
        )

        logger.info(f"Backtest {run_id} queued for user {current_user['user_id']}")

        # ========== EXECUTE BACKTEST IN BACKGROUND ==========
        import asyncio

        asyncio.create_task(
            _execute_backtest_task(run_id, request, strategy_params)
        )

        return ApiResponse(
            success=True,
            message="Backtest started",
            data={
                "run_id": run_id,
                "status": "queued",
                "strategy_id": strategy.id if strategy else None,
                "strategy_name": strategy.name if strategy else None,
                "message": f"Your backtest has been queued. "
                           f"{'Using strategy: ' + strategy.name if strategy else 'Using custom parameters.'}",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting backtest: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start backtest: {str(e)}",
        )


async def _execute_backtest_task(
        run_id: str,
        request: BacktestStartRequest,
        strategy_params: Optional[dict] = None,
):
    """Background task to execute backtest and create logs.

    Args:
        run_id: UUID of the backtest run
        request: Backtest start request parameters
        strategy_params: Optional strategy parameters to override config
    """
    import logging
    import os
    import sys
    from datetime import datetime

    # Add app directory to path BEFORE importing app modules
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

    from bot.config import config
    from bot.func_backtest_logging import log_backtest_error, log_backtest_info
    from bot.func_backtesting import BacktestEngine
    from bot.func_connections import connect_dydx
    from bot.logging_setup import setup_logging

    # Initialize logging for this background task
    setup_logging()
    task_logger = logging.getLogger(__name__)
    task_logger.info(f"Background task started for backtest {run_id}")

    # ========== FIX: Force reimport of services module to access new methods ==========
    # This ensures BacktestRunService has the latest methods (find_cached_backtest, aggregate_run_metrics)
    import importlib

    from . import db_services

    importlib.reload(db_services)
    from db_services import BacktestResultService

    try:
        log_backtest_info(run_id, "Backtest execution started", None)

        # Get the integer ID from the database
        run_record = BacktestRunService.get_run_by_run_id(run_id)
        if not run_record:
            log_backtest_error(run_id, "BacktestRun record not found in database", None)
            raise ValueError(f"BacktestRun with run_id {run_id} not found")

        run_id_int = run_record["id"]  # Direct integer value
        log_backtest_info(
            run_id, f"Backtest execution started (DB ID: {run_id_int})", None
        )

        # Load configuration
        cfg = config()
        log_backtest_info(run_id, "Configuration loaded", None)

        # ========== NEW: Apply Strategy Parameters ==========
        if strategy_params:
            # Override config.botSettings with strategy parameters
            for param, value in strategy_params.items():
                if hasattr(cfg.botSettings, param):
                    setattr(cfg.botSettings, param, value)
            log_backtest_info(
                run_id,
                f"Strategy parameters applied ({len(strategy_params)} overrides)",
                None,
            )

        # ========== CACHE-FIRST CHECK: Look for matching completed backtest ==========
        log_backtest_info(run_id, "Checking for cached backtest results...", None)

        # Build strategy snapshot for comparison
        strategy_snapshot = {}
        if strategy_params:
            strategy_snapshot = strategy_params.copy()

        # Create hashable strategy representation for comparison
        strategy_snapshot_for_query = strategy_snapshot if strategy_snapshot else None

        # Look for cached backtest with identical parameters
        cached_run = BacktestResultService.find_cached_backtest(
            None,
            request.start_date,
            request.end_date,
            request.num_pairs or 999,
            strategy_snapshot_for_query,
        )

        if cached_run and cached_run["status"] == "completed":
            log_backtest_info(
                run_id,
                f"Found cached backtest result from {cached_run['created_at']}. Using cached data...",
                None,
            )

            # Copy all result fields from cached run to current run
            run_record = (
                db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
            )
            if run_record:
                # Copy metrics (only fields that exist in BacktestRun model)
                run_record.total_trades = cached_run.total_trades
                run_record.profitable_trades = cached_run.profitable_trades
                run_record.losing_trades = cached_run.losing_trades
                run_record.total_pnl = cached_run.total_pnl
                run_record.total_pnl_usd = cached_run.total_pnl_usd
                run_record.sharpe_ratio = cached_run.sharpe_ratio
                run_record.sortino_ratio = cached_run.sortino_ratio
                run_record.max_drawdown = cached_run.max_drawdown
                run_record.win_rate = cached_run.win_rate
                run_record.profit_factor = cached_run.profit_factor
                run_record.ending_balance = cached_run.ending_balance

                db.commit()

                log_backtest_info(
                    run_id,
                    f"Cache hit! Results copied: {run_record.total_trades} trades, ${run_record.total_pnl:.2f} PnL",
                    None,
                )

                # Mark as completed and return early
                run_record.status = "completed"
                run_record.completed_at = datetime.now(timezone.utc)
                db.commit()

                log_backtest_info(run_id, "Backtest completed using cached results", None)
                return  # Exit early - no need to run backtest

        # ========== NO CACHE: Proceed with regular backtest execution ==========

        # Connect to dYdX client
        try:
            client = await connect_dydx()
            log_backtest_info(run_id, "Connected to dYdX API", None)
        except Exception as e:
            log_backtest_error(run_id, f"Failed to connect to dYdX: {str(e)}", None)
            raise

        # Create backtest engine with logging (pass integer ID for database operations)
        engine = BacktestEngine(
            client, cfg, run_id=run_id, run_id_int=run_id_int, db=None
        )  # type: ignore
        log_backtest_info(run_id, "Backtest engine initialized", None)

        # Run backtest in a thread pool to avoid blocking the event loop
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)
        num_pairs = request.num_pairs or 999

        # FIX: Use asyncio.to_thread() to run synchronous backtest in background thread
        # This prevents the UI from freezing while backtest runs
        import asyncio

        def run_backtest_sync():
            """Synchronous wrapper to run backtest in thread pool."""
            # Run the async backtest engine in the background
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    engine.run_backtest(start_date, end_date, num_pairs)
                )
            finally:
                loop.close()

        # Execute in thread pool (non-blocking)
        await asyncio.to_thread(run_backtest_sync)

        log_backtest_info(run_id, "Backtest execution completed successfully", None)

        # ========== AGGREGATE METRICS FROM TRADES ==========
        run_record = BacktestRunService.get_run_by_run_id(run_id)
        if run_record:
            BacktestResultService.aggregate_run_metrics(None, run_record["id"])
            log_backtest_info(
                run_id,
                f"Metrics aggregated - {run_record.total_trades} trades, "
                f"${run_record.total_pnl:.2f} PnL, {run_record.win_rate:.1f}% win rate",
                None,
            )

        # ========== UPDATE STATUS TO COMPLETED ==========
        run_record = BacktestRunService.get_run_by_run_id(run_id)
        if run_record:
            run_record.status = "completed"
            run_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Backtest {run_id} marked as completed in database")

    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        log_backtest_error(run_id, f"Backtest execution failed: {str(e)}", None)

        # ========== UPDATE STATUS TO FAILED ==========
        try:
            run_record = (
                db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
            )
            if run_record:
                run_record.status = "failed"
                run_record.error_message = str(e)
                run_record.completed_at = datetime.now(timezone.utc)
                db.commit()
                logger.error(f"Backtest {run_id} marked as failed in database")
        except Exception as db_error:
            logger.error(f"Failed to update backtest status to failed: {db_error}")


@app.get("/api/v1/stats")
async def get_stats(
        current_user: dict = Depends(get_current_user),
):
    """Get backtest statistics."""
    stats = BacktestRunService.get_run_stats()
    return ApiResponse(success=True, message="Statistics retrieved", data=stats)


@app.get("/api/v1/backtests/{run_id}/logs")
async def get_backtest_logs(
        run_id: str,
        current_user: dict = Depends(get_current_user),
):
    """Get logs for a specific backtest run."""
    try:
        # Find the backtest run
        run = BacktestRunService.get_run_by_run_id(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest run {run_id} not found",
            )

        # Get logs for this run, ordered by creation time
        logs = BacktestRunService.get_run_logs(run["id"])

        formatted_logs = [
            {
                "id": log.id,
                "message": log.message,
                "level": log.level,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

        return ApiResponse(
            success=True,
            message="Logs retrieved",
            data={
                "run_id": run_id,
                "logs": formatted_logs,
                "count": len(formatted_logs),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching backtest logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch logs: {str(e)}",
        )


@app.get("/api/v1/backtests/{run_id}/candles")
async def get_backtest_candles(
        run_id: str,
        market: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """
    Get historical candle data for backtest.

    Query Parameters:
    - market: Market symbol (optional - returns all if not specified)
    - start_date: Filter from date (optional, ISO format)
    - end_date: Filter to date (optional, ISO format)

    Returns candle data with OHLCV information.
    """
    try:
        # Find the backtest run
        run = BacktestRunService.get_run_by_run_id(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest run {run_id} not found",
            )

        # Parse dates if provided
        start_dt = None
        end_dt = None
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date must be ISO format (YYYY-MM-DD or ISO-8601)",
                )
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date must be ISO format (YYYY-MM-DD or ISO-8601)",
                )

        # Build query
        query = BacktestRunService.get_candles_by_run_id(run.id)

        if market:
            query = query.filter(BacktestCandle.market == market)

        if start_dt:
            query = query.filter(BacktestCandle.timestamp >= start_dt)

        if end_dt:
            query = query.filter(BacktestCandle.timestamp <= end_dt)

        candles = query.order_by(BacktestCandle.timestamp).all()

        # Get unique markets
        markets_result = (
            BacktestRunService.get_markets_by_run_id(run.id)
        )
        markets_list = [m[0] for m in markets_result]

        # Format candle data
        candles_data = [
            {
                "market": c.market,
                "timestamp": c.timestamp.isoformat() + "Z"
                if c.timestamp and c.timestamp.tzinfo is None
                else c.timestamp.isoformat()
                if c.timestamp
                else None,
                "open": float(c.open_price),
                "high": float(c.high_price),
                "low": float(c.low_price),
                "close": float(c.close_price),
                "volume": float(c.volume),
            }
            for c in candles
        ]

        return ApiResponse(
            success=True,
            message="Candles retrieved",
            data={
                "run_id": run_id,
                "candles": candles_data,
                "count": len(candles_data),
                "markets": markets_list,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching backtest candles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch candles: {str(e)}",
        )


# ==================== SETTINGS ENDPOINTS ====================


@app.get("/api/v1/settings/schema", response_model=ApiResponse)
async def get_settings_schema():
    """Get the schema/definition of all available settings."""
    try:
        schema = SettingsService.get_settings_schema()
        return ApiResponse(
            success=True,
            message="Settings schema retrieved",
            data=schema,
        )
    except Exception as e:
        logger.error(f"Error getting settings schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get("/api/v1/settings", response_model=ApiResponse)
async def get_settings(
        section: str = None,
):
    """Get current settings grouped by section."""
    try:
        all_settings = SettingsService.get_all_settings()

        # Filter by section if provided
        if section:
            all_settings["sections"] = [
                s for s in all_settings["sections"] if s["section"] == section
            ]

        return ApiResponse(
            success=True,
            message="Settings retrieved",
            data=all_settings,
        )
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.post("/api/v1/settings", response_model=ApiResponse)
async def update_settings(
        updates: dict,
        current_user: dict = Depends(get_current_user),
):
    """Update multiple settings at once.

    Request body: {"section.key": value, "section.key": value, ...}
    """
    try:
        # Update settings in database
        result = SettingsService.update_settings(updates)

        # Log the action
        AuditLogService.log_action(
            action="settings_update",
            resource_type="settings",
            user_id=current_user["user_id"],
            details=f"Updated {len(updates)} settings",
        )

        return ApiResponse(
            success=True,
            message="Settings updated successfully",
            data=result,
        )
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.post("/api/v1/settings/initialize", response_model=ApiResponse)
async def initialize_settings(
        current_user: dict = Depends(get_current_user),
):
    """Initialize default settings if they don't exist."""
    try:
        SettingsService.initialize_defaults()

        # Log the action
        AuditLogService.log_action(
            action="settings_initialize",
            resource_type="settings",
            user_id=current_user["user_id"],
            details="Initialized default settings",
        )

        return ApiResponse(
            success=True,
            message="Settings initialized",
        )
    except Exception as e:
        logger.error(f"Error initializing settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# ==================== STARTUP ====================


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8888,
        reload=False,
        log_level="info",
    )
