"""
Backtest-related database models.

Models:
- BacktestRun: Represents a single backtest execution run
- BacktestResult: Individual trading pair result from a backtest run
- BacktestLog: Stores logs from backtest execution for real-time display
- BacktestTrade: Stores individual trades from backtest execution for detailed analysis
- BacktestPosition: Tracks open/closed positions during backtest
- BacktestCandle: Stores OHLCV candle data during backtest
- BacktestComparison: Stores comparisons between multiple backtest runs
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import relationship

from base import Base


class BacktestRun(Base):
    """Represents a single backtest execution run."""

    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Execution info
    run_id = Column(String(50), unique=True, index=True, nullable=False)
    status = Column(String(20), default="running", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Input parameters
    start_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    end_date = Column(String(10), nullable=False)
    num_pairs = Column(Integer, nullable=False)
    total_markets = Column(Integer, nullable=False)
    resolution = Column(String(20), default="1HOUR")
    config = Column(JSON, nullable=True)

    # Overall metrics
    total_trades = Column(Integer, default=0)
    profitable_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)
    total_pnl = Column(Float, default=0.0)
    total_pnl_usd = Column(Float, default=0.0)

    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    calmar_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)

    # Position info
    starting_balance = Column(Float, default=1000.0)
    ending_balance = Column(Float, nullable=True)
    max_balance = Column(Float, nullable=True)
    min_balance = Column(Float, nullable=True)

    # Error tracking
    error_message = Column(String, nullable=True)

    # User tracking
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Strategy tracking
    strategy_id = Column(
        Integer, ForeignKey("backtest_strategies.id"), nullable=True, index=True
    )
    strategy_snapshot = Column(JSON, nullable=True)
    strategy_version_id = Column(
        Integer, ForeignKey("strategy_version_history.id"), nullable=True, index=True
    )

    # Relationships
    results = relationship(
        "BacktestResult", back_populates="run", cascade="all, delete-orphan"
    )
    user = relationship("User", back_populates="backtest_runs")
    strategy = relationship(
        "BacktestStrategy", back_populates="runs", foreign_keys=[strategy_id]
    )
    strategy_version = relationship(
        "StrategyVersionHistory", foreign_keys=[strategy_version_id]
    )

    __table_args__ = (
        Index("idx_run_status_created", "status", "created_at"),
        Index("idx_run_user_created", "user_id", "created_at"),
        Index("idx_run_date_range", "start_date", "end_date"),
    )

    def __repr__(self):
        return f"<BacktestRun {self.run_id} - {self.status}>"


class BacktestResult(Base):
    """Individual trading pair result from a backtest run."""

    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)

    # Pair identification
    market_1 = Column(String(50), nullable=False, index=True)
    market_2 = Column(String(50), nullable=False, index=True)

    # Foreign key
    run_id_fk = Column(
        Integer, ForeignKey("backtest_runs.id"), index=True, nullable=False
    )

    # Trading metrics
    total_trades = Column(Integer, default=0)
    entry_trades = Column(Integer, default=0)
    exit_trades = Column(Integer, default=0)
    profitable_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)

    # Performance
    pnl = Column(Float, default=0.0)
    pnl_usd = Column(Float, default=0.0)
    win_rate = Column(Float, nullable=True)
    avg_win = Column(Float, nullable=True)
    avg_loss = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)

    # Risk metrics
    max_drawdown = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    calmar_ratio = Column(Float, nullable=True)

    # Strategy metrics
    avg_trade_duration_hours = Column(Float, nullable=True)
    avg_winning_trade_duration = Column(Float, nullable=True)
    avg_losing_trade_duration = Column(Float, nullable=True)

    # Cointegration metrics
    cointegration_score = Column(Float, nullable=True)
    correlation = Column(Float, nullable=True)
    zscore_mean = Column(Float, nullable=True)
    zscore_std = Column(Float, nullable=True)

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    run = relationship("BacktestRun", back_populates="results")
    trades = relationship(
        "TradeLog", back_populates="result", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_result_pair", "market_1", "market_2"),
        Index("idx_result_run_profit", "run_id_fk", "pnl"),
    )

    def __repr__(self):
        return f"<BacktestResult {self.market_1}/{self.market_2}>"


class BacktestLog(Base):
    """Stores logs from backtest execution for real-time display."""

    __tablename__ = "backtest_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id_fk = Column(
        Integer, ForeignKey("backtest_runs.id"), index=True, nullable=False
    )

    message = Column(String, nullable=False)
    level = Column(String(20), default="info")  # debug, info, warning, error
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    run = relationship("BacktestRun", backref="logs")

    __table_args__ = (Index("idx_backtest_log_run_created", "run_id_fk", "created_at"),)

    def __repr__(self):
        return f"<BacktestLog {self.level}: {self.message[:50]}>"


class BacktestTrade(Base):
    """Stores individual trades from backtest execution for detailed analysis."""

    __tablename__ = "backtest_trades"

    id = Column(Integer, primary_key=True, index=True)
    run_id_fk = Column(
        Integer, ForeignKey("backtest_runs.id"), index=True, nullable=False
    )

    # Trade identification
    trade_id = Column(String(100), unique=True, index=True, nullable=False)
    market_1 = Column(String(50), nullable=False, index=True)
    market_2 = Column(String(50), nullable=False, index=True)

    # Entry details
    entry_timestamp = Column(DateTime, nullable=False, index=True)
    entry_price_1 = Column(Float, nullable=False)
    entry_price_2 = Column(Float, nullable=False)
    entry_z_score = Column(Float, nullable=False)
    side_1 = Column(String(10), nullable=False)  # BUY or SELL
    side_2 = Column(String(10), nullable=False)
    size_1 = Column(Float, nullable=False)
    size_2 = Column(Float, nullable=False)

    # Exit details
    exit_timestamp = Column(DateTime, nullable=True, index=True)
    exit_price_1 = Column(Float, nullable=True)
    exit_price_2 = Column(Float, nullable=True)
    exit_z_score = Column(Float, nullable=True)

    # Performance
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    duration_hours = Column(Float, nullable=True)

    # Configuration
    hedge_ratio = Column(Float, nullable=False)
    transaction_fee = Column(Float, nullable=False)
    slippage = Column(Float, nullable=False)

    # Relationships
    run = relationship("BacktestRun", backref="trades")

    __table_args__ = (
        Index("idx_backtest_trade_run_entry", "run_id_fk", "entry_timestamp"),
        Index("idx_backtest_trade_market", "market_1", "market_2"),
    )

    def __repr__(self):
        return f"<BacktestTrade {self.trade_id}>"


class BacktestPosition(Base):
    """Tracks open/closed positions during backtest for detailed analysis."""

    __tablename__ = "backtest_positions"

    id = Column(Integer, primary_key=True, index=True)
    run_id_fk = Column(
        Integer, ForeignKey("backtest_runs.id"), index=True, nullable=False
    )

    # Position identification
    position_id = Column(String(100), unique=True, index=True, nullable=False)
    market_1 = Column(String(50), nullable=False)
    market_2 = Column(String(50), nullable=False)

    # Status
    status = Column(String(20), nullable=False)  # OPEN, CLOSED, FAILED
    entry_timestamp = Column(DateTime, nullable=False)
    close_timestamp = Column(DateTime, nullable=True)

    # Position details
    entry_price_1 = Column(Float, nullable=False)
    entry_price_2 = Column(Float, nullable=False)
    entry_z_score = Column(Float, nullable=False)
    current_price_1 = Column(Float, nullable=True)
    current_price_2 = Column(Float, nullable=True)
    current_z_score = Column(Float, nullable=True)

    # Sizes and sides
    size_1 = Column(Float, nullable=False)
    size_2 = Column(Float, nullable=False)
    side_1 = Column(String(10), nullable=False)
    side_2 = Column(String(10), nullable=False)
    hedge_ratio = Column(Float, nullable=False)

    # Performance
    unrealized_pnl = Column(Float, nullable=True)
    realized_pnl = Column(Float, nullable=True)

    # Relationships
    run = relationship("BacktestRun", backref="positions")

    __table_args__ = (
        Index("idx_backtest_position_run_time", "run_id_fk", "entry_timestamp"),
        Index("idx_backtest_position_status", "run_id_fk", "status"),
    )

    def __repr__(self):
        return f"<BacktestPosition {self.position_id} - {self.status}>"


class BacktestCandle(Base):
    """Stores OHLCV candle data during backtest for accurate chart rendering and smart caching."""

    __tablename__ = "backtest_candles"

    id = Column(Integer, primary_key=True, index=True)
    run_id_fk = Column(
        Integer, ForeignKey("backtest_runs.id"), index=True, nullable=False
    )

    # Candle identification
    market = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    resolution = Column(String(20), default="1HOUR")

    # OHLCV data
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

    # Additional metrics
    trades_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    run = relationship("BacktestRun", backref="candles")

    __table_args__ = (
        Index("idx_backtest_candle_run_market", "run_id_fk", "market"),
        Index("idx_backtest_candle_market_time", "market", "timestamp"),
        Index("idx_backtest_candle_run_time", "run_id_fk", "timestamp"),
    )

    def __repr__(self):
        return f"<BacktestCandle {self.market} {self.timestamp} O:{self.open_price} C:{self.close_price}>"


class BacktestComparison(Base):
    """Stores comparisons between multiple backtest runs for strategy analysis."""

    __tablename__ = "backtest_comparisons"

    id = Column(Integer, primary_key=True, index=True)

    # Comparison identification
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    # Owner
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Strategies being compared
    strategy_id_1 = Column(
        Integer, ForeignKey("backtest_strategies.id"), nullable=False
    )
    strategy_id_2 = Column(
        Integer, ForeignKey("backtest_strategies.id"), nullable=False
    )

    # Backtest runs to compare
    run_id_1 = Column(Integer, ForeignKey("backtest_runs.id"), nullable=False)
    run_id_2 = Column(Integer, ForeignKey("backtest_runs.id"), nullable=False)

    # Comparison results (pre-calculated for performance)
    winner_run_id = Column(Integer, nullable=True)
    pnl_difference = Column(Float, nullable=True)
    sharpe_difference = Column(Float, nullable=True)
    win_rate_difference = Column(Float, nullable=True)
    drawdown_difference = Column(Float, nullable=True)

    # Detailed metrics JSON for UI display
    comparison_metrics = Column(JSON, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="comparisons")
    strategy_1 = relationship(
        "BacktestStrategy",
        foreign_keys=[strategy_id_1],
    )
    strategy_2 = relationship(
        "BacktestStrategy",
        foreign_keys=[strategy_id_2],
    )
    run_1 = relationship("BacktestRun", foreign_keys=[run_id_1])
    run_2 = relationship("BacktestRun", foreign_keys=[run_id_2])

    __table_args__ = (
        Index("idx_comparison_user_created", "user_id", "created_at"),
        Index("idx_comparison_strategies", "strategy_id_1", "strategy_id_2"),
        Index("idx_comparison_runs", "run_id_1", "run_id_2"),
    )

    def __repr__(self):
        return f"<BacktestComparison {self.name}>"

    def to_dict(self):
        """Convert comparison to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "strategy_1": {"id": self.strategy_id_1, "name": self.strategy_1.name},
            "strategy_2": {"id": self.strategy_id_2, "name": self.strategy_2.name},
            "run_1": {"id": self.run_id_1},
            "run_2": {"id": self.run_id_2},
            "winner_run_id": self.winner_run_id,
            "metrics": {
                "pnl_difference": self.pnl_difference,
                "sharpe_difference": self.sharpe_difference,
                "win_rate_difference": self.win_rate_difference,
                "drawdown_difference": self.drawdown_difference,
            },
            "created_at": self.created_at.isoformat()
            if self.created_at is not None
            else None,
            "updated_at": self.updated_at.isoformat()
            if self.updated_at is not None
            else None,
        }
