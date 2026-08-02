"""
Password 2FA router
"""

from datetime import timedelta
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.auth_utils import TwoFactorUtils
from src.infrastructure.database import db
from src.infrastructure.domain.models.auth_models import User, UserToken
from src.middleware.auth_middleware import get_current_active_user
from src.shared.time_utils import utc_now

router = APIRouter()


class Verify2FARequest(BaseModel):
    """Payload for verifying a TOTP token."""

    token: str


def _user_id_value(user: User) -> int:
    return int(user.id)


def _username_value(user: User) -> str:
    return str(cast(object, user.username))


def _token_value(record: UserToken) -> str:
    return str(cast(object, record.token))


def _get_totp_secret_record(session: Session, user_id: int):
    return (
        session.query(UserToken)
        .filter(
            UserToken.user_id == user_id,
            UserToken.token_type == "totp_secret",
            UserToken.is_revoked.is_(False),
        )
        .order_by(UserToken.created_at.desc())
        .first()
    )


def _get_enabled_record(session: Session, user_id: int):
    return (
        session.query(UserToken)
        .filter(
            UserToken.user_id == user_id,
            UserToken.token_type == "totp_enabled",
            UserToken.is_revoked.is_(False),
        )
        .order_by(UserToken.created_at.desc())
        .first()
    )


@router.post("/setup")
async def setup_2fa(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(db.get_session),
):
    """Setup TOTP 2FA and return QR provisioning metadata."""
    user_id = _user_id_value(current_user)
    username = _username_value(current_user)

    secret_record = _get_totp_secret_record(session, user_id)
    if secret_record:
        secret = _token_value(secret_record)
    else:
        secret = TwoFactorUtils.generate_totp_secret()
        expires_at = utc_now() + timedelta(days=3650)
        secret_record = UserToken(
            user_id=user_id,
            token=secret,
            token_type="totp_secret",
            expires_at=expires_at,
            is_revoked=False,
        )
        session.add(secret_record)
        session.commit()

    qr_code = TwoFactorUtils.generate_qr_code(secret, username)
    otpauth_uri = TwoFactorUtils.generate_totp_uri(secret, username)
    is_enabled = _get_enabled_record(session, user_id) is not None

    return {
        "message": "2FA setup ready",
        "secret": secret,
        "otpauth_uri": otpauth_uri,
        "qr_code": qr_code,
        "is_enabled": is_enabled,
    }


@router.post("/verify")
async def verify_2fa(
    payload: Verify2FARequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(db.get_session),
):
    """Verify TOTP token and mark 2FA as enabled for user."""
    user_id = _user_id_value(current_user)

    secret_record = _get_totp_secret_record(session, user_id)
    if not secret_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA has not been set up for this user",
        )

    token = payload.token.strip().replace(" ", "")
    if not token.isdigit() or len(token) not in {6, 8}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP token format",
        )

    is_valid = TwoFactorUtils.verify_totp_token(_token_value(secret_record), token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA token",
        )

    enabled_record = _get_enabled_record(session, user_id)
    if not enabled_record:
        expires_at = utc_now() + timedelta(days=3650)
        enabled_record = UserToken(
            user_id=user_id,
            token=f"enabled:{user_id}",
            token_type="totp_enabled",
            expires_at=expires_at,
            is_revoked=False,
        )
        session.add(enabled_record)
    else:
        setattr(enabled_record, "is_revoked", False)

    session.commit()

    return {
        "message": "2FA verification successful",
        "is_enabled": True,
    }
