"""
Password 2FA router
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/setup")
async def setup_2fa():
    """Setup 2FA"""
    # Placeholder implementation
    return {"message": "2FA setup not implemented"}


@router.post("/verify")
async def verify_2fa():
    """Verify 2FA"""
    # Placeholder implementation
    return {"message": "2FA verification not implemented"}
