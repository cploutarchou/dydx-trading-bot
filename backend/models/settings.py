"""
Settings-related database models.

Models:
- BotSetting: Stores bot configuration settings securely in database
- RedisSetting: Stores Redis configuration and connection settings
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String

from backend.models.base import Base


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
