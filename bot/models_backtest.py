"""
SQLAlchemy ORM Models for Backtesting System
Tracks: Backtest runs, results, trades, position snapshots, and configuration snapshots
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import declarative_base, relationship

# Use same base as main models for consistency
Base = declarative_base()


class BacktestStatusEnum(str, Enum):
    """Backtest execution status"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BacktestRun(Base):
    """Tracks backtest execution runs"""

    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_status", "status"),
        Index("ix_backtest_created", "created_at"),
        Index("ix_backtest_dates", "start_date", "end_date"),
    )

    # Primary key and identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(256), nullable=False)

    # Async task tracking
    task_id = Column(String(128), nullable=True, index=True)  # AsyncIO task ID
    job_id = Column(String(128), nullable=True, index=True)  # Optional job queue ID

    # Execution status
    status = Column(
        SQLEnum(BacktestStatusEnum), default=BacktestStatusEnum.QUEUED, nullable=False
    )

    # Date range configuration
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    total_days = Column(Integer, nullable=False)

    # Strategy parameters (snapshot at runtime)
    strategy_params = Column(JSON, nullable=False)

    # Backtest configuration
    backtest_config = Column(JSON, nullable=False)

    # Results (populated after completion)
    starting_balance = Column(Float, default=1000.0)
    ending_balance = Column(Float, nullable=True)
    total_pnl = Column(Float, nullable=True)
    total_return_pct = Column(Float, nullable=True)

    # Trade statistics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)

    # Performance metrics
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    max_drawdown_pct = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)

    # Progress tracking
    progress_pct = Column(Float, default=0.0)
    current_pair = Column(String(64), nullable=True)
    eta_seconds = Column(Integer, default=0)

    # Error handling
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    trades = relationship(
        "BacktestTrade", back_populates="run", cascade="all, delete-orphan"
    )
    position_snapshots = relationship(
        "BacktestPositionSnapshot", back_populates="run", cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "name": self.name,
            "task_id": self.task_id,
            "job_id": self.job_id,
            "status": self.status.value,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "total_days": self.total_days,
            "strategy_params": self.strategy_params,
            "backtest_config": self.backtest_config,
            "starting_balance": self.starting_balance,
            "ending_balance": self.ending_balance,
            "total_pnl": self.total_pnl,
            "total_return_pct": self.total_return_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "profit_factor": self.profit_factor,
            "progress_pct": self.progress_pct,
            "current_pair": self.current_pair,
            "eta_seconds": self.eta_seconds,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


class BacktestTrade(Base):
    """Individual backtest trade records"""

    __tablename__ = "backtest_trades"
    __table_args__ = (
        Index("ix_backtest_trade_run", "backtest_run_id"),
        Index("ix_backtest_trade_entry", "entry_timestamp"),
        Index("ix_backtest_trade_pnl", "pnl"),
    )

    # Primary key and relationships
    id = Column(Integer, primary_key=True, autoincrement=True)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id"), nullable=False)

    # Trade identification
    trade_id = Column(String(128), nullable=False, index=True)

    # Market pair
    market_1 = Column(String(32), nullable=False)
    market_2 = Column(String(32), nullable=False)

    # Entry details
    entry_timestamp = Column(DateTime, nullable=False)
    entry_price_1 = Column(Float, nullable=False)
    entry_price_2 = Column(Float, nullable=False)
    entry_zscore = Column(Float, nullable=False)

    # Position details
    side_1 = Column(String(8), nullable=False)  # BUY/SELL
    side_2 = Column(String(8), nullable=False)  # BUY/SELL
    size_1 = Column(Float, nullable=False)
    size_2 = Column(Float, nullable=False)
    hedge_ratio = Column(Float, nullable=False)

    # Exit details
    exit_timestamp = Column(DateTime, nullable=True)
    exit_price_1 = Column(Float, nullable=True)
    exit_price_2 = Column(Float, nullable=True)
    exit_zscore = Column(Float, nullable=True)

    # Performance
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    duration_hours = Column(Float, nullable=True)

    # Strategy context
    strategy_zscore_threshold = Column(Float, nullable=True)

    # Relationships
    run = relationship("BacktestRun", back_populates="trades")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "backtest_run_id": self.backtest_run_id,
            "trade_id": self.trade_id,
            "market_1": self.market_1,
            "market_2": self.market_2,
            "entry_timestamp": self.entry_timestamp.isoformat()
            if self.entry_timestamp
            else None,
            "entry_price_1": self.entry_price_1,
            "entry_price_2": self.entry_price_2,
            "entry_zscore": self.entry_zscore,
            "side_1": self.side_1,
            "side_2": self.side_2,
            "size_1": self.size_1,
            "size_2": self.size_2,
            "hedge_ratio": self.hedge_ratio,
            "exit_timestamp": self.exit_timestamp.isoformat()
            if self.exit_timestamp
            else None,
            "exit_price_1": self.exit_price_1,
            "exit_price_2": self.exit_price_2,
            "exit_zscore": self.exit_zscore,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "duration_hours": self.duration_hours,
            "strategy_zscore_threshold": self.strategy_zscore_threshold,
        }


