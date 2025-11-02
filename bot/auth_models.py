"""
Authentication Models for dYdX Trading Bot
SQLAlchemy models for user authentication, JWT tokens, and related data
"""

import os
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models import Base

# Use String for UUID on SQLite, UUID for PostgreSQL
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
if DB_TYPE == "postgresql":
    from sqlalchemy.dialects.postgresql import UUID

    def uuid_column():
        return Column(
            UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
        )

    def uuid_fk_column(fk_table):
        return Column(
            UUID(as_uuid=True),
            ForeignKey(fk_table, ondelete="CASCADE"),
            nullable=False,
            index=True,
        )

    def uuid_regular_column(nullable=True):
        return Column(UUID(as_uuid=True), nullable=nullable, index=True)
else:

    def uuid_column():
        return Column(
            String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True
        )

    def uuid_fk_column(fk_table):
        return Column(
            String(36),
            ForeignKey(fk_table, ondelete="CASCADE"),
            nullable=False,
            index=True,
        )

    def uuid_regular_column(nullable=True):
        return Column(String(36), nullable=nullable, index=True)


class User(Base):
    """User model with authentication and 2FA support"""

    __tablename__ = "users"

    id = uuid_column()
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # User status and metadata
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)

    # 2FA fields
    is_2fa_enabled = Column(Boolean, default=False, nullable=False)
    totp_secret = Column(String(32), nullable=True)  # Base32 encoded TOTP secret
    backup_codes = Column(Text, nullable=True)  # JSON array of backup codes

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Password management
    password_changed_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    jwt_tokens = relationship(
        "JWTToken", back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )
    email_verifications = relationship(
        "EmailVerification", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"

    def __str__(self):
        """String representation of user"""
        return f"{self.username} ({self.email})"


class JWTToken(Base):
    """JWT Token model for refresh token management"""

    __tablename__ = "jwt_tokens"

    id = uuid_column()
    user_id = uuid_fk_column("users.id")
    token_id = Column(
        String(50), unique=True, index=True, nullable=False
    )  # JWT 'jti' claim
    token_type = Column(String(20), nullable=False)  # 'access' or 'refresh'

    # Token metadata
    issued_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    # Client information
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="jwt_tokens")

    def __repr__(self):
        return f"<JWTToken(token_id='{self.token_id}', type='{self.token_type}')>"


class PasswordResetToken(Base):
    """Password Reset Token model"""

    __tablename__ = "password_reset_tokens"

    id = uuid_column()
    user_id = uuid_fk_column("users.id")
    token = Column(String(255), unique=True, index=True, nullable=False)

    # Token status
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Request metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")

    def __repr__(self):
        return f"<PasswordResetToken(user_id='{self.user_id}', is_used={self.is_used})>"


class LoginAttempt(Base):
    """Login Attempt model for security tracking"""

    __tablename__ = "login_attempts"

    id = uuid_column()
    username = Column(String(50), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    user_agent = Column(String(500), nullable=True)

    # Attempt details
    success = Column(Boolean, nullable=False, index=True)
    failure_reason = Column(
        String(100), nullable=True
    )  # invalid_password, user_not_found, etc.

    # 2FA details
    two_fa_required = Column(Boolean, default=False, nullable=False)
    two_fa_success = Column(Boolean, nullable=True)

    # Timestamp
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<LoginAttempt(username='{self.username}', success={self.success})>"


class EmailVerification(Base):
    """Email Verification model"""

    __tablename__ = "email_verifications"

    id = uuid_column()
    user_id = uuid_fk_column("users.id")

    # Verification tokens
    verification_token = Column(String(255), unique=True, index=True, nullable=False)
    verification_code = Column(String(6), nullable=False)  # 6-digit code

    # Token status
    is_verified = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Verification context
    purpose = Column(
        String(50), nullable=False
    )  # '2fa_setup', 'password_reset', 'account_activation'

    # Request metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="email_verifications")

    def __repr__(self):
        return f"<EmailVerification(user_id='{self.user_id}', purpose='{self.purpose}', is_verified={self.is_verified})>"


# Create indexes for better performance
Index("ix_jwt_tokens_user_type", JWTToken.user_id, JWTToken.token_type)
Index("ix_jwt_tokens_expires", JWTToken.expires_at)
Index("ix_password_reset_expires", PasswordResetToken.expires_at)
Index("ix_login_attempts_time", LoginAttempt.created_at)
Index("ix_login_attempts_ip_time", LoginAttempt.ip_address, LoginAttempt.created_at)
Index("ix_email_verification_expires", EmailVerification.expires_at)
Index("ix_email_verification_purpose", EmailVerification.purpose)
Index(
    "ix_email_verification_user_purpose",
    EmailVerification.user_id,
    EmailVerification.purpose,
)
