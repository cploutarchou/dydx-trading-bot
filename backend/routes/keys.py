"""
API routes for managing dYdX keys securely.

Endpoints for creating, retrieving, and managing dYdX credentials.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.services.key_management import DYDXKeyService

router = APIRouter(prefix="/api/v1/keys", tags=["keys"])


# ============================================================================
# Request/Response Schemas
# ============================================================================


class CreateKeyRequest(BaseModel):
    """Request to create or update a dYdX key."""

    network: str = Field(..., description="testnet or mainnet")
    chain_address: str = Field(..., description="dYdX chain address")
    secret_phrase: str = Field(..., description="dYdX mnemonic seed phrase")


class KeyResponse(BaseModel):
    """Response with key information (without secret)."""

    id: int
    network: str
    chain_address: str
    is_active: bool
    created_at: str
    updated_at: str


class KeyListResponse(BaseModel):
    """Response with list of user's keys."""

    keys: list[KeyResponse]
    total: int


class KeySecret(BaseModel):
    """Full key with decrypted secret (only for authenticated users)."""

    id: int
    network: str
    chain_address: str
    secret_phrase: str


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/create", response_model=KeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    request: CreateKeyRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create or update a dYdX key for the current user.

    **Request body:**
    - network: "testnet" or "mainnet"
    - chain_address: Your dYdX chain address
    - secret_phrase: Your mnemonic seed phrase

    **Response:** Created key information (without secret)
    """
    try:
        key = DYDXKeyService.create_key(
            db=db,
            user_id=current_user.id,
            network=request.network.lower(),
            chain_address=request.chain_address,
            secret_phrase=request.secret_phrase,
        )

        return KeyResponse(
            id=key.id,
            network=key.network,
            chain_address=key.chain_address,
            is_active=key.is_active,
            created_at=key.created_at.isoformat(),
            updated_at=key.updated_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create key: {str(e)}",
        )


@router.get("/list", response_model=KeyListResponse)
async def list_keys(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all active keys for the current user (without secrets).

    **Response:** List of keys with metadata
    """
    try:
        keys_data = DYDXKeyService.get_active_keys(db, current_user.id)

        keys_response = [
            KeyResponse(
                id=key["id"],
                network=key["network"],
                chain_address=key["chain_address"],
                is_active=True,
                created_at=key["created_at"],
                updated_at=key.get("updated_at", key["created_at"]),
            )
            for key in keys_data
        ]

        return KeyListResponse(keys=keys_response, total=len(keys_response))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list keys: {str(e)}",
        )


@router.get("/{network}", response_model=KeyResponse)
async def get_key_info(
    network: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get key information for a specific network (without secret).

    **Parameters:**
    - network: "testnet" or "mainnet"

    **Response:** Key information
    """
    try:
        key_info = DYDXKeyService.get_key_info(db, current_user.id, network.lower())

        if not key_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No key found for network: {network}",
            )

        return KeyResponse(**key_info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve key: {str(e)}",
        )


@router.delete("/{network}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    network: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete (deactivate) a key for the current user.

    **Parameters:**
    - network: "testnet" or "mainnet"
    """
    try:
        success = DYDXKeyService.delete_key(db, current_user.id, network.lower())

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No key found for network: {network}",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete key: {str(e)}",
        )


@router.get(
    "/{network}/secret",
    response_model=KeySecret,
    dependencies=[Depends(get_current_user)],
)
async def get_key_with_secret(
    network: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get full key with decrypted secret (only for authenticated users).

    ⚠️  SENSITIVE ENDPOINT - Returns decrypted secret phrase

    **Parameters:**
    - network: "testnet" or "mainnet"

    **Response:** Full key including secret phrase
    """
    try:
        key_data = DYDXKeyService.get_key(db, current_user.id, network.lower())

        if not key_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No key found for network: {network}",
            )

        return KeySecret(**key_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve key: {str(e)}",
        )
