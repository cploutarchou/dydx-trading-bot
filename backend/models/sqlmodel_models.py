"""
SQLModel-based database models combining SQLAlchemy and Pydantic.
Production-ready models matching PostgreSQL schema.
Provides type hints, validation, and serialization out of the box.
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Column, JSON


# ========== Base Classes ==========

class TimestampMixin(SQLModel):
    """Mixin for common timestamp fields."""
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


# ========== User Models ==========

class UserBase(SQLModel):
    """Base User model with common fields."""
    username: str = Field(unique=True, index=True, nullable=False, max_length=50)
    email: str = Field(unique=True, index=True, nullable=False, max_length=100)
    full_name: Optional[str] = Field(default=None, max_length=100)
    avatar: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True, index=True)
    is_admin: bool = Field(default=False)


class User(UserBase, TimestampMixin, table=True):
    """User account for authentication and access control."""
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str = Field(nullable=False, max_length=500)
    last_login: Optional[datetime] = Field(default=None, nullable=True)
    
    # Relationships
    dydx_keys: List["DYDXKey"] = Relationship(back_populates="user", cascade_delete=True)
    dydx_key_settings: Optional["DYDXKeySettings"] = Relationship(back_populates="user", cascade_delete=True)
    backtest_runs: List["BacktestRun"] = Relationship(back_populates="user", cascade_delete=True)
    backtest_strategies: List["BacktestStrategy"] = Relationship(back_populates="user", cascade_delete=True)
    audit_logs: List["AuditLog"] = Relationship(back_populates="user", cascade_delete=True)
    bot_settings: List["BotSetting"] = Relationship(back_populates="updated_by_user", cascade_delete=True)
    backtest_comparisons: List["BacktestComparison"] = Relationship(back_populates="user", cascade_delete=True)
    strategy_version_history: List["StrategyVersionHistory"] = Relationship(back_populates="created_by_user", cascade_delete=True)


class DYDXKeyBase(SQLModel):
    """Base DYdX Key model with common fields."""
    network: str = Field(index=True, nullable=False, max_length=50)
    chain_address: str = Field(nullable=False, max_length=255)
    encrypted_secret: str = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)


class DYDXKey(DYDXKeyBase, TimestampMixin, table=True):
    """DYdX API key storage (encrypted)."""
    __tablename__ = "dydx_keys"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    
    # Relationship
    user: Optional[User] = Relationship(back_populates="dydx_keys")


class DYDXKeySettingsBase(SQLModel):
    """Base DYdX Key Settings model."""
    default_network: Optional[str] = Field(default=None, nullable=True, max_length=50)
    auto_switch_testnet: bool = Field(default=True, nullable=False)


class DYDXKeySettings(DYDXKeySettingsBase, TimestampMixin, table=True):
    """User's DYdX key preferences."""
    __tablename__ = "dydx_key_settings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True, nullable=False)
    
    # Relationship
    user: Optional[User] = Relationship(back_populates="dydx_key_settings")


# ========== Backtest Strategy Models ==========

class BacktestStrategyBase(SQLModel):
    """Base Backtest Strategy model."""
    name: str = Field(index=True, nullable=False, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, max_length=50)
    is_public: bool = Field(default=False)
    is_default: bool = Field(default=False)
    
    # Strategy parameters
    zscore_threshold: float = Field(default=1.5, nullable=False)
    stats_window: int = Field(default=21, nullable=False)
    max_half_life: float = Field(default=24.0, nullable=False)
    usd_per_trade: float = Field(default=10.0, nullable=False)
    usd_min_collateral: float = Field(default=100.0, nullable=False)
    close_at_zscore_cross: bool = Field(default=True, nullable=False)
    find_cointegrated_pairs: bool = Field(default=True, nullable=False)
    manage_exits: bool = Field(default=True, nullable=False)
    place_trades: bool = Field(default=True, nullable=False)
    abort_all_positions: bool = Field(default=False, nullable=False)
    max_positions: int = Field(default=5, nullable=False)
    max_drawdown_pct: float = Field(default=15.0, nullable=False)
    stop_loss_pct: float = Field(default=2.0, nullable=False)
    take_profit_pct: float = Field(default=5.0, nullable=False)
    trailing_stop_pct: float = Field(default=1.0, nullable=False)
    rebalance_interval_hours: int = Field(default=24, nullable=False)
    position_timeout_hours: int = Field(default=72, nullable=False)
    transaction_fee: float = Field(default=0.0005, nullable=False)
    slippage: float = Field(default=0.001, nullable=False)
    starting_balance: float = Field(default=1000.0, nullable=False)
    candle_resolution: str = Field(default="1HOUR", nullable=False, max_length=20)
    max_history_days: int = Field(default=90, nullable=False)
    benchmark_symbol: Optional[str] = Field(default="BTC-USD", max_length=20)
    risk_free_rate: float = Field(default=0.02, nullable=False)
    initial_amount: float = Field(default=1000.0, nullable=False)


