"""
Pydantic models for backtest operations
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BacktestStatus(str, Enum):
    """Backtest status enumeration"""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    STALE = "stale"


class BacktestConfigRequest(BaseModel):
    """Backtest configuration request"""

    name: str = Field(..., description="Backtest name")
    description: Optional[str] = Field(None, description="Backtest description")
    strategy_id: Optional[int] = Field(
        None, description="Optional originating strategy id"
    )
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_balance: float = Field(10000.0, description="Initial balance")
    pair_selection_mode: str = Field("liquidity", description="Pair selection mode")
    max_pairs: int = Field(
        0, description="Maximum number of pairs to process (0 means no cap)"
    )
    trading_parameters: Dict[str, Any] = Field(..., description="Trading parameters")
    pairs: List[str] = Field(..., description="Trading pairs to test")
    selected_pairs: Optional[List[str]] = Field(
        None, description="Exact selected markets requested for this run"
    )
    strategy_payload_snapshot: Optional[Dict[str, Any]] = Field(
        None, description="Immutable strategy payload snapshot used for this run"
    )
    bot_id: Optional[str] = Field(None, description="Optional bot identifier")
    source: Optional[str] = Field(None, description="Request source label")
    environment: Optional[str] = Field(None, description="Selected runtime environment")
    requested_by_user_id: Optional[int] = Field(
        None, description="Requesting user identifier"
    )
    source_strategy_version: Optional[Any] = Field(
        None, description="Originating strategy version metadata"
    )
    timeout_seconds: Optional[float] = Field(
        None, description="Maximum wall-clock runtime for the backtest"
    )


class BacktestResponse(BaseModel):
    """Backtest response"""

    id: int
    name: str
    status: BacktestStatus
    created_at: datetime
    updated_at: datetime
    config: BacktestConfigRequest


class BacktestListResponse(BaseModel):
    """Backtest list response"""

    backtests: List[BacktestResponse]
    total: int


class BacktestResultMetrics(BaseModel):
    """Backtest result metrics"""

    total_return: float
    total_return_pct: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    profitable_trades: int
    average_win: float
    average_loss: float
    profit_factor: float
    calmar_ratio: float


class BacktestTrade(BaseModel):
    """Individual backtest trade"""

    id: int
    pair1: str
    pair2: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price1: float
    entry_price2: float
    exit_price1: Optional[float]
    exit_price2: Optional[float]
    quantity1: float
    quantity2: float
    realized_pnl: float
    realized_pnl_pct: float
    status: str


class BacktestDetailResponse(BaseModel):
    """Detailed backtest response"""

    id: int
    name: str
    description: Optional[str]
    status: BacktestStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    config: BacktestConfigRequest
    metrics: Optional[BacktestResultMetrics]
    trades: List[BacktestTrade]
    equity_curve: List[Dict[str, Any]]  # Time series of equity values
