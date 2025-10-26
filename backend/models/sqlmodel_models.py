"""
SQLModel-based database models combining SQLAlchemy and Pydantic.
Provides type hints, validation, and serialization out of the box.
This is the new standard for all database models in the project.
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Column, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey, Index


# ========== Base Classes ==========

class TimestampMixin(SQLModel):
    """Mixin for common timestamp fields."""
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


# ========== User Models ==========

class DYDXKeyBase(SQLModel):
    """Base DYdX Key model with common fields."""
    network: str = Field(index=True, nullable=False)
    chain_address: str = Field(nullable=False)
    encrypted_secret: str = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)


class DYDXKey(DYDXKeyBase, TimestampMixin, table=True):
    """DYdX API key storage (encrypted)."""
    __tablename__ = "dydx_keys"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    
    # Relationship
    user: Optional["User"] = Relationship(back_populates="dydx_keys")


class DYDXKeySettingsBase(SQLModel):
    """Base DYdX Key Settings model."""
    default_network: Optional[str] = Field(default=None, nullable=True)
    auto_switch_testnet: bool = Field(default=True, nullable=False)


class DYDXKeySettings(DYDXKeySettingsBase, TimestampMixin, table=True):
    """User's DYdX key preferences."""
    __tablename__ = "dydx_key_settings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True, nullable=False)
    
    # Relationship
    user: Optional["User"] = Relationship(back_populates="dydx_key_settings")


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
    __tablename__ = "user"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str = Field(nullable=False, max_length=500)
    last_login: Optional[datetime] = Field(default=None, nullable=True)
    
    # Relationships
    dydx_keys: List[DYDXKey] = Relationship(back_populates="user", cascade_delete=True)
    dydx_key_settings: Optional[DYDXKeySettings] = Relationship(back_populates="user", cascade_delete=True)
    backtest_runs: List["BacktestRun"] = Relationship(back_populates="user", cascade_delete=True)
    backtest_strategies: List["BacktestStrategy"] = Relationship(back_populates="user", cascade_delete=True)
    audit_logs: List["AuditLog"] = Relationship(back_populates="user", cascade_delete=True)


class UserCreate(UserBase):
    """User creation schema (password in plain text)."""
    password: str = Field(min_length=8, max_length=100)


class UserRead(UserBase):
    """User read schema (for API responses)."""
    id: int
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class UserUpdate(SQLModel):
    """User update schema (partial fields)."""
    username: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=100)
    full_name: Optional[str] = Field(default=None, max_length=100)
    avatar: Optional[str] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)
    password: Optional[str] = Field(default=None, min_length=8, max_length=100)


class DYDXKeyRead(DYDXKeyBase):
    """DYdX Key read schema."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class DYDXKeyCreate(DYDXKeyBase):
    """DYdX Key creation schema."""
    user_id: int


class DYDXKeySettingsRead(DYDXKeySettingsBase):
    """DYdX Key Settings read schema."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class DYDXKeySettingsCreate(DYDXKeySettingsBase):
    """DYdX Key Settings creation schema."""
    user_id: int


# ========== Backtest Models ==========

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
    __tablename__ = "backtest_strategy"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    usage_count: int = Field(default=0)
    last_used_at: Optional[datetime] = Field(default=None, nullable=True)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="backtest_strategies")
    backtest_runs: List["BacktestRun"] = Relationship(back_populates="strategy", cascade_delete=True)


