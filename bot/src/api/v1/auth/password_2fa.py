"""
Password 2FA router
"""

from datetime import timedelta
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.auth_utils import TwoFactorUtils
from src.api.v1.auth.totp_state import (
    disable_two_factor,
    get_totp_enabled_record,
    get_totp_secret_record,
    issue_backup_codes,
    verify_login_second_factor,
)
from src.infrastructure.database import get_session
from src.infrastructure.domain.models.auth_models import User, UserToken
from src.middleware.auth_middleware import get_current_active_user
from src.shared.time_utils import utc_now

router = APIRouter()


class Verify2FARequest(BaseModel):
    """Payload for verifying a TOTP token (setup/regenerate — TOTP only)."""

    token: str = Field(
        ...,
        min_length=6,
        max_length=15,
        pattern=r"^[\d ]+$",
        description=(
            "6- or 8-digit TOTP code; optional internal spaces are stripped "
            "before verification."
        ),
    )


class SecondFactorRequest(BaseModel):
    """A second-factor token: either a TOTP code or a single-use backup code."""

    token: str = Field(
        ...,
        min_length=6,
        max_length=32,
        pattern=r"^[A-Za-z0-9 ]+$",
        description=(
            "A 6/8-digit TOTP code or a backup code (case-insensitive). "
            "Optional internal spaces are stripped before verification."
        ),
    )


def _user_id_value(user: User) -> int:
    return int(user.id)


def _username_value(user: User) -> str:
    return str(cast(object, user.username))


def _token_value(record: UserToken) -> str:
    return str(cast(object, record.token))


def _verify_current_totp(session: Session, user_id: int, raw_token: str) -> None:
    """Validate ``raw_token`` as a current TOTP for the user.

    Raises ``HTTPException(400)`` if 2FA is not set up or the token is malformed,
    ``HTTPException(401)`` if the token is wrong.
    """
    secret_record = get_totp_secret_record(session, user_id)
    if not secret_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA has not been set up for this user",
        )

    token = raw_token.strip().replace(" ", "")
    if not token.isdigit() or len(token) not in {6, 8}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP token format",
        )

    if not TwoFactorUtils.verify_totp_token(_token_value(secret_record), token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA token",
        )


@router.post("/setup")
async def setup_2fa(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Setup TOTP 2FA and return QR provisioning metadata."""
    user_id = _user_id_value(current_user)
    username = _username_value(current_user)

    secret_record = get_totp_secret_record(session, user_id)
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
    is_enabled = get_totp_enabled_record(session, user_id) is not None

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
    session: Session = Depends(get_session),
):
    """Verify TOTP token and mark 2FA as enabled for the user.

    On the enable transition (first successful verify), a set of single-use
    backup codes is issued and returned in plain form **exactly once**.
    """
    user_id = _user_id_value(current_user)
    _verify_current_totp(session, user_id, payload.token)

    if get_totp_enabled_record(session, user_id) is None:
        expires_at = utc_now() + timedelta(days=3650)
        existing_enabled = (
            session.query(UserToken)
            .filter(
                UserToken.user_id == user_id,
                UserToken.token_type == "totp_enabled",
            )
            .order_by(UserToken.created_at.desc())
            .first()
        )
        if existing_enabled is None:
            session.add(
                UserToken(
                    user_id=user_id,
                    token=f"enabled:{user_id}",
                    token_type="totp_enabled",
                    expires_at=expires_at,
                    is_revoked=False,
                )
            )
        else:
            # Re-enabling after a disable: un-revoke the existing row rather than
            # inserting a duplicate (``token`` is unique and deterministic).
            setattr(existing_enabled, "is_revoked", False)
        session.commit()
        backup_codes = issue_backup_codes(session, user_id)
        return {
            "message": "2FA verification successful",
            "is_enabled": True,
            "backup_codes": backup_codes,
        }

    return {"message": "2FA verification successful", "is_enabled": True}


@router.post("/backup-codes/regenerate")
async def regenerate_backup_codes(
    payload: Verify2FARequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Regenerate backup codes. Requires a valid TOTP code (device present).

    Invalidates all previously-issued backup codes and returns a new set in plain
    form **exactly once**.
    """
    user_id = _user_id_value(current_user)

    if get_totp_enabled_record(session, user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this user",
        )

    _verify_current_totp(session, user_id, payload.token)
    backup_codes = issue_backup_codes(session, user_id)
    return {"message": "Backup codes regenerated", "backup_codes": backup_codes}


@router.post("/disable")
async def disable_2fa(
    payload: SecondFactorRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Disable 2FA. Requires a valid TOTP code **or** an unused backup code.

    Never accepts password-only, so 2FA cannot be bypassed via password
    compromise. Revokes the enabled flag, the TOTP secret, and all backup codes;
    re-setup after disable creates fresh rows.
    """
    user_id = _user_id_value(current_user)

    if get_totp_enabled_record(session, user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this user",
        )

    if not verify_login_second_factor(session, user_id, payload.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA token",
        )

    disabled_count = disable_two_factor(session, user_id)
    return {
        "message": "2FA disabled",
        "is_enabled": False,
        "disabled_count": disabled_count,
    }
