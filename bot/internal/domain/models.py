"""
Core database models for the trading bot system
"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    ForeignKey, Enum, JSON
)
from sqlalchemy.orm import relationship
from . import Base


class BotStatusEnum(enum.Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class JobStatusEnum(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TradeStatusEnum(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String(50), unique=True, nullable=False, index=True)
    network = Column(String(20), nullable=False)  # testnet, mainnet
    strategy = Column(String(50), nullable=False)
    config = Column(JSON, nullable=False)
    status = Column(Enum(BotStatusEnum), default=BotStatusEnum.CREATED)
    process_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="bot", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="bot", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    job_type = Column(String(50), nullable=False)
    status = Column(Enum(JobStatusEnum), default=JobStatusEnum.PENDING)
    config = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    bot = relationship("Bot", back_populates="jobs")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    position_id = Column(String(100), nullable=False, index=True)
    pair1 = Column(String(20), nullable=False)
    pair2 = Column(String(20), nullable=False)
    side1 = Column(String(10), nullable=False)  # BUY, SELL
    side2 = Column(String(10), nullable=False)  # BUY, SELL
    entry_price1 = Column(Float, nullable=False)
    entry_price2 = Column(Float, nullable=False)
    exit_price1 = Column(Float, nullable=True)
    exit_price2 = Column(Float, nullable=True)
    entry_size1 = Column(Float, nullable=False)
    entry_size2 = Column(Float, nullable=False)
    exit_size1 = Column(Float, nullable=True)
    exit_size2 = Column(Float, nullable=True)
    status = Column(Enum(TradeStatusEnum), default=TradeStatusEnum.OPEN)
    realized_pnl = Column(Float, default=0.0)
    realized_pnl_pct = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    bot = relationship("Bot", back_populates="trades")
