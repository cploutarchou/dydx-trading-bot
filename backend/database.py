"""
Database configuration and models for backtest results storage.
Supports both SQLite (development) and PostgreSQL (production).
"""

# ⚠️ CRITICAL: Load environment variables FIRST, before any other imports
# This ensures DB_* environment variables are available for database configuration
from dotenv import load_dotenv

load_dotenv()

import logging
import os
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


def get_database_url() -> str:
    """Get database URL from config.yaml or environment variables.

    Priority:
    1. config.yaml (database section)
    2. Environment variables (DB_*)
    3. Built-in defaults

    Returns:
        SQLAlchemy database URL
    """
    try:
        from backend.config_loader import get_config_loader

        config_loader = get_config_loader()
        db_config = config_loader.get_database_config()
    except ImportError:
        # Fallback to direct environment variables
        db_config = {
            "type": os.getenv("DB_TYPE", "sqlite"),
            "name": os.getenv("DB_NAME", "dydx_backtest.db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
        }

    db_type = db_config.get("type", "sqlite")
    db_name = db_config.get("name", "dydx_backtest.db")
    db_user = db_config.get("user", "postgres")
    db_password = db_config.get("password", "")
    db_host = db_config.get("host", "localhost")
    db_port = db_config.get("port", "5432")

    if db_type == "postgresql":
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        # SQLite - create file in app directory
        db_path = os.path.join(os.path.dirname(__file__), "..", "app", db_name)
        db_url = f"sqlite:///{db_path}"

    return db_url


# Get database configuration and log it
DATABASE_URL = get_database_url()
log_msg = (
    f"Using database: {os.getenv('DB_TYPE', 'sqlite')} - "
    f"{DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}"
)
logger.info(log_msg)


class BacktestRun(Base):
    """Represents a single backtest execution run."""

    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Execution info
    run_id = Column(String(50), unique=True, index=True, nullable=False)
    # running, completed, failed
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
    resolution = Column(
        String(20), default="1HOUR"
    )  # 1MIN, 5MINS, 15MINS, 1HOUR, 4HOURS, 1DAY
    # Configuration snapshot
    config = Column(JSON, nullable=True)  # Store full config used

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

    # Strategy tracking (Phase 1 enhancement)
    strategy_id = Column(
        Integer, ForeignKey("backtest_strategies.id"), nullable=True, index=True
    )
    strategy_snapshot = Column(
        JSON, nullable=True
    )  # Store strategy config at runtime for reproducibility
    strategy_version_id = Column(
        Integer, ForeignKey("strategy_version_history.id"), nullable=True, index=True
    )  # Track which strategy version was used for this backtest

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

    # Indexes for common queries
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

    # Indexes
    __table_args__ = (
        Index("idx_result_pair", "market_1", "market_2"),
        Index("idx_result_run_profit", "run_id_fk", "pnl"),
    )

    def __repr__(self):
        return f"<BacktestResult {self.market_1}/{self.market_2}>"


class TradeLog(Base):
    """Individual trade executed during backtesting."""

    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key
    result_id_fk = Column(
        Integer, ForeignKey("backtest_results.id"), index=True, nullable=False
    )

    # Trade details
    trade_number = Column(Integer, nullable=False)
    entry_timestamp = Column(DateTime, nullable=False)
    exit_timestamp = Column(DateTime, nullable=True)

    # Position details
    entry_price_1 = Column(Float, nullable=False)
    entry_price_2 = Column(Float, nullable=False)
    exit_price_1 = Column(Float, nullable=True)
    exit_price_2 = Column(Float, nullable=True)

    quantity_1 = Column(Float, nullable=False)
    quantity_2 = Column(Float, nullable=False)

    side_1 = Column(String(10), nullable=False)  # BUY or SELL
    side_2 = Column(String(10), nullable=False)

    # PnL
    pnl = Column(Float, nullable=True)
    pnl_usd = Column(Float, nullable=True)

    # Entry/Exit signals
    entry_zscore = Column(Float, nullable=True)
    exit_zscore = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    result = relationship("BacktestResult", back_populates="trades")

    __table_args__ = (Index("idx_trade_result", "result_id_fk", "entry_timestamp"),)

    def __repr__(self):
        return f"<TradeLog #{self.trade_number}>"


class User(Base):
    """User account for authentication and access control."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(500), nullable=False)

    # Profile information
    full_name = Column(String(100), nullable=True)
    avatar = Column(Text, nullable=True)  # Base64 encoded image data

    # Account status
    is_active = Column(Boolean, default=True, index=True)
    is_admin = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    backtest_runs = relationship(
        "BacktestRun", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_user_active", "is_active"),)

    def __repr__(self):
        return f"<User {self.username}>"


class BacktestLog(Base):
    """Stores logs from backtest execution for real-time display."""

    __tablename__ = "backtest_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id_fk = Column(
        Integer, ForeignKey("backtest_runs.id"), index=True, nullable=False
    )

    # Log content
    message = Column(String, nullable=False)
    level = Column(String(20), default="info")  # debug, info, warning, error

    # Timestamp when log was created
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
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
    # FIXED: Increased from String(50) to String(255) to accommodate long market names
    # Example: "FARTCOIN,RAYDIUM,9BB6NFECJBCTNNLFKO2FQVQBQ8HHM13KCYYCDQBGPUMP-USD" (61 chars)
    market = Column(
        String(255), nullable=False, index=True
    )  # e.g., "BTC-USD" or comma-separated markets
    timestamp = Column(DateTime, nullable=False, index=True)
    resolution = Column(
        String(20), default="1HOUR"
    )  # 1MIN, 5MINS, 15MINS, 1HOUR, 4HOURS, 1DAY

    # OHLCV data
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

    # Additional metrics
    trades_count = Column(Integer, nullable=True)  # Number of trades in the candle

    # Timestamp when inserted
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


class BotSetting(Base):
    """Stores bot configuration settings securely in database instead of YAML."""

    __tablename__ = "bot_settings"

    id = Column(Integer, primary_key=True, index=True)

    # Setting identification
    section = Column(
        String(50), nullable=False, index=True
    )  # botSettings, backtesting, etc.
    key = Column(String(100), nullable=False, index=True)

    # Value storage
    value = Column(String, nullable=False)  # JSON serialized
    value_type = Column(String(20), nullable=False)  # string, float, int, boolean, json

    # Metadata
    description = Column(String, nullable=True)
    default_value = Column(String, nullable=True)

    # Active version tracking
    is_active = Column(Boolean, default=True, index=True)
    version = Column(Integer, default=1)  # For change tracking

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # User who made the change
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("idx_bot_setting_section_key", "section", "key"),
        Index("idx_bot_setting_active", "is_active"),
    )

    def __repr__(self):
        return f"<BotSetting {self.section}.{self.key}>"


class AuditLog(Base):
    """Track system actions for audit trail."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    status = Column(String(20), default="success")  # success, failure
    ip_address = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )

    def __repr__(self):
        return f"<AuditLog {self.action} on {self.resource_type}>"