class BacktestStrategyRead(BacktestStrategyBase):
    """Backtest Strategy read schema."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class BacktestStrategyCreate(BacktestStrategyBase):
    """Backtest Strategy creation schema."""
    user_id: int


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
    __tablename__ = "backtest_run"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(foreign_key="user.id", index=True, nullable=True)
    strategy_id: Optional[int] = Field(foreign_key="backtest_strategy.id", index=True, nullable=True)
    started_at: Optional[datetime] = Field(default=None, nullable=True)
    completed_at: Optional[datetime] = Field(default=None, nullable=True)
    duration_seconds: Optional[float] = Field(default=None)
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="backtest_runs")
    strategy: Optional[BacktestStrategy] = Relationship(back_populates="backtest_runs")
    backtest_results: List["BacktestResult"] = Relationship(back_populates="backtest_run", cascade_delete=True)
    backtest_candles: List["BacktestCandle"] = Relationship(back_populates="backtest_run", cascade_delete=True)


class BacktestRunRead(BacktestRunBase):
    """Backtest Run read schema."""
    id: int
    created_at: datetime
    updated_at: datetime


class BacktestRunCreate(BacktestRunBase):
    """Backtest Run creation schema."""
    user_id: Optional[int] = None
    strategy_id: Optional[int] = None


# ========== Audit Models ==========

class AuditLogBase(SQLModel):
    """Base Audit Log model."""
    action: str = Field(index=True, nullable=False, max_length=100)
    resource_type: str = Field(nullable=False, max_length=50)
    resource_id: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(default="success", max_length=20)
    ip_address: Optional[str] = Field(default=None, max_length=50)


class AuditLog(AuditLogBase, table=True):
    """System audit trail."""
    __tablename__ = "audit_log"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(foreign_key="user.id", index=True, nullable=True)
    details: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationship
    user: Optional[User] = Relationship(back_populates="audit_logs")


class AuditLogRead(AuditLogBase):
    """Audit Log read schema."""
    id: int
    user_id: Optional[int] = None
    created_at: datetime


class AuditLogCreate(AuditLogBase):
    """Audit Log creation schema."""
    user_id: Optional[int] = None


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


class RedisSettings(RedisSettingsBase, TimestampMixin, table=True):
    """Redis cache configuration."""
    __tablename__ = "redis_settings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    last_connection_test: Optional[datetime] = Field(default=None, nullable=True)
    last_connection_status: str = Field(default="unknown", max_length=20)
    total_cache_hits: int = Field(default=0)
    total_cache_misses: int = Field(default=0)


class RedisSettingsRead(RedisSettingsBase):
    """Redis Settings read schema."""
    id: int
    created_at: datetime
    updated_at: datetime


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
    __tablename__ = "bot_setting"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    updated_by: Optional[int] = Field(foreign_key="user.id", nullable=True)


class BotSettingRead(BotSettingBase):
    """Bot Setting read schema."""
    id: int
    created_at: datetime
    updated_at: datetime


# ========== Backtest Result Models ==========

class BacktestResultBase(SQLModel):
    """Base Backtest Result model."""
    market_1: str = Field(index=True, nullable=False, max_length=50)
    market_2: str = Field(index=True, nullable=False, max_length=50)
    total_trades: Optional[int] = Field(default=0)
    profitable_trades: Optional[int] = Field(default=0)
    losing_trades: Optional[int] = Field(default=0)
    pnl: Optional[float] = Field(default=0.0)
    pnl_usd: Optional[float] = Field(default=0.0)
    win_rate: Optional[float] = Field(default=None)
    sharpe_ratio: Optional[float] = Field(default=None)
    max_drawdown: Optional[float] = Field(default=None)


class BacktestResult(BacktestResultBase, TimestampMixin, table=True):
    """Per-pair backtest results."""
    __tablename__ = "backtest_result"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id_fk: int = Field(foreign_key="backtest_run.id", index=True, nullable=False)
    
    # Relationship
    backtest_run: Optional[BacktestRun] = Relationship(back_populates="backtest_results")


class BacktestResultRead(BacktestResultBase):
    """Backtest Result read schema."""
    id: int
    run_id_fk: int
    created_at: datetime


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


class BacktestTrade(BacktestTradeBase, table=True):
    """Individual backtest trade."""
    __tablename__ = "backtest_trade"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id_fk: int = Field(foreign_key="backtest_run.id", index=True, nullable=False)
    entry_timestamp: datetime = Field(index=True, nullable=False)
    exit_timestamp: Optional[datetime] = Field(default=None, index=True, nullable=True)
    exit_price_1: Optional[float] = Field(default=None)
    exit_price_2: Optional[float] = Field(default=None)
    exit_z_score: Optional[float] = Field(default=None)
    pnl_pct: Optional[float] = Field(default=None)
    duration_hours: Optional[float] = Field(default=None)


class BacktestTradeRead(BacktestTradeBase):
    """Backtest Trade read schema."""
    id: int
    run_id_fk: int
    entry_timestamp: datetime


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
    __tablename__ = "backtest_candle"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id_fk: int = Field(foreign_key="backtest_run.id", index=True, nullable=False)
    timestamp: datetime = Field(index=True, nullable=False)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationship
    backtest_run: Optional[BacktestRun] = Relationship(back_populates="backtest_candles")


class BacktestCandleRead(BacktestCandleBase):
    """Backtest Candle read schema."""
    id: int
    run_id_fk: int
    timestamp: datetime
