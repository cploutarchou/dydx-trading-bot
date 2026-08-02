"""
Pydantic models for backtest operations
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.shared.trading_validators import (
    ISO_DATE_PATTERN,
    normalize_market_list,
    validate_iso_date_range,
)


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
    """Backtest configuration request."""

    name: str = Field(..., min_length=1, max_length=255, description="Backtest name")
    description: Optional[str] = Field(
        None, max_length=2000, description="Backtest description"
    )
    strategy_id: Optional[int] = Field(
        None, ge=1, description="Optional originating strategy id"
    )
    start_date: str = Field(
        ..., pattern=ISO_DATE_PATTERN, description="Start date (YYYY-MM-DD)"
    )
    end_date: str = Field(
        ..., pattern=ISO_DATE_PATTERN, description="End date (YYYY-MM-DD)"
    )
    initial_balance: float = Field(
        default=10000.0, gt=0.0, description="Initial balance"
    )
    pair_selection_mode: str = Field(
        "liquidity", min_length=1, max_length=64, description="Pair selection mode"
    )
    max_pairs: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="Maximum number of pairs to process (0 means no cap)",
    )
    trading_parameters: Dict[str, Any] = Field(..., description="Trading parameters")
    pairs: List[str] = Field(..., description="Trading pairs to test")
    selected_pairs: Optional[List[str]] = Field(
        None, description="Exact selected markets requested for this run"
    )
    strategy_payload_snapshot: Optional[Dict[str, Any]] = Field(
        None, description="Immutable strategy payload snapshot used for this run"
    )
    bot_id: Optional[str] = Field(
        None, min_length=1, max_length=128, description="Optional bot identifier"
    )
    source: Optional[str] = Field(
        None, min_length=1, max_length=64, description="Request source label"
    )
    environment: Optional[str] = Field(
        None, min_length=1, max_length=32, description="Selected runtime environment"
    )
    requested_by_user_id: Optional[int] = Field(
        None, ge=1, description="Requesting user identifier"
    )
    source_strategy_version: Optional[Any] = Field(
        None, description="Originating strategy version metadata"
    )
    timeout_seconds: Optional[float] = Field(
        default=None, gt=0.0, description="Maximum wall-clock runtime for the backtest"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional structured run metadata persisted with the request"
    )

    @field_validator("pairs", "selected_pairs", mode="before")
    @classmethod
    def _normalize_pair_lists(cls, value: Any) -> Any:
        # Only normalize when a list-like is supplied; leave ``None`` untouched
        # so Optional fields keep their absence semantics.
        if value is None:
            return None
        return normalize_market_list(value)

    @model_validator(mode="after")
    def _validate_date_range(self) -> "BacktestConfigRequest":
        validate_iso_date_range(self.start_date, self.end_date)
        return self


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
    artifact_refs: Dict[str, str] = Field(
        default_factory=dict,
        description="Backtest artifact references keyed by artifact kind",
    )
    analytics_rows_written: int = Field(
        0,
        description="Total analytical rows written during artifact sidecar sync",
    )
