"""
User-related database models.

Models:
- User: User account for authentication and access control
- AuditLog: Track system actions for audit trail
"""

from datetime import datetime, timezone

from typing import Any, Dict

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from models.base import Base

# Use auth helpers for password hashing/verification to keep logic consistent
from auth import hash_password, verify_password


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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    # Relationships
    backtest_runs = relationship(
        "BacktestRun", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_user_active", "is_active"),)

    def __repr__(self) -> str:
        return f"<User {self.username}>"

    def to_dict(self, include_password: bool = False) -> Dict[str, Any]:
        """Return a serializable dict for the user.

        By default the returned dict excludes the hashed password. Set
        include_password=True only when you explicitly need the hash (rare).
        """
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "avatar": self.avatar,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            **({"hashed_password": self.hashed_password} if include_password else {}),
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """Return a public-safe serializable dict (never includes password/hash).

        This is handy for API responses where sensitive fields should be excluded.
        """
        data = self.to_dict(include_password=False)
        # Hide admin flag by default in public views
        data.pop("is_admin", None)
        return data

    def set_password(self, password: str) -> None:
        """Hash and set the user's password using project auth helpers."""
        if password is None:
            raise ValueError("Password cannot be None")
        self.hashed_password = hash_password(password)

    def check_password(self, password: str) -> bool:
        """Verify a plain password against the stored hash.

        Returns False if no password is set or verification fails.
        """
        if not self.hashed_password:
            return False
        try:
            return verify_password(password, self.hashed_password)
        except Exception:
            # Any unexpected verification error should be treated as a failed check
            return False

    # Provide a write-only `password` property so callers can set a plain password
    # without accidentally reading it.
    @property
    def password(self) -> None:  # pragma: no cover - intentionally write-only
        raise AttributeError("Password is write-only")

    @password.setter
    def password(self, raw: str) -> None:
        """Set password using the hashing helper (write-only)."""
        self.set_password(raw)

    def update_from_dict(self, data: Dict[str, Any], allow_password: bool = False) -> None:
        """Update model fields from a dict.

        - `allow_password` controls whether a `password` key in `data` will be
          used to update the stored password (and will be hashed).
        - Only known fields are applied. Basic validation is applied to a few
          commonly abused fields (length and simple email sanity check).
        """
        allowed_fields = [
            "username",
            "email",
            "full_name",
            "avatar",
            "is_active",
            "is_admin",
        ]

        # Basic type/length validation to catch obvious mistakes early
        if "username" in data:
            username = data.get("username")
            if username is None or not isinstance(username, str) or len(username) == 0:
                raise ValueError("username must be a non-empty string")
            if len(username) > 50:
                raise ValueError("username exceeds maximum length (50)")

        if "email" in data:
            email = data.get("email")
            if email is None or not isinstance(email, str) or len(email) == 0:
                raise ValueError("email must be a non-empty string")
            if len(email) > 100:
                raise ValueError("email exceeds maximum length (100)")
            if "@" not in email:
                # Keep this check light — more thorough validation should run at the API layer
                raise ValueError("email does not appear valid")

        for field in allowed_fields:
            if field in data:
                setattr(self, field, data[field])

        # Handle password explicitly
        if allow_password and "password" in data and data["password"] is not None:
            self.set_password(data["password"])

    # Keep backward-compatible API
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Deprecated alias for update_from_dict for compatibility with existing callers."""
        # preserve previous behavior which allowed raw hashed_password to be set
        # but prefer the safer update_from_dict usage
        if "hashed_password" in data and data["hashed_password"]:
            # Directly set hashed password if provided
            self.hashed_password = data["hashed_password"]

        # If caller provided plain password under `password`, hash it
        if "password" in data and data["password"]:
            # We allow setting password via from_dict by default (legacy behavior)
            self.set_password(data["password"])

        # Update other fields
        self.update_from_dict(data, allow_password=False)


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

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.resource_type}>"