class RedisSetting(Base):
    """Stores Redis configuration and connection settings."""

    __tablename__ = "redis_settings"

    id = Column(Integer, primary_key=True, index=True)

    # Redis connection parameters
    enabled = Column(Boolean, default=True, index=True)
    host = Column(String(255), default="localhost")
    port = Column(Integer, default=6379)
    db = Column(Integer, default=0)
    password = Column(String(255), nullable=True)  # Encrypted in production
    ssl = Column(Boolean, default=False)

    # Connection and performance settings
    timeout = Column(Integer, default=5)  # seconds
    max_connections = Column(Integer, default=10)
    cache_ttl_seconds = Column(Integer, default=86400)  # 24 hours

    # Feature flags
    cache_backtest_results = Column(Boolean, default=True)
    cache_market_data = Column(Boolean, default=True)
    cache_analysis_results = Column(Boolean, default=True)

    # Statistics and monitoring
    last_connection_test = Column(DateTime, nullable=True)
    last_connection_status = Column(
        String(20), default="unknown"
    )  # connected, failed, disabled
    total_cache_hits = Column(Integer, default=0)
    total_cache_misses = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_redis_enabled", "enabled"),)

    def __repr__(self):
        return f"<RedisSetting {self.host}:{self.port}/{self.db}>"


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
    winner_run_id = Column(Integer, nullable=True)  # Which run performed better
    pnl_difference = Column(Float, nullable=True)  # Run1 PnL - Run2 PnL
    sharpe_difference = Column(Float, nullable=True)  # Run1 Sharpe - Run2 Sharpe
    win_rate_difference = Column(Float, nullable=True)  # Run1 Win Rate - Run2 Win Rate
    drawdown_difference = Column(Float, nullable=True)  # Run1 Drawdown - Run2 Drawdown

    # Detailed metrics JSON for UI display
    comparison_metrics = Column(JSON, nullable=True)  # Store detailed metric comparison

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


