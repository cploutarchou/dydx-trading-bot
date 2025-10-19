"""
Secure key management models for dYdX credentials.

Stores testnet and mainnet keys encrypted with Fernet symmetric encryption.
"""

from datetime import datetime

from cryptography.fernet import Fernet
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class DYDXKey(Base):
    """Securely stores dYdX testnet and mainnet keys per user."""

    __tablename__ = "dydx_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "network", name="uq_user_network_keys"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), index=True, nullable=False
    )
    network: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # testnet, mainnet
    chain_address: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship to User
    user: Mapped["User"] = relationship("User", back_populates="dydx_keys")

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


class DYDXKeySettings(Base):
    """Stores user preferences for dYdX key usage."""

    __tablename__ = "dydx_key_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), unique=True, index=True, nullable=False
    )
    default_network: Mapped[str] = mapped_column(
        String(50), default="testnet", nullable=False
    )  # Default network
    auto_switch_testnet: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship to User
    user: Mapped["User"] = relationship("User", back_populates="dydx_key_settings")

    def __repr__(self) -> str:
        return f"<DYDXKeySettings(user_id={self.user_id}, default_network={self.default_network})>"
