"""
FastAPI backend server for dYdX Backtest System.
Provides REST API and WebSocket for real-time backtest monitoring.
"""

# ⚠️ CRITICAL: Load environment variables FIRST, before any other imports
# This ensures DB_* environment variables are available to database.py
from dotenv import load_dotenv

load_dotenv()

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
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import (
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    create_access_token,
    create_refresh_token,
    extract_user_from_token,
    verify_token,
)
from backend.database import (
    BacktestCandle,
    BacktestLog,
    BacktestResult,
    BacktestRun,
    BacktestStrategy,
    TradeLog,
    User,
    get_db,
    init_db,
)
from backend.schemas import BacktestStrategyCreate, BacktestStrategyUpdate
from backend.services import (
    AuditLogService,
    BacktestResultService,
    BacktestRunService,
    BacktestStrategyService,
    UserService,
)
from backend.ws_broadcaster import BacktestProgressUpdate, get_broadcaster

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
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Startup/Shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown event handler."""
    # Startup
    logger.info("Starting dYdX Backtest API Server")
    init_db()
    logger.info("Database initialized")
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
            "timestamp": datetime.utcnow().isoformat(),
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
    db: Session = Depends(get_db),
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
        user = UserService.get_user_by_id(db, user_id_int)
    except (ValueError, TypeError):
        # Fall back to username lookup
        user = UserService.get_user_by_username(db, subject)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return {"user_id": user.id, "username": user.username, "is_admin": user.is_admin}


# ==================== AUTHENTICATION ENDPOINTS ====================


@app.post("/api/v1/auth/register", response_model=ApiResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register new user account."""
    try:
        user = UserService.create_user(
            db, user_data.username, user_data.email, user_data.password
        )
        AuditLogService.log_action(db, "user_registration", "user", None, user.id)
        return ApiResponse(
            success=True,
            message="User registered successfully",
            data={"user_id": user.id, "username": user.username},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/v1/auth/login", response_model=Token)
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT tokens."""
    user = UserService.authenticate_user(db, login_data.username, login_data.password)

    if not user:
        AuditLogService.log_action(
            db, "login_failed", "user", None, login_data.username, status="failure"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    AuditLogService.log_action(db, "login_success", "user", user.id, None)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,  # 30 minutes in seconds
    )


@app.post("/api/v1/auth/refresh", response_model=Token)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
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
    current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get current user profile."""
    user = UserService.get_user_by_id(db, current_user["user_id"])
    return user


@app.put("/api/v1/profile", response_model=ApiResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user profile (full_name, email, avatar)."""
    try:
        user = UserService.get_user_by_id(db, current_user["user_id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Update fields if provided
        if profile_data.full_name is not None:
            user.full_name = profile_data.full_name.strip()[:100]  # Max 100 chars

        if profile_data.email is not None:
            # Check if email is already taken by another user
            existing_user = (
                db.query(User)
                .filter(User.email == profile_data.email, User.id != user.id)
                .first()
            )
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use",
                )
            user.email = profile_data.email

        if profile_data.avatar is not None:
            user.avatar = profile_data.avatar

        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)

        # Log the action
        AuditLogService.log_action(
            db,
            action="profile_update",
            resource_type="user",
            user_id=user.id,
            details="Profile updated (full_name, email, avatar)",
        )

        return ApiResponse(
            success=True,
            message="Profile updated successfully",
            data={
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "avatar": user.avatar,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "created_at": user.created_at.isoformat()
                    if user.created_at is not None
                    else None,
                    "last_login": user.last_login.isoformat()
                    if user.last_login is not None
                    else None,
                }
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# ==================== BACKTEST ENDPOINTS ====================


@app.get("/api/v1/backtests")
async def list_backtests(
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List backtest runs for current user."""
    runs = BacktestRunService.get_user_runs(db, current_user["user_id"], skip, limit)
    return ApiResponse(
        success=True,
        message="Backtests retrieved",
        data={
            "backtests": [
                {
                    "id": run.id,
                    "run_id": run.run_id,
                    "status": run.status,
                    "created_at": run.created_at.isoformat(),
                    "duration_seconds": run.duration_seconds,
                    "total_pnl": run.total_pnl,
                    "total_trades": run.total_trades,
                    "win_rate": run.win_rate,
                }
                for run in runs
            ]
        },
    )


@app.get("/api/v1/backtests/{run_id}")
async def get_backtest(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get backtest details with trades and results."""
    run = BacktestRunService.get_run_by_run_id(db, run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found"
        )

    # Check authorization
    if run.user_id != current_user["user_id"] and not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    # Get all results for this backtest run
    results = db.query(BacktestResult).filter(BacktestResult.run_id_fk == run.id).all()

    # Format results with trades
    formatted_results = []
    all_trades = []
    for result in results:
        trades = (
            db.query(TradeLog)
            .filter(TradeLog.result_id_fk == result.id)
            .order_by(TradeLog.entry_timestamp)
            .all()
        )

        formatted_trades = []
        for trade in trades:
            formatted_trades.append(
                {
                    "trade_number": trade.trade_number,
                    "entry_timestamp": trade.entry_timestamp.isoformat()
                    if trade.entry_timestamp is not None
                    else None,
                    "exit_timestamp": trade.exit_timestamp.isoformat()
                    if trade.exit_timestamp is not None
                    else None,
                    "entry_price_1": trade.entry_price_1,
                    "entry_price_2": trade.entry_price_2,
                    "exit_price_1": trade.exit_price_1,
                    "exit_price_2": trade.exit_price_2,
                    "quantity_1": trade.quantity_1,
                    "quantity_2": trade.quantity_2,
                    "side_1": trade.side_1,
                    "side_2": trade.side_2,
                    "pnl": trade.pnl,
                    "pnl_usd": trade.pnl_usd,
                    "entry_zscore": trade.entry_zscore,
                    "exit_zscore": trade.exit_zscore,
                }
            )
            all_trades.append(formatted_trades[-1])

        formatted_results.append(
            {
                "market_1": result.market_1,
                "market_2": result.market_2,
                "total_trades": result.total_trades,
                "profitable_trades": result.profitable_trades,
                "win_rate": result.win_rate,
                "pnl": result.pnl,
                "pnl_usd": result.pnl_usd,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown": result.max_drawdown,
                "profit_factor": result.profit_factor,
                "trades": formatted_trades,
            }
        )

    return ApiResponse(
        success=True,
        message="Backtest retrieved",
        data={
            "id": run.id,
            "run_id": run.run_id,
            "status": run.status,
            "created_at": run.created_at.isoformat(),
            "start_date": run.start_date,
            "end_date": run.end_date,
            "num_pairs": run.num_pairs,
            "total_markets": run.total_markets,
            "duration_seconds": run.duration_seconds,
            "total_trades": run.total_trades,
            "profitable_trades": run.profitable_trades,
            "win_rate": run.win_rate,
            "total_pnl": run.total_pnl,
            "total_pnl_usd": run.total_pnl_usd,
            "sharpe_ratio": run.sharpe_ratio,
            "max_drawdown": run.max_drawdown,
            "profit_factor": run.profit_factor,
            "starting_balance": run.starting_balance,
            "ending_balance": run.ending_balance,
            "strategy_snapshot": run.strategy_snapshot,
            "strategy_version_id": run.strategy_version_id,
            "strategy_id": run.strategy_id,
            "results": formatted_results,
            "all_trades": all_trades,
        },
    )


@app.post("/api/v1/backtests/run")
async def run_backtest(
    request: BacktestStartRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
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
            strategy = (
                db.query(BacktestStrategy)
                .filter(BacktestStrategy.id == request.strategy_id)
                .first()
            )

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
            }

            logger.info(f"Using strategy {strategy.id} ({strategy.name})")

            # Update last_used_at timestamp
            strategy.last_used_at = datetime.utcnow()
            db.commit()
        else:
            # Use inline parameters
            strategy_params = {
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
            db,
            run_id=run_id,
            start_date=request.start_date,
            end_date=request.end_date,
            num_pairs=request.num_pairs or 10,
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
            _execute_backtest_task(run_id, request, db, strategy_params)
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
    db: Session,
    strategy_params: Optional[dict] = None,
):
    """Background task to execute backtest and create logs.

    Args:
        run_id: UUID of the backtest run
        request: Backtest start request parameters
        db: Database session
        strategy_params: Optional strategy parameters to override config
    """
    import logging
    import os
    import sys
    from datetime import datetime

    # Add app directory to path BEFORE importing app modules
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

    from config import config
    from func_backtest_logging import log_backtest_error, log_backtest_info
    from func_backtesting import BacktestEngine
    from func_connections import connect_dydx
    from logging_setup import setup_logging

    # Initialize logging for this background task
    setup_logging()
    task_logger = logging.getLogger(__name__)
    task_logger.info(f"Background task started for backtest {run_id}")

    # ========== FIX: Force reimport of services module to access new methods ==========
    # This ensures BacktestRunService has the latest methods (find_cached_backtest, aggregate_run_metrics)
    import importlib

    import backend.services

    importlib.reload(backend.services)
    from backend.services import BacktestResultService

    try:
        log_backtest_info(run_id, "Backtest execution started", db)

        # Get the integer ID from the database
        run_record = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
        if not run_record:
            log_backtest_error(run_id, "BacktestRun record not found in database", db)
            raise ValueError(f"BacktestRun with run_id {run_id} not found")

        run_id_int = run_record.id  # Direct integer value
        log_backtest_info(
            run_id, f"Backtest execution started (DB ID: {run_id_int})", db
        )

        # Load configuration
        cfg = config()
        log_backtest_info(run_id, "Configuration loaded", db)

        # ========== NEW: Apply Strategy Parameters ==========
        if strategy_params:
            # Override config.botSettings with strategy parameters
            for param, value in strategy_params.items():
                if hasattr(cfg.botSettings, param):
                    setattr(cfg.botSettings, param, value)
            log_backtest_info(
                run_id,
                f"Strategy parameters applied ({len(strategy_params)} overrides)",
                db,
            )

        # ========== CACHE-FIRST CHECK: Look for matching completed backtest ==========
        log_backtest_info(run_id, "Checking for cached backtest results...", db)

        # Build strategy snapshot for comparison
        strategy_snapshot = {}
        if strategy_params:
            strategy_snapshot = strategy_params.copy()

        # Create hashable strategy representation for comparison
        strategy_snapshot_for_query = strategy_snapshot if strategy_snapshot else None

        # Look for cached backtest with identical parameters
        cached_run = BacktestResultService.find_cached_backtest(
            db,
            request.start_date,
            request.end_date,
            request.num_pairs or 10,
            strategy_snapshot_for_query,
        )

        if cached_run and cached_run.status == "completed":
            log_backtest_info(
                run_id,
                f"Found cached backtest result from {cached_run.created_at}. Using cached data...",
                db,
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
                    db,
                )

                # Mark as completed and return early
                run_record.status = "completed"
                run_record.completed_at = datetime.now(timezone.utc)
                db.commit()

                log_backtest_info(run_id, "Backtest completed using cached results", db)
                return  # Exit early - no need to run backtest

        # ========== NO CACHE: Proceed with regular backtest execution ==========

        # Connect to dYdX client
        try:
            client = await connect_dydx()
            log_backtest_info(run_id, "Connected to dYdX API", db)
        except Exception as e:
            log_backtest_error(run_id, f"Failed to connect to dYdX: {str(e)}", db)
            raise

        # Create backtest engine with logging (pass integer ID for database operations)
        engine = BacktestEngine(
            client, cfg, run_id=run_id, run_id_int=run_id_int, db=db
        )  # type: ignore
        log_backtest_info(run_id, "Backtest engine initialized", db)

        # Run backtest in a thread pool to avoid blocking the event loop
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)
        num_pairs = request.num_pairs or 10

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

        log_backtest_info(run_id, "Backtest execution completed successfully", db)

        # ========== AGGREGATE METRICS FROM TRADES ==========
        run_record = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
        if run_record:
            BacktestResultService.aggregate_run_metrics(db, run_record.id)
            log_backtest_info(
                run_id,
                f"Metrics aggregated - {run_record.total_trades} trades, "
                f"${run_record.total_pnl:.2f} PnL, {run_record.win_rate:.1f}% win rate",
                db,
            )

        # ========== UPDATE STATUS TO COMPLETED ==========
        run_record = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
        if run_record:
            run_record.status = "completed"
            run_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Backtest {run_id} marked as completed in database")

    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        log_backtest_error(run_id, f"Backtest execution failed: {str(e)}", db)

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
    current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get backtest statistics."""
    stats = BacktestRunService.get_run_stats(db)
    return ApiResponse(success=True, message="Statistics retrieved", data=stats)


@app.get("/api/v1/backtests/{run_id}/logs")
async def get_backtest_logs(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get logs for a specific backtest run."""
    try:
        # Find the backtest run
        run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest run {run_id} not found",
            )

        # Get logs for this run, ordered by creation time
        logs = (
            db.query(BacktestLog)
            .filter(BacktestLog.run_id_fk == run.id)
            .order_by(BacktestLog.created_at.asc())
            .all()
        )

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
    db: Session = Depends(get_db),
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
        run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
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
        query = db.query(BacktestCandle).filter(BacktestCandle.run_id_fk == run.id)

        if market:
            query = query.filter(BacktestCandle.market == market)

        if start_dt:
            query = query.filter(BacktestCandle.timestamp >= start_dt)

        if end_dt:
            query = query.filter(BacktestCandle.timestamp <= end_dt)

        candles = query.order_by(BacktestCandle.timestamp).all()

        # Get unique markets
        markets_result = (
            db.query(BacktestCandle.market)
            .filter(BacktestCandle.run_id_fk == run.id)
            .distinct()
            .all()
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


@app.get("/api/v1/settings/schema")
async def get_settings_schema(
    current_user: dict = Depends(get_current_user),
):
    """Get settings schema for UI generation."""
    # Define complete settings schema matching config.yaml structure
    schema = {
        "sections": [
            {
                "section": "botSettings",
                "title": "Bot Settings",
                "description": "Core trading bot configuration",
                "fields": [
                    {
                        "key": "ZScoreThreshold",
                        "label": "Z-Score Threshold",
                        "description": "Entry trigger when |Z-score| exceeds this value",
                        "value_type": "float",
                        "default_value": 1.5,
                        "required": True,
                        "min_value": 0.5,
                        "max_value": 3.0,
                    },
                    {
                        "key": "statsWindow",
                        "label": "Stats Window (days)",
                        "description": "Rolling window for Z-score calculation",
                        "value_type": "int",
                        "default_value": 21,
                        "required": True,
                        "min_value": 5,
                        "max_value": 100,
                    },
                    {
                        "key": "maxHalfLife",
                        "label": "Max Half-Life (hours)",
                        "description": "Maximum half-life for cointegration pairs",
                        "value_type": "int",
                        "default_value": 24,
                        "required": True,
                        "min_value": 1,
                        "max_value": 168,
                    },
                    {
                        "key": "usdPerTrade",
                        "label": "USD Per Trade",
                        "description": "Position size per trade in USD",
                        "value_type": "float",
                        "default_value": 10.0,
                        "required": True,
                        "min_value": 1.0,
                        "max_value": 10000.0,
                    },
                    {
                        "key": "usdMinCollateral",
                        "label": "Min Collateral (USD)",
                        "description": "Minimum account balance required",
                        "value_type": "float",
                        "default_value": 100.0,
                        "required": True,
                        "min_value": 50.0,
                        "max_value": 100000.0,
                    },
                    {
                        "key": "closeAtZscoreCross",
                        "label": "Close at Z-Score Cross",
                        "description": "Exit positions when Z-score crosses zero",
                        "value_type": "boolean",
                        "default_value": True,
                        "required": True,
                    },
                    {
                        "key": "abortAllPositions",
                        "label": "Abort All Positions",
                        "description": "Close all positions on startup",
                        "value_type": "boolean",
                        "default_value": False,
                        "required": False,
                    },
                    {
                        "key": "findCointegratedPairs",
                        "label": "Find Cointegrated Pairs",
                        "description": "Run statistical analysis for cointegration",
                        "value_type": "boolean",
                        "default_value": True,
                        "required": True,
                    },
                    {
                        "key": "placeTrades",
                        "label": "Place Trades",
                        "description": "Execute new trade orders",
                        "value_type": "boolean",
                        "default_value": True,
                        "required": True,
                    },
                    {
                        "key": "manageExits",
                        "label": "Manage Exits",
                        "description": "Monitor and close existing positions",
                        "value_type": "boolean",
                        "default_value": True,
                        "required": True,
                    },
                ],
            },
            {
                "section": "backtesting",
                "title": "Backtesting",
                "description": "Historical simulation parameters",
                "fields": [
                    {
                        "key": "candleResolution",
                        "label": "Candle Resolution",
                        "description": "Candle timeframe for analysis",
                        "value_type": "string",
                        "default_value": "1HOUR",
                        "required": True,
                        "options": [
                            "1MIN",
                            "5MINS",
                            "15MINS",
                            "1HOUR",
                            "4HOURS",
                            "1DAY",
                        ],
                    },
                    {
                        "key": "maxHistoryDays",
                        "label": "Max History (days)",
                        "description": "Maximum lookback period",
                        "value_type": "int",
                        "default_value": 90,
                        "required": True,
                        "min_value": 7,
                        "max_value": 365,
                    },
                    {
                        "key": "startingBalance",
                        "label": "Starting Balance (USD)",
                        "description": "Initial capital for simulation",
                        "value_type": "float",
                        "default_value": 1000.0,
                        "required": True,
                        "min_value": 100.0,
                        "max_value": 1000000.0,
                    },
                    {
                        "key": "transactionFee",
                        "label": "Transaction Fee",
                        "description": "Fee per transaction (0.0005 = 0.05%)",
                        "value_type": "float",
                        "default_value": 0.0005,
                        "required": True,
                        "min_value": 0.0,
                        "max_value": 0.01,
                    },
                    {
                        "key": "slippage",
                        "label": "Slippage",
                        "description": "Estimated slippage per trade",
                        "value_type": "float",
                        "default_value": 0.001,
                        "required": True,
                        "min_value": 0.0,
                        "max_value": 0.1,
                    },
                    {
                        "key": "benchmarkSymbol",
                        "label": "Benchmark Symbol",
                        "description": "Market for Sharpe ratio calculation",
                        "value_type": "string",
                        "default_value": "BTC-USD",
                        "required": False,
                    },
                    {
                        "key": "riskFreeRate",
                        "label": "Risk-Free Rate",
                        "description": "Annual risk-free rate (0.02 = 2%)",
                        "value_type": "float",
                        "default_value": 0.02,
                        "required": True,
                        "min_value": 0.0,
                        "max_value": 0.1,
                    },
                ],
            },
            {
                "section": "logging",
                "title": "Logging",
                "description": "Log level and Loki integration",
                "fields": [
                    {
                        "key": "level",
                        "label": "Log Level",
                        "description": "Logging verbosity",
                        "value_type": "string",
                        "default_value": "INFO",
                        "required": True,
                        "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                    },
                    {
                        "key": "lokiEnabled",
                        "label": "Enable Loki",
                        "description": "Send logs to Loki server",
                        "value_type": "boolean",
                        "default_value": False,
                        "required": False,
                    },
                    {
                        "key": "lokiUrl",
                        "label": "Loki URL",
                        "description": "Loki server endpoint",
                        "value_type": "string",
                        "default_value": "http://localhost:3100",
                        "required": False,
                        "placeholder": "http://localhost:3100",
                    },
                ],
            },
            {
                "section": "telegram",
                "title": "Telegram Notifications",
                "description": "Real-time trade and error alerts",
                "fields": [
                    {
                        "key": "enabled",
                        "label": "Enable Telegram",
                        "description": "Send notifications to Telegram",
                        "value_type": "boolean",
                        "default_value": False,
                        "required": False,
                    },
                    {
                        "key": "chatId",
                        "label": "Chat ID",
                        "description": "Telegram chat ID for messages",
                        "value_type": "string",
                        "required": False,
                        "placeholder": "123456789",
                    },
                    {
                        "key": "token",
                        "label": "Bot Token",
                        "description": "Telegram bot token",
                        "value_type": "string",
                        "required": False,
                        "placeholder": "Your bot token",
                    },
                ],
            },
            {
                "section": "dydx",
                "title": "dYdX Connection",
                "description": "Blockchain and exchange configuration",
                "fields": [
                    {
                        "key": "isTestnet",
                        "label": "Use Testnet",
                        "description": "Connect to testnet or mainnet",
                        "value_type": "boolean",
                        "default_value": True,
                        "required": True,
                    },
                    {
                        "key": "chainId",
                        "label": "Chain ID",
                        "description": "dYdX chain identifier",
                        "value_type": "string",
                        "default_value": "dydx-testnet-1",
                        "required": True,
                        "options": ["dydx-testnet-1", "dydx-mainnet-1"],
                    },
                    {
                        "key": "mnemonicSecretKey",
                        "label": "Secret Phrase (Mnemonic)",
                        "description": "BIP39 mnemonic seed phrase",
                        "value_type": "string",
                        "required": False,
                        "placeholder": "Your 12 or 24-word mnemonic...",
                    },
                ],
            },
        ]
    }
    return ApiResponse(success=True, message="Settings schema retrieved", data=schema)


@app.post("/api/v1/settings/initialize")
async def initialize_settings(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initialize default settings in database if not already present."""
    import json

    from backend.database import BotSetting

    # Define default settings matching the schema
    default_settings = [
        # Bot Settings section
        (
            "botSettings",
            "ZScoreThreshold",
            1.5,
            "float",
            "Entry trigger when |Z-score| exceeds this value",
        ),
        (
            "botSettings",
            "statsWindow",
            21,
            "int",
            "Rolling window for Z-score calculation",
        ),
        (
            "botSettings",
            "maxHalfLife",
            24,
            "int",
            "Maximum half-life for cointegration pairs",
        ),
        ("botSettings", "usdPerTrade", 10.0, "float", "Position size per trade in USD"),
        (
            "botSettings",
            "usdMinCollateral",
            100.0,
            "float",
            "Minimum account balance required",
        ),
        (
            "botSettings",
            "closeAtZscoreCross",
            True,
            "boolean",
            "Exit positions when Z-score crosses zero",
        ),
        (
            "botSettings",
            "abortAllPositions",
            False,
            "boolean",
            "Close all positions on startup",
        ),
        (
            "botSettings",
            "findCointegratedPairs",
            True,
            "boolean",
            "Run statistical analysis for cointegration",
        ),
        ("botSettings", "placeTrades", True, "boolean", "Execute new trade orders"),
        (
            "botSettings",
            "manageExits",
            True,
            "boolean",
            "Monitor and close existing positions",
        ),
    ]

    created_count = 0
    for section, key, default_value, value_type, description in default_settings:
        # Check if setting already exists
        existing = (
            db.query(BotSetting)
            .filter(
                BotSetting.section == section,
                BotSetting.key == key,
            )
            .first()
        )

        if not existing:
            # Create new setting with default value
            new_setting = BotSetting(
                section=section,
                key=key,
                value=json.dumps(default_value)
                if value_type == "json"
                else str(default_value),
                value_type=value_type,
                description=description,
                default_value=str(default_value),
                is_active=True,
            )
            db.add(new_setting)
            created_count += 1

    db.commit()

    return ApiResponse(
        success=True,
        message=f"Settings initialized. Created {created_count} new settings.",
        data={"created_count": created_count},
    )


@app.get("/api/v1/settings")
async def get_settings(
    section: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get bot settings from database, grouped by section."""
    from backend.database import BotSetting

    query = db.query(BotSetting).filter(BotSetting.is_active)

    if section:
        query = query.filter(BotSetting.section == section)

    settings = query.all()

    # If database is empty, return schema defaults
    if not settings:
        # Get schema defaults
        schema = {
            "sections": [
                {
                    "section": "botSettings",
                    "title": "Bot Settings",
                    "description": "Core trading bot configuration",
                    "fields": [
                        {
                            "key": "ZScoreThreshold",
                            "default_value": 1.5,
                            "value_type": "float",
                        },
                        {
                            "key": "statsWindow",
                            "default_value": 21,
                            "value_type": "int",
                        },
                        {
                            "key": "maxHalfLife",
                            "default_value": 24,
                            "value_type": "int",
                        },
                        {
                            "key": "usdPerTrade",
                            "default_value": 10.0,
                            "value_type": "float",
                        },
                        {
                            "key": "usdMinCollateral",
                            "default_value": 100.0,
                            "value_type": "float",
                        },
                        {
                            "key": "closeAtZscoreCross",
                            "default_value": True,
                            "value_type": "boolean",
                        },
                        {
                            "key": "abortAllPositions",
                            "default_value": False,
                            "value_type": "boolean",
                        },
                        {
                            "key": "findCointegratedPairs",
                            "default_value": True,
                            "value_type": "boolean",
                        },
                        {
                            "key": "placeTrades",
                            "default_value": True,
                            "value_type": "boolean",
                        },
                        {
                            "key": "manageExits",
                            "default_value": True,
                            "value_type": "boolean",
                        },
                    ],
                }
            ]
        }

        sections_response = []
        for schema_section in schema["sections"]:
            section_data = {
                "section": schema_section["section"],
                "settings": [
                    {
                        "id": 0,
                        "key": field["key"],
                        "value": field["default_value"],
                        "value_type": field["value_type"],
                        "description": "",
                        "default_value": field["default_value"],
                        "is_active": True,
                        "version": 1,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                    for field in schema_section["fields"]
                ],
            }
            sections_response.append(section_data)

        return ApiResponse(
            success=True,
            message="Settings retrieved (using defaults)",
            data={"sections": sections_response},
        )

    # Group by section
    grouped = {}
    for setting in settings:
        if setting.section not in grouped:
            grouped[setting.section] = []
        grouped[setting.section].append(
            {
                "id": setting.id,
                "key": setting.key,
                "value": setting.value,
                "value_type": setting.value_type,
                "description": setting.description,
                "default_value": setting.default_value,
                "is_active": setting.is_active,
                "version": setting.version,
                "updated_at": setting.updated_at.isoformat(),
            }
        )

    sections = [
        {"section": section_name, "settings": section_settings}
        for section_name, section_settings in grouped.items()
    ]

    return ApiResponse(
        success=True,
        message="Settings retrieved",
        data={"sections": sections},
    )


@app.post("/api/v1/settings")
async def update_settings(
    updates: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update bot settings (batch update)."""
    import json

    from backend.database import BotSetting

    updated_count = 0
    errors: List[str] = []

    # Parse updates: can be {section.key: value} or {section: {key: value}}
    flat_updates = {}

    for key, value in updates.items():
        if "." in key:
            flat_updates[key] = value
        else:
            # Nested format
            if isinstance(value, dict):
                for k, v in value.items():
                    flat_updates[f"{key}.{k}"] = v
            else:
                flat_updates[key] = value

    for key_path, value in flat_updates.items():
        try:
            section, key = key_path.rsplit(".", 1)

            # Find existing setting
            setting = (
                db.query(BotSetting)
                .filter(
                    BotSetting.section == section,
                    BotSetting.key == key,
                    BotSetting.is_active,
                )
                .first()
            )

            # Determine value type (from existing setting or infer from value)
            if setting:
                value_type = setting.value_type
            else:
                # Infer type from value
                if isinstance(value, bool):
                    value_type = "boolean"
                elif isinstance(value, int):
                    value_type = "int"
                elif isinstance(value, float):
                    value_type = "float"
                else:
                    value_type = "string"

            # Validate type conversion
            if value_type == "float":
                value = float(value)
            elif value_type == "int":
                value = int(value)
            elif value_type == "boolean":
                value = str(value).lower() in ["true", "1", "yes"]

            # Update existing or create new setting
            if setting:
                setting.value = (
                    json.dumps(value) if value_type == "json" else str(value)
                )
                setting.updated_by = current_user["user_id"]
                setting.version += 1
                setting.updated_at = datetime.utcnow()
            else:
                # Create new setting
                setting = BotSetting(
                    section=section,
                    key=key,
                    value=json.dumps(value) if value_type == "json" else str(value),
                    value_type=value_type,
                    description="",
                    default_value=str(value),
                    is_active=True,
                    updated_by=current_user["user_id"],
                )
                db.add(setting)

            updated_count += 1
        except Exception as e:
            errors.append(f"Error updating {key_path}: {str(e)}")

    db.commit()

    response_data: dict = {
        "updated": updated_count,
        "total": len(flat_updates),
    }

    if errors:
        response_data["errors"] = errors  # type: ignore

    return ApiResponse(
        success=len(errors) == 0,
        message=f"Updated {updated_count} settings"
        if updated_count > 0
        else "No settings updated",
        data=response_data,
    )


# ==================== ANALYSIS ENDPOINTS ====================


@app.get("/api/v1/backtests/{run_id}/trades")
async def get_backtest_trades(
    run_id: str,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed trades from a backtest."""
    from backend.database import BacktestTrade

    # Get run
    run = BacktestRunService.get_run_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    # Check authorization
    if run.user_id != current_user["user_id"] and not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get trades
    trades = (
        db.query(BacktestTrade)
        .filter(BacktestTrade.run_id_fk == run.id)
        .order_by(BacktestTrade.entry_timestamp.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = db.query(BacktestTrade).filter(BacktestTrade.run_id_fk == run.id).count()

    formatted_trades = []
    for trade in trades:
        formatted_trades.append(
            {
                "id": trade.id,
                "trade_id": trade.trade_id,
                "market_1": trade.market_1,
                "market_2": trade.market_2,
                "entry_timestamp": trade.entry_timestamp.isoformat(),
                "exit_timestamp": trade.exit_timestamp.isoformat()
                if trade.exit_timestamp is not None
                else None,
                "entry_price_1": trade.entry_price_1,
                "entry_price_2": trade.entry_price_2,
                "exit_price_1": trade.exit_price_1,
                "exit_price_2": trade.exit_price_2,
                "entry_z_score": trade.entry_z_score,
                "exit_z_score": trade.exit_z_score,
                "side_1": trade.side_1,
                "side_2": trade.side_2,
                "size_1": trade.size_1,
                "size_2": trade.size_2,
                "pnl": trade.pnl,
                "pnl_pct": trade.pnl_pct,
                "duration_hours": trade.duration_hours,
            }
        )

    return ApiResponse(
        success=True,
        message="Trades retrieved",
        data={
            "run_id": run_id,
            "trades": formatted_trades,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    )


@app.get("/api/v1/backtests/{run_id}/positions")
async def get_backtest_positions(
    run_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get position history from a backtest."""
    from backend.database import BacktestPosition

    # Get run
    run = BacktestRunService.get_run_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    # Check authorization
    if run.user_id != current_user["user_id"] and not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get positions
    query = db.query(BacktestPosition).filter(BacktestPosition.run_id_fk == run.id)

    if status:
        query = query.filter(BacktestPosition.status == status)

    positions = (
        query.order_by(BacktestPosition.entry_timestamp.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = query.count()

    formatted_positions = []
    for position in positions:
        formatted_positions.append(
            {
                "id": position.id,
                "position_id": position.position_id,
                "market_1": position.market_1,
                "market_2": position.market_2,
                "status": position.status,
                "entry_timestamp": position.entry_timestamp.isoformat(),
                "close_timestamp": position.close_timestamp.isoformat()
                if position.close_timestamp is not None
                else None,
                "entry_price_1": position.entry_price_1,
                "entry_price_2": position.entry_price_2,
                "current_price_1": position.current_price_1,
                "current_price_2": position.current_price_2,
                "size_1": position.size_1,
                "size_2": position.size_2,
                "side_1": position.side_1,
                "side_2": position.side_2,
                "unrealized_pnl": position.unrealized_pnl,
                "realized_pnl": position.realized_pnl,
            }
        )

    return ApiResponse(
        success=True,
        message="Positions retrieved",
        data={
            "run_id": run_id,
            "positions": formatted_positions,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    )


# ==================== TASK 17: ANALYTICS ENDPOINTS ====================


@app.get("/api/v1/backtests/{run_id}/performance")
async def get_backtest_performance(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get comprehensive performance metrics for a backtest."""
    from backend.database import BacktestTrade

    # Get run
    run = BacktestRunService.get_run_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    # Check authorization
    if run.user_id != current_user["user_id"] and not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Query all trades for this run
    trades = db.query(BacktestTrade).filter(BacktestTrade.run_id_fk == run.id).all()

    if not trades:
        return ApiResponse(
            success=True,
            message="Performance metrics retrieved",
            data={
                "run_id": run_id,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "average_pnl": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "average_duration": 0.0,
            },
        )

    # Extract numeric values from trades
    pnl_values = []
    for t in trades:
        pnl = getattr(t, "pnl", None)
        if pnl is not None:
            pnl_values.append(float(pnl))  # type: ignore
        else:
            pnl_values.append(0.0)

    # Calculate metrics
    import statistics

    total_trades = len(trades)
    winning_trades = sum(1 for p in pnl_values if p > 0)
    losing_trades = sum(1 for p in pnl_values if p < 0)
    total_pnl = sum(pnl_values)
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0
    max_win = max(pnl_values) if pnl_values else 0.0
    max_loss = min(pnl_values) if pnl_values else 0.0
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

    # Calculate Sharpe ratio
    if len(pnl_values) > 1:
        std_dev = statistics.stdev(pnl_values)
        sharpe_ratio = (avg_pnl / std_dev) if std_dev > 0 else 0.0
    else:
        sharpe_ratio = 0.0

    # Calculate max drawdown
    cumulative_pnl = 0
    peak = 0
    max_dd = 0
    for pnl in pnl_values:
        cumulative_pnl += pnl
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        drawdown = peak - cumulative_pnl
        if drawdown > max_dd:
            max_dd = drawdown

    max_drawdown = max_dd

    # Average trade duration
    durations = []
    for t in trades:
        duration = getattr(t, "duration_hours", None)
        if duration is not None:
            durations.append(float(duration))  # type: ignore
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    return ApiResponse(
        success=True,
        message="Performance metrics retrieved",
        data={
            "run_id": run_id,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": float(round(win_rate, 2)),
            "total_pnl": float(round(total_pnl, 2)),
            "average_pnl": float(round(avg_pnl, 2)),
            "max_win": float(round(max_win, 2)),
            "max_loss": float(round(max_loss, 2)),
            "sharpe_ratio": float(round(sharpe_ratio, 4)),
            "max_drawdown": float(round(max_drawdown, 2)),
            "average_duration": float(round(avg_duration, 2)),
        },
    )


@app.get("/api/v1/backtests/{run_id}/trades/{trade_id}")
async def get_backtest_trade_detail(
    run_id: str,
    trade_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific trade."""
    from backend.database import BacktestTrade

    # Get run
    run = BacktestRunService.get_run_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    # Check authorization
    if run.user_id != current_user["user_id"] and not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get trade
    trade = (
        db.query(BacktestTrade)
        .filter(BacktestTrade.run_id_fk == run.id, BacktestTrade.id == trade_id)
        .first()
    )

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

        return ApiResponse(
            success=True,
            message="Trade details retrieved",
            data={
                "id": trade.id,
                "trade_id": trade.trade_id,
                "run_id": run_id,
                "market_1": trade.market_1,
                "market_2": trade.market_2,
                "entry_timestamp": trade.entry_timestamp.isoformat(),
                "exit_timestamp": trade.exit_timestamp.isoformat()
                if trade.exit_timestamp is not None
                else None,  # type: ignore
                "entry_price_1": trade.entry_price_1,
                "entry_price_2": trade.entry_price_2,
                "exit_price_1": trade.exit_price_1,
                "exit_price_2": trade.exit_price_2,
                "entry_z_score": trade.entry_z_score,
                "exit_z_score": trade.exit_z_score,
                "side_1": trade.side_1,
                "side_2": trade.side_2,
                "size_1": trade.size_1,
                "size_2": trade.size_2,
                "hedge_ratio": trade.hedge_ratio,
                "pnl": trade.pnl,
                "pnl_pct": trade.pnl_pct,
                "duration_hours": trade.duration_hours,
                "transaction_fee": trade.transaction_fee,
                "slippage": trade.slippage,
            },
        )


@app.get("/api/v1/backtests/{run_id}/summary")
async def get_backtest_summary(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get summary statistics for a backtest run."""
    from backend.database import BacktestTrade

    # Get run
    run = BacktestRunService.get_run_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    # Check authorization
    if run.user_id != current_user["user_id"] and not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Count trades
    total_trades = (
        db.query(BacktestTrade).filter(BacktestTrade.run_id_fk == run.id).count()
    )

    # Get date range
    trades = db.query(BacktestTrade).filter(BacktestTrade.run_id_fk == run.id).all()

    if trades:
        earliest_date = min(t.entry_timestamp for t in trades)
        latest_date = max(t.exit_timestamp or t.entry_timestamp for t in trades)
    else:
        earliest_date = None
        latest_date = None

    return ApiResponse(
        success=True,
        message="Backtest summary retrieved",
        data={
            "run_id": run_id,
            "status": run.status,
            "created_at": run.created_at.isoformat(),
            "started_at": run.started_at.isoformat()
            if run.started_at is not None
            else None,  # type: ignore
            "completed_at": run.completed_at.isoformat()
            if run.completed_at is not None
            else None,  # type: ignore
            "total_trades": total_trades,
            "earliest_trade_date": earliest_date.isoformat()
            if earliest_date is not None
            else None,  # type: ignore
            "latest_trade_date": latest_date.isoformat()
            if latest_date is not None
            else None,  # type: ignore
            "configuration": {
                "num_pairs": getattr(run, "num_pairs", None),
                "zscore_threshold": getattr(run, "zscore_threshold", None),
                "stats_window": getattr(run, "stats_window", None),
                "usd_per_trade": getattr(run, "usd_per_trade", None),
            },
        },
    )


# ==================== BACKTEST RESULTS ENDPOINTS ====================


@app.get("/api/v1/backtests/{run_id}/results")
async def get_backtest_results(
    run_id: str,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "pnl",
    sort_order: str = "desc",
    min_win_rate: Optional[float] = None,
    min_trades: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed results for each pair tested in a backtest with enhanced filtering and validation.

    Args:
        run_id: UUID of the backtest run
        limit: Maximum results to return (default 20, max 100)
        offset: Number of results to skip for pagination (default 0)
        sort_by: Field to sort by (pnl, win_rate, sharpe_ratio, total_trades, profit_factor)
        sort_order: Sort order (desc or asc)
        min_win_rate: Filter results with win rate >= this value (0-100)
        min_trades: Filter results with total_trades >= this value
        current_user: Current authenticated user
        db: Database session

    Returns:
        ApiResponse with paginated list of pair results including validation metadata
    """
    # Get run
    run = BacktestRunService.get_run_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    # Check authorization
    if run.user_id != current_user["user_id"] and not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate and sanitize parameters
    limit = min(int(limit), 100)  # Cap at 100 results per page
    offset = max(int(offset), 0)

    # Validate sort field
    valid_sorts = [
        "pnl",
        "pnl_usd",
        "win_rate",
        "sharpe_ratio",
        "total_trades",
        "profit_factor",
        "avg_trade_duration_hours",
        "cointegration_score",
    ]
    if sort_by not in valid_sorts:
        sort_by = "pnl"

    # Build query
    query = db.query(BacktestResult).filter(BacktestResult.run_id_fk == run.id)

    # Apply filters
    if min_win_rate is not None:
        try:
            min_win_rate_val = float(min_win_rate)
            if 0 <= min_win_rate_val <= 100:
                query = query.filter(BacktestResult.win_rate >= min_win_rate_val)
        except (ValueError, TypeError):
            pass

    if min_trades is not None:
        try:
            min_trades_val = int(min_trades)
            if min_trades_val > 0:
                query = query.filter(BacktestResult.total_trades >= min_trades_val)
        except (ValueError, TypeError):
            pass

    # Get total count before applying limit/offset
    total_count = query.count()

    # Apply sorting
    sort_column = getattr(BacktestResult, sort_by, BacktestResult.pnl)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Get paginated results
    results = query.offset(offset).limit(limit).all()

    # Format results
    formatted_results = []
    for result in results:
        formatted_results.append(
            {
                "id": result.id,
                "pair": f"{result.market_1}/{result.market_2}",
                "market_1": result.market_1,
                "market_2": result.market_2,
                "total_trades": result.total_trades or 0,
                "profitable_trades": result.profitable_trades or 0,
                "losing_trades": result.losing_trades or 0,
                "win_rate": float(result.win_rate or 0),
                "pnl": float(result.pnl or 0),
                "pnl_usd": float(result.pnl_usd or 0),
                "avg_win": float(result.avg_win or 0),
                "avg_loss": float(result.avg_loss or 0),
                "profit_factor": float(result.profit_factor or 0),
                "max_drawdown": float(result.max_drawdown or 0),
                "sharpe_ratio": float(result.sharpe_ratio)
                if result.sharpe_ratio
                else None,
                "sortino_ratio": float(result.sortino_ratio)
                if result.sortino_ratio
                else None,
                "calmar_ratio": float(result.calmar_ratio)
                if result.calmar_ratio
                else None,
                "avg_trade_duration_hours": float(result.avg_trade_duration_hours or 0),
                "cointegration_score": float(result.cointegration_score or 0),
                "correlation": float(result.correlation or 0),
                "zscore_mean": float(result.zscore_mean or 0),
                "zscore_std": float(result.zscore_std or 0),
                "created_at": result.created_at.isoformat(),
            }
        )

    # Validate results quality
    from backend.services import validate_results_quality

    data_quality = validate_results_quality(results)

    # Calculate pagination metadata
    pages_count = (total_count + limit - 1) // limit if limit > 0 else 1
    current_page = (offset // limit) + 1 if limit > 0 else 1

    return ApiResponse(
        success=True,
        message=f"Retrieved {len(formatted_results)} results",
        data={
            "results": formatted_results,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "returned": len(formatted_results),
                "pages": pages_count,
                "current_page": current_page,
            },
            "metadata": {
                "run_id": run.run_id,
                "status": run.status,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
            "data_quality": data_quality,
        },
    )


@app.get("/api/v1/backtests/{run_id}/results/by-strategy")
async def get_results_by_strategy(
    run_id: str,
    strategy_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get results filtered by strategy.

    Args:
        run_id: UUID of the backtest run
        strategy_id: Filter results by strategy ID (optional)
        limit: Maximum results to return
        offset: Number of results to skip
        current_user: Current authenticated user
        db: Database session

    Returns:
        ApiResponse with strategy-filtered results
    """

    # Get run
    run = BacktestRunService.get_run_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    # Check authorization
    if run.user_id != current_user["user_id"] and not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Use strategy from run if not provided
    effective_strategy_id = strategy_id or run.strategy_id
    if not effective_strategy_id:
        raise HTTPException(
            status_code=400,
            detail="No strategy associated with this backtest. Provide strategy_id parameter.",
        )

    # Get results using service helper
    results = BacktestResultService.get_results_by_strategy(
        db, effective_strategy_id, skip=offset, limit=limit
    )

    total = len(
        BacktestResultService.get_results_by_strategy(
            db, effective_strategy_id, skip=0, limit=999999
        )
    )

    formatted_results = []
    for result in results:
        formatted_results.append(
            {
                "id": result.id,
                "market_1": result.market_1,
                "market_2": result.market_2,
                "total_trades": result.total_trades,
                "pnl": result.pnl,
                "win_rate": result.win_rate,
                "sharpe_ratio": result.sharpe_ratio,
                "profit_factor": result.profit_factor,
            }
        )

    return ApiResponse(
        success=True,
        message="Strategy results retrieved",
        data={
            "strategy_id": effective_strategy_id,
            "results": formatted_results,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "returned": len(formatted_results),
            },
        },
    )


@app.get("/api/v1/strategies/{strategy_id}/performance")
async def get_strategy_performance(
    strategy_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get aggregate performance metrics for a strategy across all backtests.

    Args:
        strategy_id: ID of the strategy
        current_user: Current authenticated user
        db: Database session

    Returns:
        ApiResponse with aggregated performance summary
    """
    # Verify strategy exists and user has access
    strategy = BacktestStrategyService.get_strategy_by_id(db, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Check authorization (public strategies visible to all, private only to owner)
    if (
        not strategy.is_public
        and strategy.user_id != current_user["user_id"]
        and not current_user["is_admin"]
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to view this strategy"
        )

    # Get performance summary
    summary = BacktestResultService.get_strategy_performance_summary(db, strategy_id)

    return ApiResponse(
        success=True,
        message="Strategy performance retrieved",
        data={
            "strategy_id": strategy_id,
            "strategy_name": strategy.name,
            "performance": summary,
            "description": strategy.description,
            "category": strategy.category,
        },
    )


@app.get("/api/v1/strategies/{strategy_id}/results")
async def get_strategy_all_results(
    strategy_id: int,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all backtest results for a strategy.

    Args:
        strategy_id: ID of the strategy
        limit: Maximum results to return
        offset: Number of results to skip
        current_user: Current authenticated user
        db: Database session

    Returns:
        ApiResponse with paginated list of results for the strategy
    """
    # Verify strategy exists and user has access
    strategy = BacktestStrategyService.get_strategy_by_id(db, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Check authorization
    if (
        not strategy.is_public
        and strategy.user_id != current_user["user_id"]
        and not current_user["is_admin"]
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to view this strategy"
        )

    # Get results
    results = BacktestResultService.get_results_by_strategy(
        db, strategy_id, skip=offset, limit=limit
    )

    # Get total count (simple but not optimal - can be optimized with query count)
    all_results = BacktestResultService.get_results_by_strategy(
        db, strategy_id, skip=0, limit=999999
    )
    total = len(all_results)

    formatted_results = []
    for result in results:
        formatted_results.append(
            {
                "id": result.id,
                "market_1": result.market_1,
                "market_2": result.market_2,
                "total_trades": result.total_trades,
                "pnl": result.pnl,
                "win_rate": result.win_rate,
                "sharpe_ratio": result.sharpe_ratio,
                "profit_factor": result.profit_factor,
                "max_drawdown": result.max_drawdown,
                "created_at": result.created_at.isoformat(),
            }
        )

    return ApiResponse(
        success=True,
        message="Strategy results retrieved",
        data={
            "strategy_id": strategy_id,
            "strategy_name": strategy.name,
            "results": formatted_results,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "returned": len(formatted_results),
            },
        },
    )


# ==================== STRATEGY MANAGEMENT ENDPOINTS ====================


@app.post("/api/v1/strategies", response_model=ApiResponse)
async def create_strategy(
    request: BacktestStrategyCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new backtest strategy."""
    try:
        from backend.services import BacktestStrategyService

        strategy = BacktestStrategyService.create_strategy(
            db=db,
            user_id=current_user["user_id"],
            name=request.name,
            description=request.description,
            category=request.category,
            is_public=request.is_public,
            zscore_threshold=request.zscore_threshold,
            stats_window=request.stats_window,
            max_half_life=request.max_half_life,
            usd_per_trade=request.usd_per_trade,
            usd_min_collateral=request.usd_min_collateral,
            close_at_zscore_cross=request.close_at_zscore_cross,
            find_cointegrated_pairs=request.find_cointegrated_pairs,
            manage_exits=request.manage_exits,
            place_trades=request.place_trades,
            abort_all_positions=request.abort_all_positions,
            max_positions=request.max_positions,
            max_drawdown_pct=request.max_drawdown_pct,
            stop_loss_pct=request.stop_loss_pct,
            take_profit_pct=request.take_profit_pct,
            trailing_stop_pct=request.trailing_stop_pct,
            rebalance_interval_hours=request.rebalance_interval_hours,
            position_timeout_hours=request.position_timeout_hours,
        )

        AuditLogService.log_action(
            db=db,
            action="create_strategy",
            resource_type="BacktestStrategy",
            user_id=current_user["user_id"],
            resource_id=str(strategy.id),
            status="success",
        )

        return ApiResponse(
            success=True,
            message="Strategy created successfully",
            data=strategy.to_dict(),
        )
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        AuditLogService.log_action(
            db=db,
            action="create_strategy",
            resource_type="BacktestStrategy",
            user_id=current_user["user_id"],
            status="failed",
            details={"error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/v1/strategies", response_model=ApiResponse)
async def list_user_strategies(
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all strategies for the current user."""
    try:
        from backend.services import BacktestStrategyService

        strategies = BacktestStrategyService.get_user_strategies(
            db=db, user_id=current_user["user_id"], skip=skip, limit=limit
        )

        return ApiResponse(
            success=True,
            message="Strategies retrieved",
            data={
                "total": len(strategies),
                "skip": skip,
                "limit": limit,
                "strategies": [s.to_dict() for s in strategies],
            },
        )
    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get("/api/v1/strategies/public", response_model=ApiResponse)
async def list_public_strategies(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get all public strategies available to all users."""
    try:
        from backend.services import BacktestStrategyService

        strategies = BacktestStrategyService.get_public_strategies(
            db=db, skip=skip, limit=limit
        )

        return ApiResponse(
            success=True,
            message="Public strategies retrieved",
            data={
                "total": len(strategies),
                "skip": skip,
                "limit": limit,
                "strategies": [s.to_dict() for s in strategies],
            },
        )
    except Exception as e:
        logger.error(f"Error listing public strategies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get("/api/v1/strategies/{strategy_id}", response_model=ApiResponse)
async def get_strategy(
    strategy_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific strategy by ID."""
    try:
        from backend.services import BacktestStrategyService

        strategy = BacktestStrategyService.get_strategy_by_id(
            db=db, strategy_id=strategy_id
        )

        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        # Check authorization (owner or public)
        if strategy.user_id != current_user["user_id"] and not strategy.is_public:
            raise HTTPException(
                status_code=403, detail="Not authorized to view this strategy"
            )

        # Get usage stats
        stats = BacktestStrategyService.get_strategy_usage_stats(
            db=db, strategy_id=strategy_id
        )

        strategy_data = strategy.to_dict()
        strategy_data["usage_stats"] = stats

        return ApiResponse(
            success=True,
            message="Strategy retrieved",
            data=strategy_data,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.put("/api/v1/strategies/{strategy_id}", response_model=ApiResponse)
async def update_strategy(
    strategy_id: int,
    updates: BacktestStrategyUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a strategy."""
    try:
        from backend.services import BacktestStrategyService

        strategy = BacktestStrategyService.get_strategy_by_id(
            db=db, strategy_id=strategy_id
        )

        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        # Check authorization
        if strategy.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this strategy"
            )

        # Convert to dict, removing None values
        update_data = updates.dict(exclude_unset=True)

        updated = BacktestStrategyService.update_strategy(
            db=db, strategy_id=strategy_id, update_data=update_data
        )

        AuditLogService.log_action(
            db=db,
            action="update_strategy",
            resource_type="BacktestStrategy",
            user_id=current_user["user_id"],
            resource_id=str(strategy_id),
            details={"updates": update_data},
            status="success",
        )

        return ApiResponse(
            success=True,
            message="Strategy updated successfully",
            data=updated.to_dict() if updated else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy: {e}")
        AuditLogService.log_action(
            db=db,
            action="update_strategy",
            resource_type="BacktestStrategy",
            user_id=current_user["user_id"],
            resource_id=str(strategy_id),
            status="failed",
            details={"error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.delete("/api/v1/strategies/{strategy_id}", response_model=ApiResponse)
async def delete_strategy(
    strategy_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a strategy."""
    try:
        from backend.services import BacktestStrategyService

        strategy = BacktestStrategyService.get_strategy_by_id(
            db=db, strategy_id=strategy_id
        )

        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        # Check authorization
        if strategy.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this strategy"
            )

        success = BacktestStrategyService.delete_strategy(
            db=db, strategy_id=strategy_id
        )

        AuditLogService.log_action(
            db=db,
            action="delete_strategy",
            resource_type="BacktestStrategy",
            user_id=current_user["user_id"],
            resource_id=str(strategy_id),
            status="success",
        )

        return ApiResponse(
            success=True,
            message="Strategy deleted successfully",
            data={"deleted": success},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting strategy: {e}")
        AuditLogService.log_action(
            db=db,
            action="delete_strategy",
            resource_type="BacktestStrategy",
            user_id=current_user["user_id"],
            resource_id=str(strategy_id),
            status="failed",
            details={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# ==================== WEBSOCKET ENDPOINTS ====================


@app.websocket("/ws/backtest/{run_id}")
async def websocket_backtest_updates(
    websocket: WebSocket, run_id: str, token: Optional[str] = None
):
    """WebSocket endpoint for real-time backtest updates."""
    # Verify token
    logger.info(
        f"WebSocket connection attempt: run_id={run_id}, token_received={bool(token)}, token_length={len(token) if token else 0}"
    )

    if not token:
        logger.error("WebSocket connection rejected: no token provided")
        await websocket.accept()  # Must accept before closing
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not verify_token(token, token_type="access"):
        logger.error("WebSocket connection rejected: token verification failed")
        await websocket.accept()  # Must accept before closing
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    logger.info(f"WebSocket connection accepted: run_id={run_id}")

    await websocket.accept()
    WS_ACTIVE_CONNECTIONS.append(websocket)
    broadcaster = get_broadcaster()

    # Define callback to send updates to this WebSocket
    async def send_update(update: BacktestProgressUpdate):
        try:
            await websocket.send_json(update.to_dict())
        except Exception as e:
            logger.error(f"Error sending WebSocket update: {e}")

    # Subscribe to updates for this run
    broadcaster.subscribe(run_id, send_update)

    try:
        while True:
            # Receive any message from client (keep connection alive)
            data = await websocket.receive_text()
            logger.debug(f"WebSocket message from {run_id}: {data}")
    except WebSocketDisconnect:
        # Unsubscribe and cleanup
        broadcaster.unsubscribe(run_id, send_update)
        WS_ACTIVE_CONNECTIONS.remove(websocket)
        logger.info(f"WebSocket client disconnected: {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in WS_ACTIVE_CONNECTIONS:
            WS_ACTIVE_CONNECTIONS.remove(websocket)
        broadcaster.unsubscribe(run_id, send_update)


@app.websocket("/ws/strategies")
async def websocket_strategy_updates(websocket: WebSocket, token: Optional[str] = None):
    """WebSocket endpoint for real-time strategy execution status updates.

    Expected client message: None (connection just maintains live status)
    Server broadcasts every 5 seconds:
    {
        "timestamp": "2025-10-20T00:46:57Z",
        "strategies": [
            {
                "strategyId": 1,
                "status": "running|stopped|paused|error",
                "tradesExecuted": 5,
                "pnl": 123.45,
                "lastError": null,
                "updatedAt": "2025-10-20T00:46:57Z"
            }
        ]
    }
    """
    # Verify token
    logger.info(f"Strategy WebSocket connection attempt: token_received={bool(token)}")

    if not token:
        logger.error("Strategy WebSocket rejected: no token provided")
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not verify_token(token, token_type="access"):
        logger.error("Strategy WebSocket rejected: token verification failed")
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    logger.info("Strategy WebSocket connection accepted")
    await websocket.accept()
    WS_ACTIVE_CONNECTIONS.append(websocket)

    try:
        # Broadcast strategy status every 5 seconds
        import asyncio

        from backend.database import SessionLocal, StrategyExecutionState

        while True:
            try:
                # Fetch all strategy execution states from database
                db = SessionLocal()
                try:
                    execution_states = db.query(StrategyExecutionState).all()
                    strategies_data = [state.to_dict() for state in execution_states]
                finally:
                    db.close()

                # Send current strategy statuses to client
                status_update = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "strategies": strategies_data,
                }

                await websocket.send_json(status_update)
                await asyncio.sleep(5)  # Broadcast every 5 seconds

            except Exception as send_error:
                logger.error(f"Error sending strategy status: {send_error}")
                break

    except WebSocketDisconnect:
        WS_ACTIVE_CONNECTIONS.remove(websocket)
        logger.info("Strategy WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Strategy WebSocket error: {e}")
        if websocket in WS_ACTIVE_CONNECTIONS:
            WS_ACTIVE_CONNECTIONS.remove(websocket)


# ==================== STRATEGY VERSION HISTORY ENDPOINTS ====================


@app.post("/api/v1/strategies/{strategy_id}/versions", response_model=ApiResponse)
async def create_strategy_version(
    strategy_id: int,
    change_description: str = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save current strategy state as a new version in history."""
    from backend.database import BacktestStrategy, StrategyVersionHistory

    try:
        # Get strategy
        strategy = (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.id == strategy_id)
            .first()
        )

        if not strategy:
            return ApiResponse(
                success=False,
                message=f"Strategy {strategy_id} not found",
                data=None,
            )

        # Check authorization
        if strategy.user_id != current_user["user_id"] and not current_user["is_admin"]:
            return ApiResponse(
                success=False,
                message="Not authorized to version this strategy",
                data=None,
            )

        # Get next version number
        latest_version = (
            db.query(StrategyVersionHistory)
            .filter(StrategyVersionHistory.strategy_id == strategy_id)
            .order_by(StrategyVersionHistory.version_number.desc())
            .first()
        )
        next_version = (latest_version.version_number + 1) if latest_version else 1

        # Create version entry
        version_entry = StrategyVersionHistory(
            strategy_id=strategy_id,
            version_number=next_version,
            change_description=change_description,
            config_snapshot=strategy.to_dict(),
            created_by_user_id=current_user["user_id"],
        )

        db.add(version_entry)
        db.commit()
        db.refresh(version_entry)

        logger.info(
            f"Strategy {strategy_id} versioned as v{next_version} by user {current_user['user_id']}"
        )

        return ApiResponse(
            success=True,
            message=f"Strategy version {next_version} saved successfully",
            data=version_entry.to_dict(),
        )

    except Exception as e:
        logger.error(f"Error creating strategy version: {e}")
        db.rollback()
        return ApiResponse(
            success=False,
            message=f"Error creating version: {str(e)}",
            data=None,
        )


@app.get("/api/v1/strategies/{strategy_id}/versions", response_model=ApiResponse)
async def get_strategy_versions(
    strategy_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all versions of a strategy."""
    from backend.database import BacktestStrategy, StrategyVersionHistory

    try:
        # Check strategy exists and user has access
        strategy = (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.id == strategy_id)
            .first()
        )

        if not strategy:
            return ApiResponse(
                success=False,
                message=f"Strategy {strategy_id} not found",
                data=None,
            )

        if strategy.user_id != current_user["user_id"] and not current_user["is_admin"]:
            return ApiResponse(
                success=False,
                message="Not authorized to view this strategy",
                data=None,
            )

        # Get all versions
        versions = (
            db.query(StrategyVersionHistory)
            .filter(StrategyVersionHistory.strategy_id == strategy_id)
            .order_by(StrategyVersionHistory.version_number.desc())
            .all()
        )

        versions_data = [v.to_dict() for v in versions]

        return ApiResponse(
            success=True,
            message="Strategy versions retrieved successfully",
            data={
                "strategy_id": strategy_id,
                "versions": versions_data,
                "total": len(versions_data),
            },
        )

    except Exception as e:
        logger.error(f"Error fetching strategy versions: {e}")
        return ApiResponse(
            success=False,
            message=f"Error fetching versions: {str(e)}",
            data=None,
        )


@app.post(
    "/api/v1/strategies/{strategy_id}/versions/{version_id}/apply",
    response_model=ApiResponse,
)
async def apply_strategy_version(
    strategy_id: int,
    version_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revert strategy to a specific version."""
    from backend.database import BacktestStrategy, StrategyVersionHistory

    try:
        # Get strategy
        strategy = (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.id == strategy_id)
            .first()
        )

        if not strategy:
            return ApiResponse(
                success=False,
                message=f"Strategy {strategy_id} not found",
                data=None,
            )

        # Check authorization
        if strategy.user_id != current_user["user_id"] and not current_user["is_admin"]:
            return ApiResponse(
                success=False,
                message="Not authorized to modify this strategy",
                data=None,
            )

        # Get version
        version = (
            db.query(StrategyVersionHistory)
            .filter(
                StrategyVersionHistory.id == version_id,
                StrategyVersionHistory.strategy_id == strategy_id,
            )
            .first()
        )

        if not version:
            return ApiResponse(
                success=False,
                message=f"Version {version_id} not found",
                data=None,
            )

        # Apply config from version to current strategy
        config = version.config_snapshot
        strategy.zscore_threshold = config.get("zscore_threshold", 1.5)
        strategy.stats_window = config.get("stats_window", 21)
        strategy.max_half_life = config.get("max_half_life", 24.0)
        strategy.usd_per_trade = config.get("usd_per_trade", 10.0)
        strategy.usd_min_collateral = config.get("usd_min_collateral", 100.0)
        strategy.close_at_zscore_cross = config.get("close_at_zscore_cross", True)
        strategy.find_cointegrated_pairs = config.get("find_cointegrated_pairs", True)
        strategy.manage_exits = config.get("manage_exits", True)
        strategy.place_trades = config.get("place_trades", True)
        strategy.abort_all_positions = config.get("abort_all_positions", False)
        strategy.max_positions = config.get("max_positions", 5)
        strategy.max_drawdown_pct = config.get("max_drawdown_pct", 15.0)
        strategy.stop_loss_pct = config.get("stop_loss_pct", 2.0)
        strategy.take_profit_pct = config.get("take_profit_pct", 5.0)
        strategy.trailing_stop_pct = config.get("trailing_stop_pct", 1.0)
        strategy.rebalance_interval_hours = config.get("rebalance_interval_hours", 24)
        strategy.position_timeout_hours = config.get("position_timeout_hours", 72)
        strategy.transaction_fee = config.get("transaction_fee", 0.0005)
        strategy.slippage = config.get("slippage", 0.001)
        strategy.starting_balance = config.get("starting_balance", 1000.0)
        strategy.candle_resolution = config.get("candle_resolution", "1HOUR")
        strategy.max_history_days = config.get("max_history_days", 90)

        db.commit()
        db.refresh(strategy)

        logger.info(
            f"Strategy {strategy_id} reverted to version {version.version_number} by user {current_user['user_id']}"
        )

        return ApiResponse(
            success=True,
            message=f"Strategy reverted to version {version.version_number}",
            data=strategy.to_dict(),
        )

    except Exception as e:
        logger.error(f"Error applying strategy version: {e}")
        db.rollback()
        return ApiResponse(
            success=False,
            message=f"Error applying version: {str(e)}",
            data=None,
        )


@app.post("/api/v1/backtests/{run_id}/create-strategy", response_model=ApiResponse)
async def create_strategy_from_backtest(
    run_id: str,
    strategy_name: str,
    strategy_description: str = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new strategy from a backtest result's configuration."""
    from backend.database import (
        BacktestRun,
        BacktestStrategy,
        StrategyVersionHistory,
    )

    try:
        # Get backtest run
        backtest_run = (
            db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
        )

        if not backtest_run:
            return ApiResponse(
                success=False,
                message=f"Backtest {run_id} not found",
                data=None,
            )

        # Check authorization
        if (
            backtest_run.user_id != current_user["user_id"]
            and not current_user["is_admin"]
        ):
            return ApiResponse(
                success=False,
                message="Not authorized to access this backtest",
                data=None,
            )

        # Get config from backtest strategy_snapshot
        config = backtest_run.strategy_snapshot or {}

        # Create new strategy
        new_strategy = BacktestStrategy(
            name=strategy_name,
            description=strategy_description
            or f"Created from backtest {run_id} with PnL: ${backtest_run.total_pnl_usd:.2f}",
            user_id=current_user["user_id"],
            zscore_threshold=config.get("zscore_threshold", 1.5),
            stats_window=config.get("stats_window", 21),
            max_half_life=config.get("max_half_life", 24.0),
            usd_per_trade=config.get("usd_per_trade", 10.0),
            usd_min_collateral=config.get("usd_min_collateral", 100.0),
            close_at_zscore_cross=config.get("close_at_zscore_cross", True),
            find_cointegrated_pairs=config.get("find_cointegrated_pairs", True),
            manage_exits=config.get("manage_exits", True),
            place_trades=config.get("place_trades", True),
            abort_all_positions=config.get("abort_all_positions", False),
            max_positions=config.get("max_positions", 5),
            max_drawdown_pct=config.get("max_drawdown_pct", 15.0),
            stop_loss_pct=config.get("stop_loss_pct", 2.0),
            take_profit_pct=config.get("take_profit_pct", 5.0),
            trailing_stop_pct=config.get("trailing_stop_pct", 1.0),
            rebalance_interval_hours=config.get("rebalance_interval_hours", 24),
            position_timeout_hours=config.get("position_timeout_hours", 72),
            transaction_fee=config.get("transaction_fee", 0.0005),
            slippage=config.get("slippage", 0.001),
            starting_balance=config.get("starting_balance", 1000.0),
            candle_resolution=config.get("candle_resolution", "1HOUR"),
            max_history_days=config.get("max_history_days", 90),
        )

        db.add(new_strategy)
        db.flush()  # Get strategy ID

        # Create initial version history entry
        version_entry = StrategyVersionHistory(
            strategy_id=new_strategy.id,
            version_number=1,
            change_description=f"Initial version created from backtest {run_id} (PnL: ${backtest_run.total_pnl_usd:.2f}, Win Rate: {backtest_run.win_rate:.1f}%)",
            config_snapshot=new_strategy.to_dict(),
            created_by_user_id=current_user["user_id"],
            backtest_count=1,
            best_backtest_pnl=backtest_run.total_pnl_usd,
            average_backtest_pnl=backtest_run.total_pnl_usd,
        )

        db.add(version_entry)
        db.commit()
        db.refresh(new_strategy)

        logger.info(
            f"Strategy '{strategy_name}' created from backtest {run_id} by user {current_user['user_id']}"
        )

        return ApiResponse(
            success=True,
            message=f"Strategy '{strategy_name}' created successfully from backtest result",
            data={
                "strategy": new_strategy.to_dict(),
                "version": version_entry.to_dict(),
                "backtest_config": config,
            },
        )

    except Exception as e:
        logger.error(f"Error creating strategy from backtest: {e}")
        db.rollback()
        return ApiResponse(
            success=False,
            message=f"Error creating strategy: {str(e)}",
            data=None,
        )


@app.get("/api/v1/backtests/{run_id}/config", response_model=ApiResponse)
async def get_backtest_config(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the strategy configuration used for a specific backtest."""
    from backend.database import BacktestRun

    try:
        # Get backtest run
        backtest_run = (
            db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
        )

        if not backtest_run:
            return ApiResponse(
                success=False,
                message=f"Backtest {run_id} not found",
                data=None,
            )

        # Check authorization
        if (
            backtest_run.user_id != current_user["user_id"]
            and not current_user["is_admin"]
        ):
            return ApiResponse(
                success=False,
                message="Not authorized to access this backtest",
                data=None,
            )

        return ApiResponse(
            success=True,
            message="Backtest configuration retrieved successfully",
            data={
                "run_id": run_id,
                "strategy_snapshot": backtest_run.strategy_snapshot,
                "config": backtest_run.config,
                "strategy_id": backtest_run.strategy_id,
                "strategy_version_id": backtest_run.strategy_version_id,
            },
        )

    except Exception as e:
        logger.error(f"Error fetching backtest config: {e}")
        return ApiResponse(
            success=False,
            message=f"Error fetching config: {str(e)}",
            data=None,
        )


# ==================== STRATEGY EXECUTION STATE ENDPOINTS ====================


@app.get("/api/v1/strategies/{strategy_id}/execution-state", response_model=ApiResponse)
async def get_strategy_execution_state(
    strategy_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current execution state of a specific strategy."""
    from backend.database import StrategyExecutionState

    try:
        execution_state = (
            db.query(StrategyExecutionState)
            .filter(StrategyExecutionState.strategy_id == strategy_id)
            .first()
        )

        if not execution_state:
            return ApiResponse(
                success=True,
                message="Strategy execution state not found",
                data=None,
            )

        return ApiResponse(
            success=True,
            message="Strategy execution state retrieved successfully",
            data=execution_state.to_dict(),
        )
    except Exception as e:
        logger.error(f"Error fetching strategy execution state: {e}")
        return ApiResponse(
            success=False,
            message=f"Error fetching execution state: {str(e)}",
            data=None,
        )


@app.get("/api/v1/strategies/execution-state/all", response_model=ApiResponse)
async def get_all_strategy_execution_states(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get execution states for all strategies."""
    from backend.database import StrategyExecutionState

    try:
        execution_states = db.query(StrategyExecutionState).all()
        states_data = [state.to_dict() for state in execution_states]

        return ApiResponse(
            success=True,
            message="Strategy execution states retrieved successfully",
            data={"strategies": states_data, "total": len(states_data)},
        )
    except Exception as e:
        logger.error(f"Error fetching strategy execution states: {e}")
        return ApiResponse(
            success=False,
            message=f"Error fetching execution states: {str(e)}",
            data=None,
        )


@app.post(
    "/api/v1/strategies/{strategy_id}/execution-state/initialize",
    response_model=ApiResponse,
)
async def initialize_strategy_execution_state(
    strategy_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initialize execution state for a strategy."""
    from backend.database import BacktestStrategy, StrategyExecutionState

    try:
        # Check if strategy exists
        strategy = (
            db.query(BacktestStrategy)
            .filter(BacktestStrategy.id == strategy_id)
            .first()
        )
        if not strategy:
            return ApiResponse(
                success=False,
                message=f"Strategy {strategy_id} not found",
                data=None,
            )

        # Check if execution state already exists
        existing_state = (
            db.query(StrategyExecutionState)
            .filter(StrategyExecutionState.strategy_id == strategy_id)
            .first()
        )

        if existing_state:
            return ApiResponse(
                success=True,
                message="Execution state already exists",
                data=existing_state.to_dict(),
            )

        # Create new execution state
        new_state = StrategyExecutionState(
            strategy_id=strategy_id,
            enabled=False,
            status="stopped",
            trades_executed=0,
            pnl=0.0,
            pnl_pct=0.0,
            config_snapshot=strategy.to_dict(),
        )
        db.add(new_state)
        db.commit()
        db.refresh(new_state)

        logger.info(f"Initialized execution state for strategy {strategy_id}")

        return ApiResponse(
            success=True,
            message="Execution state initialized successfully",
            data=new_state.to_dict(),
        )
    except Exception as e:
        logger.error(f"Error initializing strategy execution state: {e}")
        db.rollback()
        return ApiResponse(
            success=False,
            message=f"Error initializing execution state: {str(e)}",
            data=None,
        )


@app.put("/api/v1/strategies/{strategy_id}/execution-state", response_model=ApiResponse)
async def update_strategy_execution_state(
    strategy_id: int,
    updates: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update execution state for a strategy (used by strategy executor threads)."""
    from backend.database import StrategyExecutionState

    try:
        execution_state = (
            db.query(StrategyExecutionState)
            .filter(StrategyExecutionState.strategy_id == strategy_id)
            .first()
        )

        if not execution_state:
            return ApiResponse(
                success=False,
                message=f"Execution state for strategy {strategy_id} not found",
                data=None,
            )

        # Update fields from request
        for field, value in updates.items():
            if hasattr(execution_state, field) and not field.startswith("_"):
                setattr(execution_state, field, value)

        execution_state.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(execution_state)

        logger.info(f"Updated execution state for strategy {strategy_id}")

        return ApiResponse(
            success=True,
            message="Execution state updated successfully",
            data=execution_state.to_dict(),
        )
    except Exception as e:
        logger.error(f"Error updating strategy execution state: {e}")
        db.rollback()
        return ApiResponse(
            success=False,
            message=f"Error updating execution state: {str(e)}",
            data=None,
        )


@app.post(
    "/api/v1/strategies/{strategy_id}/execution-state/enable",
    response_model=ApiResponse,
)
async def enable_strategy_execution(
    strategy_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable strategy execution (start trading)."""
    from backend.database import StrategyExecutionState

    try:
        execution_state = (
            db.query(StrategyExecutionState)
            .filter(StrategyExecutionState.strategy_id == strategy_id)
            .first()
        )

        if not execution_state:
            return ApiResponse(
                success=False,
                message=f"Execution state for strategy {strategy_id} not found",
                data=None,
            )

        execution_state.enabled = True
        execution_state.status = "running"
        execution_state.last_started = datetime.now(timezone.utc)
        execution_state.error_count = 0
        execution_state.last_error = None
        execution_state.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(execution_state)

        logger.info(f"Enabled strategy execution for strategy {strategy_id}")

        return ApiResponse(
            success=True,
            message="Strategy execution enabled",
            data=execution_state.to_dict(),
        )
    except Exception as e:
        logger.error(f"Error enabling strategy execution: {e}")
        db.rollback()
        return ApiResponse(
            success=False,
            message=f"Error enabling strategy: {str(e)}",
            data=None,
        )


@app.post(
    "/api/v1/strategies/{strategy_id}/execution-state/disable",
    response_model=ApiResponse,
)
async def disable_strategy_execution(
    strategy_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable strategy execution (stop trading)."""
    from backend.database import StrategyExecutionState

    try:
        execution_state = (
            db.query(StrategyExecutionState)
            .filter(StrategyExecutionState.strategy_id == strategy_id)
            .first()
        )

        if not execution_state:
            return ApiResponse(
                success=False,
                message=f"Execution state for strategy {strategy_id} not found",
                data=None,
            )

        execution_state.enabled = False
        execution_state.status = "stopped"
        execution_state.last_stopped = datetime.now(timezone.utc)
        execution_state.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(execution_state)

        logger.info(f"Disabled strategy execution for strategy {strategy_id}")

        return ApiResponse(
            success=True,
            message="Strategy execution disabled",
            data=execution_state.to_dict(),
        )
    except Exception as e:
        logger.error(f"Error disabling strategy execution: {e}")
        db.rollback()
        return ApiResponse(
            success=False,
            message=f"Error disabling strategy: {str(e)}",
            data=None,
        )


# ==================== HEALTH CHECK ====================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


# ==================== REDIS CACHE MANAGEMENT ====================


@app.get("/api/v1/redis/status")
async def get_redis_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Redis connection status and cache statistics."""
    from backend.services import RedisSettingsService

    connection_status = RedisSettingsService.test_redis_connection(db)
    cache_stats = RedisSettingsService.get_cache_stats(db)
    redis_settings = RedisSettingsService.get_redis_settings(db)

    return {
        "success": True,
        "data": {
            "connection": connection_status,
            "cache_stats": cache_stats,
            "settings": redis_settings,
        },
    }


@app.get("/api/v1/redis/settings")
async def get_redis_settings_endpoint(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current Redis settings."""
    from backend.services import RedisSettingsService

    settings = RedisSettingsService.get_redis_settings(db)
    if not settings:
        return {
            "success": False,
            "message": "Redis settings not found",
        }

    return {
        "success": True,
        "data": settings,
    }


@app.post("/api/v1/redis/settings")
async def update_redis_settings_endpoint(
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update Redis settings."""
    from backend.services import RedisSettingsService

    try:
        settings = RedisSettingsService.update_redis_settings(
            db,
            enabled=body.get("enabled"),
            host=body.get("host"),
            port=body.get("port"),
            database=body.get("database"),
            password=body.get("password"),
            ssl=body.get("ssl"),
            timeout=body.get("timeout"),
            max_connections=body.get("max_connections"),
            cache_ttl_seconds=body.get("cache_ttl_seconds"),
            cache_backtest_results=body.get("cache_backtest_results"),
            cache_market_data=body.get("cache_market_data"),
            cache_analysis_results=body.get("cache_analysis_results"),
        )

        return {
            "success": True,
            "message": "Redis settings updated",
            "data": settings,
        }
    except Exception as e:
        logger.error(f"Failed to update Redis settings: {e}")
        return {
            "success": False,
            "message": str(e),
        }


@app.post("/api/v1/redis/test-connection")
async def test_redis_connection(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test Redis connection."""
    from backend.services import RedisSettingsService

    try:
        status = RedisSettingsService.test_redis_connection(db)
        return {
            "success": status.get("connected", False),
            "message": "Connected" if status.get("connected") else "Connection failed",
            "data": status,
        }
    except Exception as e:
        logger.error(f"Redis connection test failed: {e}")
        return {
            "success": False,
            "message": str(e),
        }


@app.post("/api/v1/redis/toggle")
async def toggle_redis(
    enabled: bool,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable or disable Redis caching."""
    from backend.services import RedisSettingsService

    try:
        settings = RedisSettingsService.toggle_redis_enabled(db, enabled)
        return {
            "success": True,
            "message": f"Redis {'enabled' if enabled else 'disabled'}",
            "data": settings,
        }
    except Exception as e:
        logger.error(f"Failed to toggle Redis: {e}")
        return {
            "success": False,
            "message": str(e),
        }


@app.post("/api/v1/redis/flush")
async def flush_redis_cache(
    current_user: dict = Depends(get_current_user),
):
    """Flush Redis cache (admin only)."""
    from backend.redis_service import get_redis_service

    try:
        redis_service = get_redis_service()
        if not redis_service.enabled:
            return {
                "success": False,
                "message": "Redis is not enabled",
            }

        redis_service.flush_all()
        return {
            "success": True,
            "message": "Redis cache flushed",
        }
    except Exception as e:
        logger.error(f"Failed to flush Redis: {e}")
        return {
            "success": False,
            "message": str(e),
        }


# ==================== ROOT ====================


@app.get("/")
async def root():
    """Root endpoint with API documentation."""
    return {
        "name": "dYdX Backtest API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the FastAPI server."""
    uvicorn.run(
        "backend.main:app", host=host, port=port, reload=reload, log_level="info"
    )


if __name__ == "__main__":
    run_server(reload=True)
