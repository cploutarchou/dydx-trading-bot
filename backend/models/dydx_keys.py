"""
Secure key management models for dYdX credentials.

Stores testnet and mainnet keys encrypted with Fernet symmetric encryption.
"""

from datetime import datetime, timezone

from cryptography.fernet import Fernet
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from models.base import Base


class DYDXKey(Base):
    """Securely stores dYdX testnet and mainnet keys per user."""

    __tablename__ = "dydx_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "network", name="uq_user_network_keys"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    network = Column(String(50), index=True, nullable=False)  # testnet, mainnet
    chain_address = Column(String(255), nullable=False)
    encrypted_secret = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship to User
    user = relationship("User", back_populates="dydx_keys")

    @staticmethod
    def encrypt_secret(secret: str, cipher: Fernet) -> str:
        """Encrypt a secret string using Fernet."""
        return cipher.encrypt(secret.encode()).decode()

    @staticmethod
    def decrypt_secret(encrypted_secret: str, cipher: Fernet) -> str:
        """Decrypt a secret string using Fernet."""
        return cipher.decrypt(encrypted_secret.encode()).decode()

    def get_decrypted_secret(self, cipher: Fernet) -> str:
        """Get the decrypted secret for this key."""
        return self.decrypt_secret(self.encrypted_secret, cipher)

    def __repr__(self) -> str:
        return f"<DYDXKey(user_id={self.user_id}, network={self.network}, address={self.chain_address[:10]}...)>"

    def to_dict(self, include_secret: bool = False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "network": self.network,
            "chain_address": self.chain_address,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_secret:
            data["encrypted_secret"] = self.encrypted_secret
        return data

    def from_dict(self, data: dict):
        for k in ["user_id", "network", "chain_address", "encrypted_secret", "is_active"]:
            if k in data:
                setattr(self, k, data[k])


class DYDXKeySettings(Base):
    """Stores user preferences for dYdX key usage."""

    __tablename__ = "dydx_key_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    default_network = Column(String(50), default="testnet", nullable=False)
    auto_switch_testnet = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship to User
    user = relationship("User", back_populates="dydx_key_settings")

    def __repr__(self) -> str:
        return f"<DYDXKeySettings(user_id={self.user_id}, default_network={self.default_network})>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "default_network": self.default_network,
            "auto_switch_testnet": self.auto_switch_testnet,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def from_dict(self, data: dict):
        for k in ["user_id", "default_network", "auto_switch_testnet"]:
            if k in data:
                setattr(self, k, data[k])