class BacktestStrategy(BacktestStrategyBase, TimestampMixin, table=True):
    """Reusable backtest strategy configuration."""
    __tablename__ = "backtest_strategies"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    usage_count: Optional[int] = Field(default=0)
    last_used_at: Optional[datetime] = Field(default=None, nullable=True)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="backtest_strategies")
    backtest_runs: List["BacktestRun"] = Relationship(back_populates="strategy", cascade_delete=True)
    backtest_comparisons_1: List["BacktestComparison"] = Relationship(
        back_populates="strategy_1", foreign_key="backtest_comparisons.strategy_id_1", cascade_delete=True
    )
    backtest_comparisons_2: List["BacktestComparison"] = Relationship(
        back_populates="strategy_2", foreign_key="backtest_comparisons.strategy_id_2", cascade_delete=True
    )
    strategy_execution_state: Optional["StrategyExecutionState"] = Relationship(back_populates="strategy", cascade_delete=True)
    strategy_version_history: List["StrategyVersionHistory"] = Relationship(back_populates="strategy", cascade_delete=True)


# ========== Backtest Run Models ==========

class BacktestRunBase(SQLModel):
    """Base Backtest Run model."""
    run_id: str = Field(unique=True, index=True, nullable=False, max_length=50)
    status: Optional[str] = Field(default="running", index=True, max_length=20)
    start_date: str = Field(nullable=False, max_length=10)
    end_date: str = Field(nullable=False, max_length=10)
    num_pairs: int = Field(nullable=False)
    total_markets: int = Field(nullable=False)
    resolution: str = Field(default="1HOUR", nullable=False, max_length=20)
    
    # Results
    total_trades: Optional[int] = Field(default=0)
    profitable_trades: Optional[int] = Field(default=0)
    losing_trades: Optional[int] = Field(default=0)
    win_rate: Optional[float] = Field(default=None)
    total_pnl: Optional[float] = Field(default=0.0)
    total_pnl_usd: Optional[float] = Field(default=0.0)
    sharpe_ratio: Optional[float] = Field(default=None)
    sortino_ratio: Optional[float] = Field(default=None)
    calmar_ratio: Optional[float] = Field(default=None)
    max_drawdown: Optional[float] = Field(default=None)
    profit_factor: Optional[float] = Field(default=None)
    starting_balance: Optional[float] = Field(default=1000.0)
    ending_balance: Optional[float] = Field(default=None)
    max_balance: Optional[float] = Field(default=None)
    min_balance: Optional[float] = Field(default=None)
    error_message: Optional[str] = Field(default=None)


