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
from backend.database import BacktestResult, TradeLog, get_db, init_db
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


@app.get("/api/v1/stats")
async def get_stats(
    current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get backtest statistics."""
    stats = BacktestRunService.get_run_stats(db)
    return ApiResponse(success=True, message="Statistics retrieved", data=stats)


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
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not verify_token(token, token_type="access"):
        logger.error("WebSocket connection rejected: token verification failed")
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