class BacktestPositionSnapshot(Base):
    """Real-time position snapshots during backtest execution"""

    __tablename__ = "backtest_position_snapshots"
    __table_args__ = (
        Index("ix_snapshot_backtest_run", "backtest_run_id"),
        Index("ix_snapshot_timestamp", "timestamp"),
        Index("ix_snapshot_market_pair", "market_1", "market_2"),
    )

    # Primary key and relationships
    id = Column(Integer, primary_key=True, autoincrement=True)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id"), nullable=False)

    # Timestamp for this snapshot
    timestamp = Column(DateTime, nullable=False)

    # Market pair
    market_1 = Column(String(32), nullable=False)
    market_2 = Column(String(32), nullable=False)

    # Position details at this point in time
    is_open = Column(Integer, nullable=False, default=1)  # 1 = open, 0 = closed
    entry_timestamp = Column(DateTime, nullable=True)

    # Current prices and sizes
    current_price_1 = Column(Float, nullable=True)
    current_price_2 = Column(Float, nullable=True)
    current_size_1 = Column(Float, nullable=True)
    current_size_2 = Column(Float, nullable=True)

    # Entry details (for reference)
    entry_price_1 = Column(Float, nullable=True)
    entry_price_2 = Column(Float, nullable=True)
    entry_zscore = Column(Float, nullable=True)

    # Real-time metrics
    current_zscore = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    unrealized_pnl_pct = Column(Float, nullable=True)

    # Portfolio context
    portfolio_value = Column(Float, nullable=True)
    position_weight = Column(Float, nullable=True)  # Position size as % of portfolio

    # Trade context
    trade_id = Column(String(128), nullable=True, index=True)  # Links to BacktestTrade

    # Relationships
    run = relationship("BacktestRun", back_populates="position_snapshots")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "backtest_run_id": self.backtest_run_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "market_1": self.market_1,
            "market_2": self.market_2,
            "is_open": bool(self.is_open),
            "entry_timestamp": self.entry_timestamp.isoformat()
            if self.entry_timestamp
            else None,
            "current_price_1": self.current_price_1,
            "current_price_2": self.current_price_2,
            "current_size_1": self.current_size_1,
            "current_size_2": self.current_size_2,
            "entry_price_1": self.entry_price_1,
            "entry_price_2": self.entry_price_2,
            "entry_zscore": self.entry_zscore,
            "current_zscore": self.current_zscore,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "portfolio_value": self.portfolio_value,
            "position_weight": self.position_weight,
            "trade_id": self.trade_id,
        }


# Pydantic models for API requests/responses


class BacktestConfigRequest(BaseModel):
    """Backtest configuration request"""

    name: str
    start_date: str  # ISO format
    end_date: str  # ISO format

    # Strategy parameters (override config defaults)
    strategy_params: Optional[Dict[str, Any]] = {}

    # Backtest settings
    max_pairs: Optional[int] = None
    starting_balance: Optional[float] = 1000.0

    class Config:
        schema_extra = {
            "example": {
                "name": "BTC-ETH Strategy Test",
                "start_date": "2024-09-01",
                "end_date": "2024-10-31",
                "strategy_params": {
                    "zscore_threshold": 1.5,
                    "usd_per_trade": 50.0,
                    "close_at_zscore_cross": True,
                    "stats_window": 21,
                },
                "max_pairs": 5,
                "starting_balance": 1000.0,
            }
        }


