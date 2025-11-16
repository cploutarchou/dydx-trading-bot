"""
SQLAlchemy ORM Models for Trading Bot
Tracks: Bot instances, jobs, trades, and execution history
"""

from datetime import datetime
from enum import Enum

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

Base = declarative_base()


class BotStatusEnum(str, Enum):
    """Bot instance status"""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    ERROR = "error"


class JobStatusEnum(str, Enum):
    """Job execution status"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"


class TradeStatusEnum(str, Enum):
    """Trade execution status"""

    PENDING = "pending"
    OPENED = "opened"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BotInstance(Base):
    """Tracks individual bot instances"""

    __tablename__ = "bot_instances"
    __table_args__ = (
        Index("ix_bot_status", "status"),
        Index("ix_bot_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(
        SQLEnum(BotStatusEnum), default=BotStatusEnum.CREATED, nullable=False
    )

    # Process information
    process_id = Column(Integer, nullable=True)
    process_started_at = Column(DateTime, nullable=True)
    process_ended_at = Column(DateTime, nullable=True)

    # Configuration
    network = Column(String(32), nullable=False)
    strategy = Column(String(128), nullable=False)
    config_json = Column(JSON, nullable=True)

    # Trading parameters
    usd_per_trade = Column(Float, nullable=True)
    zscore_threshold = Column(Float, nullable=True)
    max_positions = Column(Integer, default=10)

    # Statistics
    total_trades = Column(Integer, default=0)
    successful_trades = Column(Integer, default=0)
    failed_trades = Column(Integer, default=0)
    total_profit_loss = Column(Float, default=0.0)

    # Wallet information
    wallet_address = Column(String(128), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)

    # Relationships
    jobs = relationship(
        "Job", back_populates="bot_instance", cascade="all, delete-orphan"
    )
    trades = relationship(
        "Trade", back_populates="bot_instance", cascade="all, delete-orphan"
    )
    events = relationship(
        "EventLog", back_populates="bot_instance", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<BotInstance {self.instance_id} - {self.status}>"


class Job(Base):
    """Tracks bot execution jobs"""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_job_bot_id", "bot_instance_id"),
        Index("ix_job_status", "status"),
        Index("ix_job_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    bot_instance_id = Column(Integer, ForeignKey("bot_instances.id"), nullable=False)

    # Job information
    job_type = Column(String(64), nullable=False)
    status = Column(
        SQLEnum(JobStatusEnum), default=JobStatusEnum.QUEUED, nullable=False
    )

    # Process tracking
    process_id = Column(Integer, nullable=True)
    process_started_at = Column(DateTime, nullable=True)
    process_ended_at = Column(DateTime, nullable=True)

    # Job parameters and results
    parameters = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Performance metrics
    execution_time_ms = Column(Integer, nullable=True)
    memory_used_mb = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    bot_instance = relationship("BotInstance", back_populates="jobs")

    def __repr__(self):
        return f"<Job {self.job_id} - {self.status}>"


class Trade(Base):
    """Tracks individual trades"""

    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trade_bot_id", "bot_instance_id"),
        Index("ix_trade_status", "status"),
        Index("ix_trade_opened", "opened_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(64), unique=True, nullable=False, index=True)
    bot_instance_id = Column(Integer, ForeignKey("bot_instances.id"), nullable=False)

    # Trade pair information
    pair1 = Column(String(32), nullable=False)
    pair2 = Column(String(32), nullable=False)

    # Trade details
    status = Column(
        SQLEnum(TradeStatusEnum), default=TradeStatusEnum.PENDING, nullable=False
    )
    entry_price1 = Column(Float, nullable=True)
    entry_price2 = Column(Float, nullable=True)
    entry_size1 = Column(Float, nullable=True)
    entry_size2 = Column(Float, nullable=True)

    # Exit information
    exit_price1 = Column(Float, nullable=True)
    exit_price2 = Column(Float, nullable=True)
    exit_size1 = Column(Float, nullable=True)
    exit_size2 = Column(Float, nullable=True)

    # P&L tracking
    entry_cost = Column(Float, nullable=True)
    exit_proceeds = Column(Float, nullable=True)
    profit_loss = Column(Float, default=0.0)
    profit_loss_percentage = Column(Float, default=0.0)

    # Fees
    entry_fees = Column(Float, default=0.0)
    exit_fees = Column(Float, default=0.0)

    # On-chain information
    entry_tx_hash = Column(String(128), nullable=True)
    exit_tx_hash = Column(String(128), nullable=True)
    dydx_position_id = Column(String(128), nullable=True)

    # Cointegration metrics
    zscore_entry = Column(Float, nullable=True)
    half_life_days = Column(Float, nullable=True)
    correlation = Column(Float, nullable=True)

    # Timestamps
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Relationships
    bot_instance = relationship("BotInstance", back_populates="trades")

    def calculate_duration(self):
        """Calculate trade duration if closed"""
        if self.closed_at and self.opened_at:
            self.duration_seconds = int(
                (self.closed_at - self.opened_at).total_seconds()
            )

    def __repr__(self):
        return f"<Trade {self.trade_id} - {self.pair1}/{self.pair2}>"


class EventLog(Base):
    """Audit log for all bot events"""

    __tablename__ = "event_logs"
    __table_args__ = (
        Index("ix_event_bot_id", "bot_instance_id"),
        Index("ix_event_type", "event_type"),
        Index("ix_event_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(Integer, ForeignKey("bot_instances.id"), nullable=False)

    # Event information
    event_type = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False)

    # Event details
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)

    # Context
    user_id = Column(String(128), nullable=True)
    related_job_id = Column(String(64), nullable=True)
    related_trade_id = Column(String(64), nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    bot_instance = relationship("BotInstance", back_populates="events")

    def __repr__(self):
        return f"<EventLog {self.event_type} - {self.severity}>"


class SystemMetrics(Base):
    """Track system-wide metrics and performance"""

    __tablename__ = "system_metrics"
    __table_args__ = (Index("ix_metrics_timestamp", "timestamp"),)

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Metrics
    total_bots_running = Column(Integer, default=0)
    total_active_trades = Column(Integer, default=0)
    total_profit_loss = Column(Float, default=0.0)

    # System resources
    cpu_usage_percent = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    memory_usage_percent = Column(Float, nullable=True)

    # Database
    database_size_mb = Column(Float, nullable=True)
    connection_count = Column(Integer, default=0)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<SystemMetrics {self.timestamp}>"


class DailyReport(Base):
    """Daily trading reports"""

    __tablename__ = "daily_reports"
    __table_args__ = (Index("ix_report_bot_date", "bot_instance_id", "report_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(Integer, ForeignKey("bot_instances.id"), nullable=False)

    # Report date
    report_date = Column(DateTime, nullable=False, unique=True)

    # Daily statistics
    trades_opened = Column(Integer, default=0)
    trades_closed = Column(Integer, default=0)
    successful_trades = Column(Integer, default=0)
    failed_trades = Column(Integer, default=0)

    # P&L
    daily_profit_loss = Column(Float, default=0.0)
    cumulative_profit_loss = Column(Float, default=0.0)

    # Jobs
    jobs_completed = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)

    # Uptime
    uptime_seconds = Column(Integer, default=0)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<DailyReport {self.report_date}>"
