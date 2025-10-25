"""
Strategy-related database models.

Models:
- BacktestStrategy: Reusable backtest strategy configurations
- StrategyVersionHistory: Audit trail of strategy configuration changes
- StrategyExecutionState: Runtime execution state of strategies
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import relationship

from .base import Base


class BacktestStrategy(Base):
    """Stores reusable backtest strategy configurations for quick testing and comparison."""

    __tablename__ = "backtest_strategies"

    id = Column(Integer, primary_key=True, index=True)

    # Strategy identification
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    category = Column(
        String(50), default="custom"
    )  # custom, conservative, balanced, aggressive

    # Owner and visibility
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    is_public = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)

    # Strategy parameters - all configurable values from config.yaml
    zscore_threshold = Column(Float, nullable=False, default=1.5)
    stats_window = Column(Integer, nullable=False, default=21)
    max_half_life = Column(Float, nullable=False, default=24.0)
    usd_per_trade = Column(Float, nullable=False, default=10.0)
    usd_min_collateral = Column(Float, nullable=False, default=100.0)
    close_at_zscore_cross = Column(Boolean, nullable=False, default=True)
    find_cointegrated_pairs = Column(Boolean, nullable=False, default=True)
    manage_exits = Column(Boolean, nullable=False, default=True)
    place_trades = Column(Boolean, nullable=False, default=True)
    abort_all_positions = Column(Boolean, nullable=False, default=False)

    # Risk management parameters
    max_positions = Column(Integer, nullable=False, default=5)
    max_drawdown_pct = Column(Float, nullable=False, default=15.0)
    stop_loss_pct = Column(Float, nullable=False, default=2.0)
    take_profit_pct = Column(Float, nullable=False, default=5.0)
    trailing_stop_pct = Column(Float, nullable=False, default=1.0)
    rebalance_interval_hours = Column(Integer, nullable=False, default=24)
    position_timeout_hours = Column(Integer, nullable=False, default=72)

    # Backtesting parameters
    transaction_fee = Column(Float, nullable=False, default=0.0005)
    slippage = Column(Float, nullable=False, default=0.001)
    starting_balance = Column(Float, nullable=False, default=1000.0)
    candle_resolution = Column(String(20), nullable=False, default="1HOUR")
    max_history_days = Column(Integer, nullable=False, default=90)

    # Additional strategy metadata
    benchmark_symbol = Column(String(20), default="BTC-USD")
    risk_free_rate = Column(Float, nullable=False, default=0.02)

    # Initial investment amount - tracks the capital allocated to this strategy
    initial_amount = Column(Float, nullable=False, default=1000.0)

    # Usage statistics
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete support

    # Relationships
    user = relationship("User", backref="strategies")
    runs = relationship(
        "BacktestRun",
        back_populates="strategy",
        foreign_keys="BacktestRun.strategy_id",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_strategy_user_name", "user_id", "name"),
        Index("idx_strategy_public", "is_public"),
        Index("idx_strategy_default", "is_default"),
        Index("idx_strategy_category", "category"),
    )

    def __repr__(self):
        return f"<BacktestStrategy {self.name} (User: {self.user_id})>"

    def to_dict(self):
        """Convert strategy to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "user_id": self.user_id,
            "is_public": self.is_public,
            "is_default": self.is_default,
            "resolution": self.candle_resolution,
            "zscore_threshold": self.zscore_threshold,
            "stats_window": self.stats_window,
            "max_half_life": self.max_half_life,
            "usd_per_trade": self.usd_per_trade,
            "usd_min_collateral": self.usd_min_collateral,
            "close_at_zscore_cross": self.close_at_zscore_cross,
            "find_cointegrated_pairs": self.find_cointegrated_pairs,
            "manage_exits": self.manage_exits,
            "place_trades": self.place_trades,
            "abort_all_positions": self.abort_all_positions,
            "max_positions": self.max_positions,
            "max_drawdown_pct": self.max_drawdown_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "trailing_stop_pct": self.trailing_stop_pct,
            "rebalance_interval_hours": self.rebalance_interval_hours,
            "position_timeout_hours": self.position_timeout_hours,
            "initial_amount": self.initial_amount,
            "transaction_fee": self.transaction_fee,
            "slippage": self.slippage,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat()
            if self.last_used_at is not None
            else None,
            "created_at": self.created_at.isoformat()
            if self.created_at is not None
            else None,
            "updated_at": self.updated_at.isoformat()
            if self.updated_at is not None
            else None,
        }


