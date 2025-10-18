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

    # Relationships
    results = relationship(
        "BacktestResult", back_populates="run", cascade="all, delete-orphan"
    )
    user = relationship("User", back_populates="backtest_runs")

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
