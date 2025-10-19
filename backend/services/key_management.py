"""
Secure key management service for dYdX credentials.

Handles encryption/decryption, CRUD operations, and key management.
"""

import os
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session


class KeyEncryptionService:
    """Service for encrypting and decrypting dYdX keys."""

    _cipher: Optional[Fernet] = None

    @classmethod
    def _get_cipher(cls) -> Fernet:
        """Get or create encryption cipher from environment variable."""
        if cls._cipher is None:
            # Get encryption key from environment
            encryption_key = os.getenv("DYDX_ENCRYPTION_KEY")

            if not encryption_key:
                # Generate a new key if not provided
                cls._cipher = Fernet(Fernet.generate_key())
                print(
                    "⚠️  WARNING: No DYDX_ENCRYPTION_KEY in environment. Generated new key."
                )
                print(
                    f"Set this in your .env: DYDX_ENCRYPTION_KEY={cls._cipher._signing_key.encode().decode()}"
                )
            else:
                try:
                    cls._cipher = Fernet(
                        encryption_key.encode()
                        if isinstance(encryption_key, str)
                        else encryption_key
                    )
                except Exception as e:
                    raise ValueError(f"Invalid DYDX_ENCRYPTION_KEY format: {e}")

        return cls._cipher

    @classmethod
    def encrypt(cls, secret: str) -> str:
        """Encrypt a secret string."""
        cipher = cls._get_cipher()
        return cipher.encrypt(secret.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_secret: str) -> str:
        """Decrypt a secret string."""
        cipher = cls._get_cipher()
        try:
            return cipher.decrypt(encrypted_secret.encode()).decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt secret: {e}")


class DYDXKeyService:
    """Service for managing dYdX keys in the database."""

    @staticmethod
    def create_key(
        db: Session,
        user_id: int,
        network: str,
        chain_address: str,
        secret_phrase: str,
    ):
        """Create a new dYdX key for a user."""
        from backend.models.dydx_keys import DYDXKey

        # Check if key already exists for this network
        existing_key = (
            db.query(DYDXKey)
            .filter(DYDXKey.user_id == user_id, DYDXKey.network == network)
            .first()
        )

        encrypted_secret = KeyEncryptionService.encrypt(secret_phrase)

        if existing_key:
            # Update existing key
            existing_key.chain_address = chain_address
            existing_key.encrypted_secret = encrypted_secret
            existing_key.is_active = True
            db.commit()
            return existing_key

        # Create new key
        new_key = DYDXKey(
            user_id=user_id,
            network=network,
            chain_address=chain_address,
            encrypted_secret=encrypted_secret,
            is_active=True,
        )
        db.add(new_key)
        db.commit()
        db.refresh(new_key)
        return new_key

    @staticmethod
    def get_key(db: Session, user_id: int, network: str) -> Optional[dict]:
        """Get decrypted key for a user and network."""
        from backend.models.dydx_keys import DYDXKey

        key = (
            db.query(DYDXKey)
            .filter(
                DYDXKey.user_id == user_id,
                DYDXKey.network == network,
                DYDXKey.is_active == True,
            )
            .first()
        )

        if not key:
            return None

        return {
            "id": key.id,
            "network": key.network,
            "chain_address": key.chain_address,
            "secret_phrase": KeyEncryptionService.decrypt(key.encrypted_secret),
        }

    @staticmethod
    def get_active_keys(db: Session, user_id: int) -> list:
        """Get all active keys for a user."""
        from backend.models.dydx_keys import DYDXKey

        keys = (
            db.query(DYDXKey)
            .filter(DYDXKey.user_id == user_id, DYDXKey.is_active == True)
            .all()
        )

        return [
            {
                "id": key.id,
                "network": key.network,
                "chain_address": key.chain_address,
                "created_at": key.created_at.isoformat(),
            }
            for key in keys
        ]

    @staticmethod
    def delete_key(db: Session, user_id: int, network: str) -> bool:
        """Soft delete a key."""
        from backend.models.dydx_keys import DYDXKey

        key = (
            db.query(DYDXKey)
            .filter(DYDXKey.user_id == user_id, DYDXKey.network == network)
            .first()
        )

        if not key:
            return False

        key.is_active = False
        db.commit()
        return True

    @staticmethod
    def get_key_info(db: Session, user_id: int, network: str) -> Optional[dict]:
        """Get key info without the secret (for display purposes)."""
        from backend.models.dydx_keys import DYDXKey

        key = (
            db.query(DYDXKey)
            .filter(
                DYDXKey.user_id == user_id,
                DYDXKey.network == network,
                DYDXKey.is_active == True,
            )
            .first()
        )

        if not key:
            return None

        return {
            "id": key.id,
            "network": key.network,
            "chain_address": key.chain_address,
            "is_active": key.is_active,
            "created_at": key.created_at.isoformat(),
            "updated_at": key.updated_at.isoformat(),
        }