class BacktestResponse(BaseModel):
    """Backtest execution response"""

    id: int
    run_id: str
    name: str
    status: str

    # Task tracking
    task_id: Optional[str] = None
    job_id: Optional[str] = None

    # Results (when completed)
    total_pnl: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    sharpe_ratio: Optional[float] = None

    # Progress (when running)
    progress_pct: Optional[float] = None
    current_pair: Optional[str] = None
    eta_seconds: Optional[int] = None

    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class BacktestListResponse(BaseModel):
    """List of backtest runs"""

    total: int
    runs: list[BacktestResponse]


class BacktestTradeResponse(BaseModel):
    """Backtest trade details"""

    trade_id: str
    market_1: str
    market_2: str
    entry_timestamp: str
    exit_timestamp: Optional[str] = None
    pnl: Optional[float] = None
    duration_hours: Optional[float] = None
    entry_zscore: float
    exit_zscore: Optional[float] = None


class BacktestDetailResponse(BaseModel):
    """Detailed backtest results"""

    # Basic info
    id: int
    run_id: str
    name: str
    status: str

    # Configuration
    start_date: str
    end_date: str
    total_days: int
    strategy_params: Dict[str, Any]

    # Results
    starting_balance: float
    ending_balance: Optional[float] = None
    total_pnl: Optional[float] = None
    total_return_pct: Optional[float] = None

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Optional[float] = None

    # Performance metrics
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    profit_factor: Optional[float] = None

    # Progress (if running)
    progress_pct: float
    current_pair: Optional[str] = None
    eta_seconds: int

    # Error info
    error_message: Optional[str] = None

    # Timestamps
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Recent trades (last 10)
    recent_trades: list[BacktestTradeResponse] = []


class BacktestPositionSnapshotResponse(BaseModel):
    """Position snapshot data for analytics"""

    timestamp: str
    market_1: str
    market_2: str
    is_open: bool
    current_price_1: Optional[float] = None
    current_price_2: Optional[float] = None
    current_zscore: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    portfolio_value: Optional[float] = None


class BacktestAnalyticsResponse(BaseModel):
    """Comprehensive backtest analytics"""

    run_id: str
    name: str

    # Performance summary
    total_return_pct: float
    sharpe_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    win_rate: float

    # Position analytics
    avg_position_duration: Optional[float] = None  # hours
    max_concurrent_positions: int = 0
    position_turnover_rate: Optional[float] = None

    # Risk metrics
    var_95: Optional[float] = None  # Value at Risk 95%
    expected_shortfall: Optional[float] = None
    calmar_ratio: Optional[float] = None  # Return / Max Drawdown

    # Market comparison (if dYdX data available)
    market_correlation: Optional[Dict[str, float]] = None
    beta_to_btc: Optional[float] = None
    alpha: Optional[float] = None

    # Time series data
    equity_curve: list[Dict[str, Any]] = []  # [{timestamp, portfolio_value}]
    drawdown_periods: list[Dict[str, Any]] = []  # [{start, end, depth_pct}]

    # Position heat map data
    position_performance_by_pair: Dict[str, Dict[str, Any]] = {}


class BacktestComparisonRequest(BaseModel):
    """Request to compare multiple backtest runs"""

    run_ids: list[str]
    metrics: list[str] = [
        "total_return_pct",
        "sharpe_ratio",
        "max_drawdown_pct",
        "win_rate",
    ]


class BacktestComparisonResponse(BaseModel):
    """Multi-backtest comparison results"""

    comparison_matrix: Dict[str, Dict[str, float]]  # {run_id: {metric: value}}
    best_performers: Dict[str, str]  # {metric: best_run_id}
    correlation_matrix: Dict[str, Dict[str, float]]  # Cross-correlation of returns
    summary_statistics: Dict[str, Dict[str, float]]  # {metric: {mean, std, min, max}}