class StrategyVersionHistory(Base):
    """Audit trail of strategy configuration changes for version control and reproducibility.

    Each time a strategy is edited, a new version is saved. This allows:
    - Tracking which config generated each backtest result
    - Reverting to previous strategy versions
    - Comparing strategy versions side-by-side
    - Understanding config evolution over time
    """

    __tablename__ = "strategy_version_history"

    id = Column(Integer, primary_key=True, index=True)

    # Reference to the strategy
    strategy_id = Column(
        Integer, ForeignKey("backtest_strategies.id"), nullable=False, index=True
    )

    # Version metadata
    version_number = Column(Integer, nullable=False)  # 1, 2, 3, etc.
    change_description = Column(String(500), nullable=True)  # Why was this changed?

    # Complete config snapshot at this version
    config_snapshot = Column(JSON, nullable=False)  # Full strategy config

    # Track what changed (optional, for UI diff display)
    changes = Column(
        JSON, nullable=True
    )  # {"zscore_threshold": {"old": 1.5, "new": 2.0}}

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # Which user made this change

    # Optional: backtest results using this version
    backtest_count = Column(Integer, default=0)
    best_backtest_pnl = Column(Float, nullable=True)
    average_backtest_pnl = Column(Float, nullable=True)

    # Relationships
    strategy = relationship(
        "BacktestStrategy", backref="version_history", foreign_keys=[strategy_id]
    )
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        Index("idx_strategy_version", "strategy_id", "version_number"),
        Index("idx_strategy_version_created", "strategy_id", "created_at"),
    )

    def __repr__(self):
        return f"<StrategyVersionHistory Strategy:{self.strategy_id} v{self.version_number}>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "version_number": self.version_number,
            "change_description": self.change_description,
            "config_snapshot": self.config_snapshot,
            "changes": self.changes,
            "created_at": self.created_at.isoformat()
            if self.created_at is not None
            else None,
            "created_by_user_id": self.created_by_user_id,
            "backtest_count": self.backtest_count,
            "best_backtest_pnl": self.best_backtest_pnl,
            "average_backtest_pnl": self.average_backtest_pnl,
        }


class StrategyExecutionState(Base):
    """Stores runtime execution state of strategies for persistent tracking and real-time updates.

    Updated by strategy executor threads and queried by WebSocket broadcasts.
    Survives bot restarts via database persistence.
    """

    __tablename__ = "strategy_execution_states"

    id = Column(Integer, primary_key=True, index=True)

    # Strategy reference
    strategy_id = Column(
        Integer, ForeignKey("backtest_strategies.id"), nullable=False, index=True
    )

    # Execution state
    enabled = Column(
        Boolean, default=False, index=True
    )  # Is strategy currently active?
    status = Column(
        String(20), default="stopped", index=True
    )  # stopped, running, paused, error

    # Execution statistics
    trades_executed = Column(Integer, default=0)  # Total trades from this strategy
    pnl = Column(Float, default=0.0)  # Cumulative profit/loss in USD
    pnl_pct = Column(Float, default=0.0)  # PnL as percentage

    # Error tracking
    last_error = Column(String(500), nullable=True)  # Latest error message
    error_count = Column(Integer, default=0)  # Total errors encountered
    last_error_at = Column(DateTime, nullable=True)  # When last error occurred

    # Configuration snapshot
    config_snapshot = Column(JSON, nullable=True)  # Full strategy config at runtime

    # Timing information
    last_started = Column(DateTime, nullable=True)  # When strategy was last started
    last_stopped = Column(DateTime, nullable=True)  # When strategy was last stopped
    last_trade_at = Column(DateTime, nullable=True)  # Timestamp of last executed trade
    uptime_seconds = Column(Integer, default=0)  # How long strategy has been running

    # Market data state
    last_cointegration_check = Column(
        DateTime, nullable=True
    )  # When pairs were last analyzed
    active_pairs_count = Column(
        Integer, default=0
    )  # Number of active cointegrated pairs
    open_positions_count = Column(Integer, default=0)  # Number of open positions

    # Performance metrics (updated in real-time)
    max_drawdown = Column(Float, nullable=True)  # Maximum drawdown reached
    sharpe_ratio = Column(Float, nullable=True)  # Calculated Sharpe ratio
    win_rate = Column(Float, nullable=True)  # Win rate percentage

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True
    )

    # Relationships
    strategy = relationship("BacktestStrategy", backref="execution_state")

    __table_args__ = (
        Index("idx_execution_state_strategy_enabled", "strategy_id", "enabled"),
        Index("idx_execution_state_status", "strategy_id", "status"),
        Index("idx_execution_state_updated", "updated_at"),
    )

    def __repr__(self):
        return f"<StrategyExecutionState strategy_id={self.strategy_id} status={self.status}>"

    def to_dict(self):
        """Convert execution state to dictionary for WebSocket broadcasts and API responses."""
        return {
            "strategyId": self.strategy_id,
            "enabled": self.enabled,
            "status": self.status,
            "tradesExecuted": self.trades_executed,
            "pnl": self.pnl,
            "pnlPct": self.pnl_pct,
            "lastError": self.last_error,
            "errorCount": self.error_count,
            "lastErrorAt": self.last_error_at.isoformat()
            if self.last_error_at is not None
            else None,
            "lastStarted": self.last_started.isoformat()
            if self.last_started is not None
            else None,
            "lastStopped": self.last_stopped.isoformat()
            if self.last_stopped is not None
            else None,
            "lastTradeAt": self.last_trade_at.isoformat()
            if self.last_trade_at is not None
            else None,
            "uptimeSeconds": self.uptime_seconds,
            "activePairsCount": self.active_pairs_count,
            "openPositionsCount": self.open_positions_count,
            "maxDrawdown": self.max_drawdown,
            "sharpeRatio": self.sharpe_ratio,
            "winRate": self.win_rate,
            "updatedAt": self.updated_at.isoformat()
            if self.updated_at is not None
            else None,
        }