# Database engine and session factory
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database - create all tables and seed default admin user."""
    try:
        # Create all tables that don't exist
        # This is safe to run even if tables already exist - SQLAlchemy won't recreate them
        Base.metadata.create_all(bind=engine)

        # Log all tables that should exist
        inspector = __import__("sqlalchemy", fromlist=["inspect"]).inspect
        inspector_obj = inspector(engine)
        existing_tables = inspector_obj.get_table_names()

        logger.info("✅ Database initialized successfully")
        logger.info(
            f"   Existing tables ({len(existing_tables)}): {', '.join(sorted(existing_tables))}"
        )

        # Verify all expected model tables exist
        expected_tables = {table.name for table in Base.metadata.tables.values()}
        missing_tables = expected_tables - set(existing_tables)

        if missing_tables:
            logger.warning(f"⚠️  Missing tables: {', '.join(sorted(missing_tables))}")
        else:
            logger.info(f"✅ All {len(expected_tables)} expected tables present")

    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}", exc_info=True)
        raise

    # Seed default admin user on first run
    _seed_admin_user()


def _seed_admin_user():
    """Create default admin user if it doesn't exist.

    Behavior:
    - Uses environment variables ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL when provided.
    - If ADMIN_PASSWORD is not set, generate a secure random password and save it to
      `app/admin_credentials.txt` with restrictive permissions (0o600).
    - Never log the plaintext password to logs. Log only the username and the path
      where credentials were saved (if generated).
    - Idempotent: will not recreate admin if a user with the same username exists.
    """
    from backend.auth import hash_password
    import secrets
    from pathlib import Path

    db = SessionLocal()
    try:
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@dydx-backtest.local")
        admin_password = os.getenv("ADMIN_PASSWORD", None)

        # Check if admin user already exists
        admin_exists = db.query(User).filter(User.username == admin_username).first()

        if admin_exists:
            logger.info(f"ℹ️  Admin user '{admin_username}' already exists, skipping creation")
            return

        generated_password_path = None
        if not admin_password:
            # Generate a secure random password and persist it to a local file with restricted permissions
            admin_password = secrets.token_urlsafe(16)
            try:
                cred_path = Path(__file__).resolve().parents[1] / "app" / "admin_credentials.txt"
                cred_path.parent.mkdir(parents=True, exist_ok=True)
                with cred_path.open("w", encoding="utf-8") as f:
                    f.write(f"username: {admin_username}\n")
                    f.write(f"password: {admin_password}\n")
                    f.write(f"email: {admin_email}\n")
                    f.write(f"created_at: {datetime.utcnow().isoformat()}Z\n")
                # Restrict file permissions to owner read/write
                try:
                    cred_path.chmod(0o600)
                except Exception:
                    # chmod may not be available on all filesystems (e.g., Windows/NTFS mount)
                    logger.debug("Could not set file permissions on admin credentials file; please secure it manually")
                generated_password_path = str(cred_path)
            except Exception as e:
                logger.warning(f"Could not write admin credentials to file: {e}")

        # Create default admin user
        hashed_password = hash_password(admin_password)
        admin_user = User(
            username=admin_username,
            email=admin_email,
            hashed_password=hashed_password,
            is_active=True,
            is_admin=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(admin_user)
        db.commit()

        if generated_password_path:
            logger.info(
                f"✅ Default admin user created: username={admin_username}. Credentials saved to {generated_password_path}"
            )
        else:
            logger.info(
                f"✅ Default admin user created: username={admin_username}." " (password provided via ADMIN_PASSWORD)"
            )

    except Exception as e:
        logger.error(f"❌ Error seeding admin user: {e}")
        db.rollback()
    finally:
        db.close()


def get_db():
    """Dependency injection for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """Context manager for database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