class BacktestRun(BacktestRunBase, TimestampMixin, table=True):
    """Individual backtest execution run."""
    __tablename__ = "backtest_runs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(foreign_key="users.id", index=True, nullable=True)
    strategy_id: Optional[int] = Field(foreign_key="backtest_strategies.id", index=True, nullable=True)
    strategy_version_id: Optional[int] = Field(foreign_key="strategy_version_history.id", index=True, nullable=True)
    started_at: Optional[datetime] = Field(default=None, nullable=True)
    completed_at: Optional[datetime] = Field(default=None, nullable=True)
    duration_seconds: Optional[float] = Field(default=None)
    config: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    strategy_snapshot: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="backtest_runs")
    strategy: Optional[BacktestStrategy] = Relationship(back_populates="backtest_runs")
    strategy_version_history: Optional["StrategyVersionHistory"] = Relationship(back_populates="backtest_runs")
    backtest_results: List["BacktestResult"] = Relationship(back_populates="backtest_run", cascade_delete=True)
    backtest_candles: List["BacktestCandle"] = Relationship(back_populates="backtest_run", cascade_delete=True)
    backtest_logs: List["BacktestLog"] = Relationship(back_populates="backtest_run", cascade_delete=True)
    backtest_positions: List["BacktestPosition"] = Relationship(back_populates="backtest_run", cascade_delete=True)
    backtest_trades: List["BacktestTrade"] = Relationship(back_populates="backtest_run", cascade_delete=True)


# ========== Backtest Result Models ==========

class BacktestResultBase(SQLModel):
    """Base Backtest Result model."""
    market_1: str = Field(index=True, nullable=False, max_length=50)
    market_2: str = Field(index=True, nullable=False, max_length=50)
    total_trades: Optional[int] = Field(default=0)
    entry_trades: Optional[int] = Field(default=0)
    exit_trades: Optional[int] = Field(default=0)
    profitable_trades: Optional[int] = Field(default=0)
    losing_trades: Optional[int] = Field(default=0)
    pnl: Optional[float] = Field(default=0.0)
    pnl_usd: Optional[float] = Field(default=0.0)
    win_rate: Optional[float] = Field(default=None)
    avg_win: Optional[float] = Field(default=None)
    avg_loss: Optional[float] = Field(default=None)
    profit_factor: Optional[float] = Field(default=None)
    max_drawdown: Optional[float] = Field(default=None)
    sharpe_ratio: Optional[float] = Field(default=None)
    sortino_ratio: Optional[float] = Field(default=None)
    calmar_ratio: Optional[float] = Field(default=None)
    avg_trade_duration_hours: Optional[float] = Field(default=None)
    avg_winning_trade_duration: Optional[float] = Field(default=None)
    avg_losing_trade_duration: Optional[float] = Field(default=None)
    cointegration_score: Optional[float] = Field(default=None)
    correlation: Optional[float] = Field(default=None)
    zscore_mean: Optional[float] = Field(default=None)
    zscore_std: Optional[float] = Field(default=None)


class BacktestResult(BacktestResultBase, TimestampMixin, table=True):
    """Per-pair backtest results."""
    __tablename__ = "backtest_results"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id_fk: int = Field(foreign_key="backtest_runs.id", index=True, nullable=False)
    
    # Relationship
    backtest_run: Optional[BacktestRun] = Relationship(back_populates="backtest_results")
    trade_logs: List["TradeLog"] = Relationship(back_populates="backtest_result", cascade_delete=True)


# ========== Backtest Trade Models ==========

class BacktestTradeBase(SQLModel):
    """Base Backtest Trade model."""
    trade_id: str = Field(unique=True, index=True, nullable=False, max_length=100)
    market_1: str = Field(index=True, nullable=False, max_length=50)
    market_2: str = Field(index=True, nullable=False, max_length=50)
    entry_price_1: float = Field(nullable=False)
    entry_price_2: float = Field(nullable=False)
    entry_z_score: float = Field(nullable=False)
    side_1: str = Field(nullable=False, max_length=10)
    side_2: str = Field(nullable=False, max_length=10)
    size_1: float = Field(nullable=False)
    size_2: float = Field(nullable=False)
    hedge_ratio: float = Field(nullable=False)
    transaction_fee: float = Field(nullable=False)
    slippage: float = Field(nullable=False)
    pnl: Optional[float] = Field(default=None)
    pnl_pct: Optional[float] = Field(default=None)
    duration_hours: Optional[float] = Field(default=None)


