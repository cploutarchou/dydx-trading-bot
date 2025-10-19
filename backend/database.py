"""
Database configuration and models for backtest results storage.
Supports both SQLite (development) and PostgreSQL (production).
"""

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

# Database URL configuration
DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # sqlite or postgresql
DB_NAME = os.getenv("DB_NAME", "dydx_backtest.db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

if DB_TYPE == "postgresql":
    db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    DATABASE_URL = db_url
else:
    # SQLite - create file in app directory
    db_path = os.path.join(os.path.dirname(__file__), "..", "app", DB_NAME)
    DATABASE_URL = f"sqlite:///{db_path}"

log_msg = (
    f"Using database: {DB_TYPE} - "
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

    # Relationships
    results = relationship(
        "BacktestResult", back_populates="run", cascade="all, delete-orphan"
    )
    user = relationship("User", back_populates="backtest_runs")
    strategy = relationship(
        "BacktestStrategy", back_populates="runs", foreign_keys=[strategy_id]
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
    hashed_password = Column(String(255), nullable=False)

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

    # Backtesting parameters
    transaction_fee = Column(Float, nullable=False, default=0.0005)
    slippage = Column(Float, nullable=False, default=0.001)
    starting_balance = Column(Float, nullable=False, default=1000.0)
    candle_resolution = Column(String(20), nullable=False, default="1HOUR")
    max_history_days = Column(Integer, nullable=False, default=90)

    # Additional strategy metadata
    benchmark_symbol = Column(String(20), default="BTC-USD")
    risk_free_rate = Column(Float, nullable=False, default=0.02)

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
            "is_public": self.is_public,
            "is_default": self.is_default,
            "parameters": {
                "zscore_threshold": self.zscore_threshold,
                "stats_window": self.stats_window,
                "max_half_life": self.max_half_life,
                "usd_per_trade": self.usd_per_trade,
                "usd_min_collateral": self.usd_min_collateral,
                "close_at_zscore_cross": self.close_at_zscore_cross,
                "transaction_fee": self.transaction_fee,
                "slippage": self.slippage,
                "starting_balance": self.starting_balance,
                "candle_resolution": self.candle_resolution,
                "max_history_days": self.max_history_days,
                "benchmark_symbol": self.benchmark_symbol,
                "risk_free_rate": self.risk_free_rate,
            },
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat()
            if self.last_used_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Database engine and session factory
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DB_TYPE == "sqlite" else {},
    pool_pre_ping=True,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database - create all tables and seed default admin user."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")

    # Seed default admin user on first run
    _seed_admin_user()


def _seed_admin_user():
    """Create default admin user if it doesn't exist."""
    from backend.auth import hash_password

    db = SessionLocal()
    try:
        # Check if admin user already exists
        admin_exists = db.query(User).filter(User.username == "admin").first()

        if not admin_exists:
            # Create default admin user
            hashed_password = hash_password("admin123")
            admin_user = User(
                username="admin",
                email="admin@dydx-backtest.local",
                hashed_password=hashed_password,
                is_active=True,
                is_admin=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(admin_user)
            db.commit()
            logger.info(
                "✅ Default admin user created: username=admin, password=admin123"
            )
        else:
            logger.info("ℹ️  Admin user already exists, skipping creation")
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
