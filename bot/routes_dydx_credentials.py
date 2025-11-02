"""
dYdX Credentials API Routes

Secure API endpoints for managing dYdX wallet credentials.
All endpoints require JWT authentication.

Endpoints:
- POST /api/v1/dydx/credentials - Create new credential
- GET /api/v1/dydx/credentials - List user's credentials
- GET /api/v1/dydx/credentials/{id} - Get specific credential
- PUT /api/v1/dydx/credentials/{id} - Update credential
- DELETE /api/v1/dydx/credentials/{id} - Delete credential
- POST /api/v1/dydx/credentials/{id}/test - Test credential validity
- GET /api/v1/dydx/credentials/{id}/status - Get credential status
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

# These would be imported from your actual auth and service modules
# from auth_middleware import get_current_active_user
# from auth_models import User
# from service_dydx_credentials import DydxCredentialsService, CredentialEncryption
# from models_dydx_credentials import NetworkType
# from database import get_db

router = APIRouter(prefix="/api/v1/dydx/credentials", tags=["dYdX Credentials"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class DydxCredentialCreate(BaseModel):
    """Request model for creating a new credential"""

    network_type: str = Field(..., description="testnet or mainnet")
    address: str = Field(..., min_length=20, description="dYdX wallet address")
    mnemonic: str = Field(..., description="BIP39 mnemonic phrase (12+ words)")
    name: Optional[str] = Field(None, description="Friendly name for this credential")
    description: Optional[str] = Field(None, description="Optional description")
    test_before_save: bool = Field(
        True, description="Test credential validity before saving to database"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "network_type": "testnet",
                "address": "dydx1abc123def456...",
                "mnemonic": "word1 word2 word3 ... word12",
                "name": "My Trading Wallet",
                "description": "Primary testnet wallet for trading",
                "test_before_save": True,
            }
        }
    }


class DydxCredentialUpdate(BaseModel):
    """Request model for updating a credential"""

    address: Optional[str] = Field(None, description="New wallet address")
    mnemonic: Optional[str] = Field(None, description="New mnemonic phrase")
    name: Optional[str] = Field(None, description="New friendly name")
    description: Optional[str] = Field(None, description="New description")
    is_active: Optional[bool] = Field(None, description="Activate or deactivate")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Updated Wallet Name",
                "description": "Updated description",
            }
        }
    }


class DydxCredentialResponse(BaseModel):
    """Response model for credential details"""

    id: int
    network_type: str
    name: str
    address_preview: str  # Only show first 10 and last 4 characters
    is_active: bool
    is_test_valid: Optional[bool]
    last_tested: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "network_type": "testnet",
                "name": "My Trading Wallet",
                "address_preview": "dydx1abc...def4",
                "is_active": True,
                "is_test_valid": True,
                "last_tested": "2025-11-02T10:30:00Z",
                "created_at": "2025-11-02T09:00:00Z",
                "updated_at": "2025-11-02T10:30:00Z",
            }
        },
    }


class DydxCredentialDetailResponse(DydxCredentialResponse):
    """Response model with encrypted credential data (only for owner)"""

    address: Optional[str] = Field(None, description="Full address (only if requested)")
    mnemonic: Optional[str] = Field(
        None, description="Full mnemonic (only if requested)"
    )
    description: Optional[str] = Field(None)


class DydxTestResultResponse(BaseModel):
    """Response model for credential test results"""

    success: bool
    response_time_ms: Optional[int] = None
    balance: Optional[str] = None
    error_message: Optional[str] = None
    endpoint_used: Optional[str] = None
    tested_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "response_time_ms": 145,
                "balance": "[{'denom': 'uusdc', 'amount': '1000000'}]",
                "endpoint_used": "https://indexer.v4testnet.dydx.exchange",
                "tested_at": "2025-11-02T10:30:00Z",
            }
        }
    }


class DydxCredentialStatusResponse(BaseModel):
    """Response model for credential status"""

    id: int
    is_active: bool
    is_test_valid: Optional[bool]
    last_tested: Optional[datetime]
    error_message: Optional[str] = None
    can_be_used: bool  # is_active AND is_test_valid

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "is_active": True,
                "is_test_valid": True,
                "last_tested": "2025-11-02T10:30:00Z",
                "error_message": None,
                "can_be_used": True,
            }
        }
    }


# ============================================================================
# PLACEHOLDER ENDPOINTS
# ============================================================================

"""
NOTE: These are placeholder implementations. When integrated with the actual
FastAPI server, they should be uncommented and properly implemented with:

