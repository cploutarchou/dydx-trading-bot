"""
Pydantic models for backtest operations
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class BacktestStatus(str):
    """Backtest status enumeration"""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BacktestConfigRequest(BaseModel):
    """Backtest configuration request"""
    name: str = Field(..., description="Backtest name")
    description: Optional[str] = Field(None, description="Backtest description")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_balance: float = Field(10000.0, description="Initial balance")
    trading_parameters: Dict[str, Any] = Field(..., description="Trading parameters")
    pairs: List[str] = Field(..., description="Trading pairs to test")


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