class BacktestTrade(BacktestTradeBase, table=True):
    """Individual backtest trade."""
    __tablename__ = "backtest_trades"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id_fk: int = Field(foreign_key="backtest_runs.id", index=True, nullable=False)
    entry_timestamp: datetime = Field(index=True, nullable=False)
    exit_timestamp: Optional[datetime] = Field(default=None, index=True, nullable=True)
    exit_price_1: Optional[float] = Field(default=None)
    exit_price_2: Optional[float] = Field(default=None)
    exit_z_score: Optional[float] = Field(default=None)
    
    # Relationship
    backtest_run: Optional[BacktestRun] = Relationship(back_populates="backtest_trades")


# ========== Backtest Candle Models ==========

class BacktestCandleBase(SQLModel):
    """Base Backtest Candle model."""
    market: str = Field(index=True, nullable=False, max_length=255)
    resolution: Optional[str] = Field(default="1HOUR", max_length=20)
    open_price: float = Field(nullable=False)
    high_price: float = Field(nullable=False)
    low_price: float = Field(nullable=False)
    close_price: float = Field(nullable=False)
    volume: float = Field(nullable=False)
    trades_count: Optional[int] = Field(default=None)


class BacktestCandle(BacktestCandleBase, table=True):
    """OHLCV price data for backtest."""
    __tablename__ = "backtest_candles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id_fk: int = Field(foreign_key="backtest_runs.id", index=True, nullable=False)
    timestamp: datetime = Field(index=True, nullable=False)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationship
    backtest_run: Optional[BacktestRun] = Relationship(back_populates="backtest_candles")


# ========== Backtest Log Models ==========

class BacktestLogBase(SQLModel):
    """Base Backtest Log model."""
    message: str = Field(nullable=False)
    level: Optional[str] = Field(default=None, max_length=20)


class BacktestLog(BacktestLogBase, table=True):
    """Backtest execution logs."""
    __tablename__ = "backtest_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id_fk: int = Field(foreign_key="backtest_runs.id", index=True, nullable=False)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationship
    backtest_run: Optional[BacktestRun] = Relationship(back_populates="backtest_logs")


# ========== Backtest Position Models ==========

class BacktestPositionBase(SQLModel):
    """Base Backtest Position model."""
    position_id: str = Field(unique=True, index=True, nullable=False, max_length=100)
    market_1: str = Field(nullable=False, max_length=50)
    market_2: str = Field(nullable=False, max_length=50)
    status: str = Field(nullable=False, max_length=20)
    entry_price_1: float = Field(nullable=False)
    entry_price_2: float = Field(nullable=False)
    entry_z_score: float = Field(nullable=False)
    current_price_1: Optional[float] = Field(default=None)
    current_price_2: Optional[float] = Field(default=None)
    current_z_score: Optional[float] = Field(default=None)
    size_1: float = Field(nullable=False)
    size_2: float = Field(nullable=False)
    side_1: str = Field(nullable=False, max_length=10)
    side_2: str = Field(nullable=False, max_length=10)
    hedge_ratio: float = Field(nullable=False)
    unrealized_pnl: Optional[float] = Field(default=None)
    realized_pnl: Optional[float] = Field(default=None)


class BacktestPosition(BacktestPositionBase, table=True):
    """Open positions during backtest."""
    __tablename__ = "backtest_positions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id_fk: int = Field(foreign_key="backtest_runs.id", index=True, nullable=False)
    entry_timestamp: datetime = Field(index=True, nullable=False)
    close_timestamp: Optional[datetime] = Field(default=None, nullable=True)
    
    # Relationship
    backtest_run: Optional[BacktestRun] = Relationship(back_populates="backtest_positions")


# ========== Backtest Comparison Models ==========