@router.post("", response_model=DydxCredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    request: DydxCredentialCreate,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db),
):
    '''Create a new dYdX credential.'''
    try:
        encryption = CredentialEncryption(encryption_key=None)  # Use from config
        service = DydxCredentialsService(db, encryption)
        
        result = await service.create_credential(
            user_id=current_user.id,
            network_type=NetworkType(request.network_type.lower()),
            address=request.address,
            mnemonic=request.mnemonic,
            name=request.name,
            description=request.description,
            test_before_save=request.test_before_save,
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating credential: {str(e)}"
        )


@router.get("", response_model=List[DydxCredentialResponse])
async def list_credentials(
    network_type: Optional[str] = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db),
):
    '''List all credentials for current user.'''
    try:
        encryption = CredentialEncryption(encryption_key=None)
        service = DydxCredentialsService(db, encryption)
        
        creds = await service.list_credentials(
            user_id=current_user.id,
            network_type=NetworkType(network_type.lower()) if network_type else None,
            active_only=active_only,
        )
        
        return creds
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing credentials: {str(e)}"
        )


@router.get("/{credential_id}", response_model=DydxCredentialDetailResponse)
async def get_credential(
    credential_id: int,
    decrypt: bool = False,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db),
):
    '''Get specific credential details.'''
    try:
        encryption = CredentialEncryption(encryption_key=None)
        service = DydxCredentialsService(db, encryption)
        
        credential = await service.get_credential(
            credential_id=credential_id,
            user_id=current_user.id,
            decrypt=decrypt,
        )
        
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )
        
        return credential
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this credential"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving credential: {str(e)}"
        )


@router.put("/{credential_id}", response_model=DydxCredentialResponse)
async def update_credential(
    credential_id: int,
    request: DydxCredentialUpdate,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db),
):
    '''Update an existing credential.'''
    try:
        encryption = CredentialEncryption(encryption_key=None)
        service = DydxCredentialsService(db, encryption)
        
        result = await service.update_credential(
            credential_id=credential_id,
            user_id=current_user.id,
            address=request.address,
            mnemonic=request.mnemonic,
            name=request.name,
            description=request.description,
            is_active=request.is_active,
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this credential"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating credential: {str(e)}"
        )


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: int,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db),
):
    '''Delete a credential (soft delete).'''
    try:
        encryption = CredentialEncryption(encryption_key=None)
        service = DydxCredentialsService(db, encryption)
        
        await service.delete_credential(
            credential_id=credential_id,
            user_id=current_user.id,
        )
        
        return None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this credential"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting credential: {str(e)}"
        )


@router.post("/{credential_id}/test", response_model=DydxTestResultResponse)
async def test_credential(
    credential_id: int,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db),
):
    '''Test a credential's validity with dYdX network.'''
    try:
        encryption = CredentialEncryption(encryption_key=None)
        service = DydxCredentialsService(db, encryption)
        
        result = await service.test_credential(credential_id=credential_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Credential test failed: {result.get('error_message')}"
            )
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing credential: {str(e)}"
        )


@router.get("/{credential_id}/status", response_model=DydxCredentialStatusResponse)
async def get_credential_status(
    credential_id: int,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db),
):
    '''Get credential status and whether it can be used for trading.'''
    try:
        encryption = CredentialEncryption(encryption_key=None)
        service = DydxCredentialsService(db, encryption)
        
        credential = await service.get_credential(
            credential_id=credential_id,
            user_id=current_user.id,
            decrypt=False,
        )
        
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )
        
        return {
            "id": credential.get("id"),
            "is_active": credential.get("is_active"),
            "is_test_valid": credential.get("is_test_valid"),
            "last_tested": credential.get("last_tested"),
            "error_message": credential.get("error_message"),
            "can_be_used": credential.get("is_active") and credential.get("is_test_valid"),
        }
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this credential"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting credential status: {str(e)}"
        )
"""
