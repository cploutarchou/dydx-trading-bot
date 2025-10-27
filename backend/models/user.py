from passlib.context import CryptContext
from datetime import datetime
from typing import Any, Dict, Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User:
    """Plain compatibility User model used by tests (no SQLModel/ORM).

    Accepts arbitrary fields as kwargs and exposes to_dict/from_dict methods.
    """

    def __init__(self, **kwargs):
        # Known fields (set to None by default)
        self.id: Optional[int] = kwargs.get("id")
        self.username: Optional[str] = kwargs.get("username")
        self.email: Optional[str] = kwargs.get("email")
        self.hashed_password: Optional[str] = kwargs.get("hashed_password")
        self.full_name: Optional[str] = kwargs.get("full_name")
        self.avatar: Optional[str] = kwargs.get("avatar")
        self.is_active: bool = kwargs.get("is_active", True)
        self.is_admin: bool = kwargs.get("is_admin", False)
        self.created_at: Optional[datetime] = kwargs.get("created_at")
        self.updated_at: Optional[datetime] = kwargs.get("updated_at")
        self.last_login: Optional[datetime] = kwargs.get("last_login")
        # Allow arbitrary extra keys
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def set_password(self, password: str) -> None:
        self.hashed_password = pwd_context.hash(password)

    def check_password(self, password: str) -> bool:
        if not self.hashed_password:
            return False
        return pwd_context.verify(password, self.hashed_password)

    def to_dict(self) -> Dict[str, Any]:
        def fmt(dt):
            if isinstance(dt, datetime):
                return dt.isoformat()
            return dt

        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "avatar": self.avatar,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": fmt(self.created_at),
            "updated_at": fmt(self.updated_at),
            "last_login": fmt(self.last_login),
            "hashed_password": self.hashed_password,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d.pop("hashed_password", None)
        d.pop("is_admin", None)
        return d

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class AuditLog:
    def __init__(self, **kwargs):
        self.id: Optional[int] = kwargs.get("id")
        self.user_id: Optional[int] = kwargs.get("user_id")
        self.action: Optional[str] = kwargs.get("action")
        self.resource_type: Optional[str] = kwargs.get("resource_type")
        self.resource_id: Optional[str] = kwargs.get("resource_id")
        self.details = kwargs.get("details")
        self.status: Optional[str] = kwargs.get("status")
        self.ip_address: Optional[str] = kwargs.get("ip_address")
        self.created_at: Optional[datetime] = kwargs.get("created_at")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "status": self.status,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        return f"<AuditLog action={self.action} user_id={self.user_id}>"