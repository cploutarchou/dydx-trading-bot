"""
FastAPI backend server for dYdX Backtest System.
Provides REST API and WebSocket for real-time backtest monitoring.
"""

import logging
import os
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
    BacktestLog,
    BacktestResult,
    BacktestRun,
    TradeLog,
    get_db,
    init_db,
)
from backend.services import AuditLogService, BacktestRunService, UserService
from backend.ws_broadcaster import BacktestProgressUpdate, get_broadcaster

logger = logging.getLogger(__name__)

# Configuration
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:8000"
).split(",")
WS_ACTIVE_CONNECTIONS: List[WebSocket] = []


# Request/Response models
class BacktestStartRequest(BaseModel):
    """Request to start a backtest."""

    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    num_pairs: Optional[int] = Field(None, description="Number of pairs")
    zscore_threshold: Optional[float] = Field(1.2)
    stats_window: Optional[int] = Field(14)
    usd_per_trade: Optional[float] = Field(25.0)


class BacktestStatusUpdate(BaseModel):
    """Real-time backtest status update."""

    run_id: str
    status: str  # running, completed, failed
    progress: Optional[float] = None  # 0-100
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

    user_id = extract_user_from_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not extract user from token",
        )

    user = UserService.get_user_by_id(db, int(user_id))
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
    """Start a new backtest run."""
    try:
        logger.info(f"Starting backtest for user {current_user['user_id']}: {request}")

        # Create new backtest run record
        import uuid

        run_id = str(uuid.uuid4())

        BacktestRunService.create_run(
            db,
            run_id=run_id,
            start_date=request.start_date,
            end_date=request.end_date,
            num_pairs=request.num_pairs or 10,
            total_markets=0,  # Will be updated when backtest runs
            user_id=current_user["user_id"],
            config={
                "zscore_threshold": request.zscore_threshold,
                "stats_window": request.stats_window,
                "usd_per_trade": request.usd_per_trade,
            },
        )

        logger.info(f"Backtest {run_id} queued for user {current_user['user_id']}")

        # Execute backtest in background
        import asyncio

        asyncio.create_task(_execute_backtest_task(run_id, request, db))

        return ApiResponse(
            success=True,
            message="Backtest started",
            data={
                "run_id": run_id,
                "status": "queued",
                "message": "Your backtest has been queued. It will start shortly.",
            },
        )
    except Exception as e:
        logger.error(f"Error starting backtest: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start backtest: {str(e)}",
        )


async def _execute_backtest_task(
    run_id: str, request: BacktestStartRequest, db: Session
):
    """Background task to execute backtest and create logs."""
    import os
    import sys
    from datetime import datetime

    from config import config
    from func_backtest_logging import log_backtest_error, log_backtest_info
    from func_backtesting import BacktestEngine
    from func_connections import connect_dydx

    # Add app directory to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

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

        # Run backtest
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)
        num_pairs = request.num_pairs or 10

        await engine.run_backtest(start_date, end_date, num_pairs)

        log_backtest_info(run_id, "Backtest execution completed successfully", db)

    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        log_backtest_error(run_id, f"Backtest execution failed: {str(e)}", db)


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
    return schema


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

            if not setting:
                errors.append(f"Setting {key_path} not found")
                continue

            # Validate type conversion
            if setting.value_type == "float":
                value = float(value)
            elif setting.value_type == "int":
                value = int(value)
            elif setting.value_type == "boolean":
                value = str(value).lower() in ["true", "1", "yes"]

            # Update setting (type is stored as string)
            setting.value = (
                json.dumps(value) if setting.value_type == "json" else str(value)
            )
            setting.updated_by = current_user["user_id"]
            setting.version = setting.version + 1
            setting.updated_at = datetime.utcnow()
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


# ==================== HEALTH CHECK ====================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
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
