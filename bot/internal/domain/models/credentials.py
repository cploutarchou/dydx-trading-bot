"""
DydxCredentials Model for Secure Credential Storage

This module provides SQLAlchemy models for securely storing dYdX wallet credentials
in the database with encryption, audit trails, and validation capabilities.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class NetworkType(str, enum.Enum):
    """Network type enumeration"""

    TESTNET = "testnet"
    MAINNET = "mainnet"


class DydxCredential(Base):
    """
    Secure storage for dYdX wallet credentials with encryption and audit trail.

    Attributes:
        id: Primary key
        user_id: Foreign key to user (for multi-user support)
        network_type: testnet or mainnet
        address: dYdX wallet address (encrypted)
        mnemonic: BIP39 mnemonic phrase (encrypted)
        is_active: Whether this credential is currently active
        is_test_valid: Result of last test connection to dYdX
        last_tested: Timestamp of last validation test
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
        created_by: User ID who created this credential
        updated_by: User ID who last updated this credential
        name: Friendly name for this credential set
        description: Optional description
        error_message: Last error if validation failed
    """

    __tablename__ = "dydx_credentials"
    __table_args__ = (
        Index("idx_user_network", "user_id", "network_type"),
        Index("idx_network_active", "network_type", "is_active"),
        Index("idx_user_active", "user_id", "is_active"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)  # Will be foreign key to auth system

    # Network and credentials
    network_type = Column(
        Enum(NetworkType), nullable=False, default=NetworkType.TESTNET
    )
    address = Column(String(128), nullable=False)  # Encrypted
    mnemonic = Column(Text, nullable=False)  # Encrypted

    # Status and validation
    is_active = Column(Boolean, default=True, nullable=False)
    is_test_valid = Column(Boolean, nullable=True)  # None = not tested yet
    last_tested = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)  # Last error if test failed

    # Metadata
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # Audit trail
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by = Column(Integer, nullable=False)  # User ID
    updated_by = Column(Integer, nullable=True)  # User ID

    def __repr__(self):
        return (
            f"<DydxCredential(id={self.id}, user_id={self.user_id}, "
            f"network={self.network_type.value}, "
            f"address={self.address[:10]}..., active={self.is_active}, "
            f"valid={self.is_test_valid})>"
        )


class DydxCredentialAudit(Base):
    """
    Audit log for all dYdX credential operations.

    Tracks all CRUD operations on credentials for security and compliance.
    """

    __tablename__ = "dydx_credential_audit"
    __table_args__ = (
        Index("idx_credential_id", "credential_id"),
        Index("idx_user_id", "user_id"),
        Index("idx_operation", "operation"),
        Index("idx_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    credential_id = Column(Integer, nullable=False)  # Foreign key to DydxCredential
    user_id = Column(Integer, nullable=False)  # User who performed the action

    # Operation details
    operation = Column(String(50), nullable=False)  # create, read, update, delete, test
    network_type = Column(Enum(NetworkType), nullable=False)
    address_preview = Column(
        String(20), nullable=False
    )  # First 20 chars of address for audit

    # Outcome
    success = Column(Boolean, nullable=False)
    details = Column(Text, nullable=True)  # Error message or additional info

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<DydxCredentialAudit(id={self.id}, credential_id={self.credential_id}, "
            f"operation={self.operation}, success={self.success})>"
        )


class DydxTestResult(Base):
    """
    Record of dYdX credential validation test results.

    Stores detailed results of credential validation tests for monitoring and debugging.
    """

    __tablename__ = "dydx_test_results"
    __table_args__ = (
        Index("idx_credential_id", "credential_id"),
        Index("idx_tested_at", "tested_at"),
    )

    id = Column(Integer, primary_key=True)
    credential_id = Column(Integer, nullable=False)  # Foreign key to DydxCredential

    # Test details
    tested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    network_type = Column(Enum(NetworkType), nullable=False)

    # Results
    success = Column(Boolean, nullable=False)
    response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    balance = Column(String(50), nullable=True)  # Account balance if successful
    error_message = Column(Text, nullable=True)

    # Connection details
    endpoint_used = Column(String(255), nullable=True)
    test_type = Column(String(50), default="balance_check")  # Type of test performed

    def __repr__(self):
        return (
            f"<DydxTestResult(id={self.id}, credential_id={self.credential_id}, "
            f"success={self.success}, response_time_ms={self.response_time_ms})>"
        )
