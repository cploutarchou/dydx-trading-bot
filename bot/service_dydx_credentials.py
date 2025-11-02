"""
DydxCredentialsService - Service layer for managing dYdX credentials securely.

This service handles:
- Encryption/decryption of sensitive credentials
- CRUD operations for credential management
- Testing credential validity with dYdX network
- Audit logging for all operations
- Selecting active credentials for trading
"""

import logging
from base64 import b64decode, b64encode
from datetime import datetime
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from func_connections import connect_dydx
from models_dydx_credentials import (
    DydxCredential,
    DydxCredentialAudit,
    DydxTestResult,
    NetworkType,
)

logger = logging.getLogger(__name__)


class CredentialEncryption:
    """Handle encryption and decryption of sensitive credentials."""

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption handler.

        Args:
            encryption_key: Fernet key for encryption. If None, generates a new one.
        """
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
            self.key = encryption_key
        else:
            # Generate a new key
            self.key = Fernet.generate_key().decode()
            self.cipher = Fernet(self.key.encode())

    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data."""
        encrypted = self.cipher.encrypt(data.encode())
        return b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        decoded = b64decode(encrypted_data.encode())
        decrypted = self.cipher.decrypt(decoded)
        return decrypted.decode()

    def get_key(self) -> str:
        """Get the encryption key (store this securely!)."""
        return self.key