class BacktestComparisonBase(SQLModel):
    """Base Backtest Comparison model."""
    name: str = Field(index=True, nullable=False, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    winner_run_id: Optional[int] = Field(default=None)
    pnl_difference: Optional[float] = Field(default=None)
    sharpe_difference: Optional[float] = Field(default=None)
    win_rate_difference: Optional[float] = Field(default=None)
    drawdown_difference: Optional[float] = Field(default=None)
    comparison_metrics: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class BacktestComparison(BacktestComparisonBase, TimestampMixin, table=True):
    """Comparison of two backtest runs."""
    __tablename__ = "backtest_comparisons"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    strategy_id_1: int = Field(foreign_key="backtest_strategies.id", nullable=False)
    strategy_id_2: int = Field(foreign_key="backtest_strategies.id", nullable=False)
    run_id_1: int = Field(foreign_key="backtest_runs.id", nullable=False)
    run_id_2: int = Field(foreign_key="backtest_runs.id", nullable=False)
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="backtest_comparisons")
    strategy_1: Optional[BacktestStrategy] = Relationship(back_populates="backtest_comparisons_1")
    strategy_2: Optional[BacktestStrategy] = Relationship(back_populates="backtest_comparisons_2")


# ========== Trade Log Models ==========

class TradeLogBase(SQLModel):
    """Base Trade Log model."""
    trade_number: int = Field(nullable=False)
    entry_price_1: float = Field(nullable=False)
    entry_price_2: float = Field(nullable=False)
    exit_price_1: Optional[float] = Field(default=None)
    exit_price_2: Optional[float] = Field(default=None)
    quantity_1: float = Field(nullable=False)
    quantity_2: float = Field(nullable=False)
    side_1: str = Field(nullable=False, max_length=10)
    side_2: str = Field(nullable=False, max_length=10)
    pnl: Optional[float] = Field(default=None)
    pnl_usd: Optional[float] = Field(default=None)
    entry_zscore: Optional[float] = Field(default=None)
    exit_zscore: Optional[float] = Field(default=None)


class TradeLog(TradeLogBase, table=True):
    """Individual trade logs from backtest results."""
    __tablename__ = "trade_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    result_id_fk: int = Field(foreign_key="backtest_results.id", index=True, nullable=False)
    entry_timestamp: datetime = Field(nullable=False)
    exit_timestamp: Optional[datetime] = Field(default=None, nullable=True)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationship
    backtest_result: Optional[BacktestResult] = Relationship(back_populates="trade_logs")


# ========== Audit Log Models ==========

class AuditLogBase(SQLModel):
    """Base Audit Log model."""
    action: str = Field(index=True, nullable=False, max_length=100)
    resource_type: str = Field(nullable=False, max_length=50)
    resource_id: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(default="success", max_length=20)
    ip_address: Optional[str] = Field(default=None, max_length=50)


class AuditLog(AuditLogBase, table=True):
    """System audit trail."""
    __tablename__ = "audit_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(foreign_key="users.id", index=True, nullable=True)
    details: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationship
    user: Optional[User] = Relationship(back_populates="audit_logs")


# ========== Redis Settings Models ==========

class RedisSettingsBase(SQLModel):
    """Base Redis Settings model."""
    enabled: bool = Field(default=True, index=True)
    host: str = Field(default="localhost", max_length=255)
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = Field(default=None, max_length=255)
    ssl: bool = Field(default=False)
    timeout: int = Field(default=5)
    max_connections: int = Field(default=10)
    cache_ttl_seconds: int = Field(default=86400)
    cache_backtest_results: bool = Field(default=True)
    cache_market_data: bool = Field(default=True)
    cache_analysis_results: bool = Field(default=True)
    last_connection_test: Optional[datetime] = Field(default=None)
    last_connection_status: str = Field(default="unknown", max_length=20)
    total_cache_hits: int = Field(default=0)
    total_cache_misses: int = Field(default=0)


class RedisSettings(RedisSettingsBase, TimestampMixin, table=True):
    """Redis cache configuration."""
    __tablename__ = "redis_settings"
    
    id: Optional[int] = Field(default=None, primary_key=True)


# ========== Bot Settings Models ==========

class BotSettingBase(SQLModel):
    """Base Bot Setting model."""
    section: str = Field(index=True, nullable=False, max_length=50)
    key: str = Field(index=True, nullable=False, max_length=100)
    value: str = Field(nullable=False)
    value_type: str = Field(nullable=False, max_length=20)
    description: Optional[str] = Field(default=None)
    default_value: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True, index=True)
    version: int = Field(default=1)


