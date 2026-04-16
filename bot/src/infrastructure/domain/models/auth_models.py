"""
Authentication models for dYdX Trading Bot.

SQLAlchemy models for user authentication, JWT tokens, and related data.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from internal.domain import Base
from src.shared.time_utils import utc_now


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    tokens = relationship(
        "UserToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def is_superuser(self) -> bool:
        """Backward-compatible alias used by middleware/routes."""
        return bool(self.is_admin)

    @is_superuser.setter
    def is_superuser(self, value: bool) -> None:
        self.is_admin = bool(value)


class UserToken(Base):
    """JWT token model for refresh tokens."""

    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token = Column(Text, nullable=False, unique=True)
    token_type = Column(String(20), default="refresh")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    is_revoked = Column(Boolean, default=False)

    user = relationship("User", back_populates="tokens")