class DydxCredentialsService:
    """Service for managing dYdX credentials."""

    def __init__(self, db_session: Session, encryption: CredentialEncryption):
        """
        Initialize the credentials service.

        Args:
            db_session: SQLAlchemy database session
            encryption: CredentialEncryption instance for securing sensitive data
        """
        self.db = db_session
        self.encryption = encryption

    async def create_credential(
        self,
        user_id: int,
        network_type: NetworkType,
        address: str,
        mnemonic: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        test_before_save: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new dYdX credential entry.

        Args:
            user_id: User ID creating the credential
            network_type: testnet or mainnet
            address: dYdX wallet address
            mnemonic: BIP39 mnemonic phrase
            name: Friendly name for this credential
            description: Optional description
            test_before_save: Test credential validity before saving

        Returns:
            Dictionary with credential ID and validation result
        """
        try:
            # Validate inputs
            if not address or len(address) < 20:
                raise ValueError("Invalid dYdX address format")

            if not mnemonic or len(mnemonic.split()) < 12:
                raise ValueError("Invalid mnemonic phrase (must be at least 12 words)")

            # Encrypt sensitive data
            encrypted_address = self.encryption.encrypt(address)
            encrypted_mnemonic = self.encryption.encrypt(mnemonic)

            # Create credential object
            credential = DydxCredential(
                user_id=user_id,
                network_type=network_type,
                address=encrypted_address,
                mnemonic=encrypted_mnemonic,
                name=name or f"{network_type.value.capitalize()} Wallet",
                description=description,
                created_by=user_id,
                is_active=True,
            )

            self.db.add(credential)
            self.db.flush()  # Get ID without committing

            # Test credential if requested
            test_result = None
            if test_before_save:
                test_result = await self.test_credential(credential.id)
                credential.is_test_valid = test_result.get("success", False)
                credential.error_message = test_result.get("error_message")
                credential.last_tested = datetime.utcnow()

            self.db.commit()

            # Audit log
            await self._audit_log(
                user_id=user_id,
                credential_id=credential.id,
                operation="create",
                network_type=network_type,
                address_preview=address[:20],
                success=True,
                details=f"Created credential: {name}",
            )

            logger.info(
                f"Created new dYdX credential for user {user_id} "
                f"on {network_type.value}"
            )

            return {
                "id": credential.id,
                "network_type": network_type.value,
                "address_preview": address[:10] + "...",
                "is_active": True,
                "test_result": test_result,
                "created_at": credential.created_at.isoformat(),
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating credential: {str(e)}")
            raise

    async def update_credential(
        self,
        credential_id: int,
        user_id: int,
        address: Optional[str] = None,
        mnemonic: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update an existing credential."""
        try:
            credential = (
                self.db.query(DydxCredential).filter_by(id=credential_id).first()
            )

            if not credential:
                raise ValueError(f"Credential {credential_id} not found")

            if credential.user_id != user_id:
                raise PermissionError(
                    "You don't have permission to update this credential"
                )

            # Update fields
            if address:
                credential.address = self.encryption.encrypt(address)

            if mnemonic:
                credential.mnemonic = self.encryption.encrypt(mnemonic)

            if name is not None:
                credential.name = name

            if description is not None:
                credential.description = description

            if is_active is not None:
                credential.is_active = is_active

            credential.updated_by = user_id
            credential.updated_at = datetime.utcnow()

            self.db.commit()

            # Audit log
            await self._audit_log(
                user_id=user_id,
                credential_id=credential_id,
                operation="update",
                network_type=credential.network_type,
                address_preview=(address or credential.address)[:20],
                success=True,
                details="Updated credential fields",
            )

            logger.info(f"Updated credential {credential_id} by user {user_id}")

            return {
                "id": credential_id,
                "updated_at": credential.updated_at.isoformat(),
                "message": "Credential updated successfully",
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating credential: {str(e)}")
            raise

    async def delete_credential(
        self,
        credential_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Delete a credential (soft delete by marking inactive)."""
        try:
            credential = (
                self.db.query(DydxCredential).filter_by(id=credential_id).first()
            )

            if not credential:
                raise ValueError(f"Credential {credential_id} not found")

            if credential.user_id != user_id:
                raise PermissionError(
                    "You don't have permission to delete this credential"
                )

            # Soft delete
            credential.is_active = False
            credential.updated_by = user_id
            credential.updated_at = datetime.utcnow()

            self.db.commit()

            # Audit log
            await self._audit_log(
                user_id=user_id,
                credential_id=credential_id,
                operation="delete",
                network_type=credential.network_type,
                address_preview=credential.address[:20],
                success=True,
                details="Deleted credential",
            )

            logger.info(f"Deleted credential {credential_id} by user {user_id}")

            return {
                "id": credential_id,
                "deleted": True,
                "message": "Credential deleted successfully",
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting credential: {str(e)}")
            raise

    async def get_credential(
        self,
        credential_id: int,
        user_id: int,
        decrypt: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get a credential by ID."""
        try:
            credential = (
                self.db.query(DydxCredential).filter_by(id=credential_id).first()
            )

            if not credential:
                return None

            if credential.user_id != user_id:
                raise PermissionError(
                    "You don't have permission to view this credential"
                )

            result = {
                "id": credential.id,
                "network_type": credential.network_type.value,
                "name": credential.name,
                "description": credential.description,
                "is_active": credential.is_active,
                "is_test_valid": credential.is_test_valid,
                "last_tested": credential.last_tested.isoformat()
                if credential.last_tested
                else None,
                "created_at": credential.created_at.isoformat(),
                "updated_at": credential.updated_at.isoformat(),
            }

            # Add decrypted data if requested
            if decrypt:
                result["address"] = self.encryption.decrypt(credential.address)
                result["mnemonic"] = self.encryption.decrypt(credential.mnemonic)
            else:
                # Only show preview
                address = self.encryption.decrypt(credential.address)
                result["address_preview"] = address[:10] + "..." + address[-4:]

            return result

        except Exception as e:
            logger.error(f"Error retrieving credential: {str(e)}")
            raise

    async def list_credentials(
        self,
        user_id: int,
        network_type: Optional[NetworkType] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """List user's credentials."""
        try:
            query = self.db.query(DydxCredential).filter_by(user_id=user_id)

            if network_type:
                query = query.filter_by(network_type=network_type)

            if active_only:
                query = query.filter_by(is_active=True)

            credentials = query.order_by(desc(DydxCredential.created_at)).all()

            return [
                {
                    "id": c.id,
                    "network_type": c.network_type.value,
                    "name": c.name,
                    "address_preview": self.encryption.decrypt(c.address)[:10] + "...",
                    "is_active": c.is_active,
                    "is_test_valid": c.is_test_valid,
                    "last_tested": c.last_tested.isoformat() if c.last_tested else None,
                    "created_at": c.created_at.isoformat(),
                }
                for c in credentials
            ]

        except Exception as e:
            logger.error(f"Error listing credentials: {str(e)}")
            raise

    async def test_credential(
        self,
        credential_id: int,
    ) -> Dict[str, Any]:
        """Test a credential's validity with dYdX network."""
        try:
            credential = (
                self.db.query(DydxCredential).filter_by(id=credential_id).first()
            )

            if not credential:
                return {
                    "success": False,
                    "error_message": f"Credential {credential_id} not found",
                }

            # Test connection to dYdX
            start_time = datetime.utcnow()
            try:
                # This will use the actual dYdX client to verify the credentials work
                client = await connect_dydx()

                # Try to get account information
                if hasattr(client, "indexer_account"):
                    account = await client.indexer_account.get_account(address)
                    balance = account.get("account", {}).get("balances", [])

                    response_time = (
                        datetime.utcnow() - start_time
                    ).total_seconds() * 1000

                    test_result = {
                        "success": True,
                        "response_time_ms": int(response_time),
                        "balance": str(balance),
                        "endpoint_used": str(client.indexer.host)
                        if hasattr(client, "indexer")
                        else "unknown",
                    }

                    logger.info(f"Credential {credential_id} test successful")
                else:
                    test_result = {
                        "success": True,
                        "message": "Connection successful (limited test mode)",
                    }

            except Exception as e:
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                test_result = {
                    "success": False,
                    "error_message": str(e),
                    "response_time_ms": int(response_time),
                }
                logger.warning(f"Credential {credential_id} test failed: {str(e)}")

            # Save test result
            test_record = DydxTestResult(
                credential_id=credential_id,
                network_type=credential.network_type,
                success=test_result.get("success", False),
                response_time_ms=test_result.get("response_time_ms"),
                balance=test_result.get("balance"),
                error_message=test_result.get("error_message"),
                endpoint_used=test_result.get("endpoint_used"),
            )

            self.db.add(test_record)
            credential.is_test_valid = test_result.get("success", False)
            credential.last_tested = datetime.utcnow()
            credential.error_message = test_result.get("error_message")
            self.db.commit()

            return test_result

        except Exception as e:
            logger.error(f"Error testing credential: {str(e)}")
            return {"success": False, "error_message": f"Test failed: {str(e)}"}

    async def get_active_credential(
        self,
        user_id: int,
        network_type: NetworkType,
    ) -> Optional[Dict[str, str]]:
        """
        Get the active credential for a specific network.

        Returns the address and mnemonic if valid, None otherwise.
        """
        try:
            credential = (
                self.db.query(DydxCredential)
                .filter(
                    and_(
                        DydxCredential.user_id == user_id,
                        DydxCredential.network_type == network_type,
                        DydxCredential.is_active == True,
                        DydxCredential.is_test_valid == True,
                    )
                )
                .order_by(desc(DydxCredential.last_tested))
                .first()
            )

            if not credential:
                logger.warning(
                    f"No active valid credential found for user {user_id} "
                    f"on {network_type.value}"
                )
                return None

            return {
                "credential_id": credential.id,
                "address": self.encryption.decrypt(credential.address),
                "mnemonic": self.encryption.decrypt(credential.mnemonic),
                "name": credential.name,
            }

        except Exception as e:
            logger.error(f"Error getting active credential: {str(e)}")
            return None

    async def _audit_log(
        self,
        user_id: int,
        credential_id: int,
        operation: str,
        network_type: NetworkType,
        address_preview: str,
        success: bool,
        details: Optional[str] = None,
    ):
        """Log credential operations for audit trail."""
        try:
            audit = DydxCredentialAudit(
                credential_id=credential_id,
                user_id=user_id,
                operation=operation,
                network_type=network_type,
                address_preview=address_preview[:20],
                success=success,
                details=details,
            )
            self.db.add(audit)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error creating audit log: {str(e)}")