class BotSetting(BotSettingBase, TimestampMixin, table=True):
    """Bot configuration settings."""
    __tablename__ = "bot_settings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    updated_by: Optional[int] = Field(foreign_key="users.id", nullable=True)
    
    # Relationship
    updated_by_user: Optional[User] = Relationship(back_populates="bot_settings")


# ========== Strategy Execution State Models ==========

class StrategyExecutionStateBase(SQLModel):
    """Base Strategy Execution State model."""
    enabled: Optional[bool] = Field(default=None)
    status: Optional[str] = Field(default=None, max_length=20)
    trades_executed: Optional[int] = Field(default=0)
    pnl: Optional[float] = Field(default=None)
    pnl_pct: Optional[float] = Field(default=None)
    last_error: Optional[str] = Field(default=None, max_length=500)
    error_count: Optional[int] = Field(default=0)
    last_error_at: Optional[datetime] = Field(default=None)
    config_snapshot: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    last_started: Optional[datetime] = Field(default=None)
    last_stopped: Optional[datetime] = Field(default=None)
    last_trade_at: Optional[datetime] = Field(default=None)
    uptime_seconds: Optional[int] = Field(default=0)
    last_cointegration_check: Optional[datetime] = Field(default=None)
    active_pairs_count: Optional[int] = Field(default=0)
    open_positions_count: Optional[int] = Field(default=0)
    max_drawdown: Optional[float] = Field(default=None)
    sharpe_ratio: Optional[float] = Field(default=None)
    win_rate: Optional[float] = Field(default=None)


class StrategyExecutionState(StrategyExecutionStateBase, TimestampMixin, table=True):
    """Strategy execution state tracking."""
    __tablename__ = "strategy_execution_states"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    strategy_id: int = Field(foreign_key="backtest_strategies.id", index=True, nullable=False)
    
    # Relationship
    strategy: Optional[BacktestStrategy] = Relationship(back_populates="strategy_execution_state")


# ========== Strategy Version History Models ==========

class StrategyVersionHistoryBase(SQLModel):
    """Base Strategy Version History model."""
    version_number: int = Field(nullable=False)
    change_description: Optional[str] = Field(default=None, max_length=500)
    config_snapshot: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    changes: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    backtest_count: Optional[int] = Field(default=None)
    best_backtest_pnl: Optional[float] = Field(default=None)
    average_backtest_pnl: Optional[float] = Field(default=None)


class StrategyVersionHistory(StrategyVersionHistoryBase, TimestampMixin, table=True):
    """Strategy version history tracking."""
    __tablename__ = "strategy_version_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    strategy_id: int = Field(foreign_key="backtest_strategies.id", index=True, nullable=False)
    created_by_user_id: Optional[int] = Field(foreign_key="users.id", nullable=True)
    
    # Relationships
    strategy: Optional[BacktestStrategy] = Relationship(back_populates="strategy_version_history")
    created_by_user: Optional[User] = Relationship(back_populates="strategy_version_history")
    backtest_runs: List[BacktestRun] = Relationship(back_populates="strategy_version_history")


# Export all models
__all__ = [
    "SQLModel", "Field", "Relationship", "Column", "JSON",
    "TimestampMixin",
    "User", "UserBase",
    "DYDXKey", "DYDXKeyBase", "DYDXKeySettings", "DYDXKeySettingsBase",
    "BacktestStrategy", "BacktestStrategyBase",
    "BacktestRun", "BacktestRunBase",
    "BacktestResult", "BacktestResultBase",
    "BacktestTrade", "BacktestTradeBase",
    "BacktestCandle", "BacktestCandleBase",
    "BacktestLog", "BacktestLogBase",
    "BacktestPosition", "BacktestPositionBase",
    "BacktestComparison", "BacktestComparisonBase",
    "TradeLog", "TradeLogBase",
    "AuditLog", "AuditLogBase",
    "RedisSettings", "RedisSettingsBase",
    "BotSetting", "BotSettingBase",
    "StrategyExecutionState", "StrategyExecutionStateBase",
    "StrategyVersionHistory", "StrategyVersionHistoryBase",
]