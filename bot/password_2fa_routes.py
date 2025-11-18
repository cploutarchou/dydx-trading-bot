"""
Password management and 2FA authentication routes
Provides change password, forgot password, and 2FA management endpoints
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from midleware.auth_middleware import (
    check_rate_limit,
    get_current_active_user,
    rate_limiter,
    revoke_all_user_tokens,
)
from internal.domain.models.auth_models import EmailVerification, PasswordResetToken, User
from auth_utils import (
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS,
    EmailVerificationUtils,
    PasswordUtils,
    SecurityUtils,
    TwoFactorUtils,
)
from database import get_session
from internal.service.email_service import send_email_verification, send_password_reset_email

# Create router
router = APIRouter(prefix="/auth", tags=["Password & 2FA"])


# Pydantic models
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    totp_token: Optional[str] = Field(None, min_length=6, max_length=6)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    totp_token: Optional[str] = Field(None, min_length=6, max_length=6)


class Enable2FAResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: List[str]


class Verify2FARequest(BaseModel):
    totp_token: str = Field(..., min_length=6, max_length=6)
    password: str = Field(..., min_length=1)


class Disable2FARequest(BaseModel):
    password: str = Field(..., min_length=1)
    totp_token: Optional[str] = Field(None, min_length=6, max_length=6)


class EmailVerificationRequest(BaseModel):
    password: str = Field(..., min_length=1)


class EmailVerificationConfirmRequest(BaseModel):
    verification_token: str = Field(..., min_length=1)
    verification_code: str = Field(..., min_length=6, max_length=6)
    totp_token: str = Field(..., min_length=6, max_length=6)


class EmailVerificationResponse(BaseModel):
    message: str
    expires_in_minutes: int = 15


@router.post("/change-password")
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    """
    Change user password with optional 2FA verification
    """
    check_rate_limit(request, "change_password")

    # Verify current password
    current_hashed = getattr(current_user, "hashed_password")
    if not PasswordUtils.verify_password(
        password_data.current_password, current_hashed
    ):
        rate_limiter.record_attempt(
            SecurityUtils.rate_limit_key(
                request.client.host if request.client else "unknown", "change_password"
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Check 2FA if enabled
    is_2fa_enabled = getattr(current_user, "is_2fa_enabled", False)
    if is_2fa_enabled:
        if not password_data.totp_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="2FA token required for password change",
            )

        totp_secret = getattr(current_user, "totp_secret", "")
        if not TwoFactorUtils.verify_totp_token(totp_secret, password_data.totp_token):
            rate_limiter.record_attempt(
                SecurityUtils.rate_limit_key(
                    request.client.host if request.client else "unknown",
                    "change_password",
                )
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA token"
            )

    # Validate new password strength
    password_check = SecurityUtils.validate_password_strength(
        password_data.new_password
    )
    if not password_check["is_valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password requirements not met: {', '.join(password_check['errors'])}",
        )

    # Update password
    new_hashed_password = PasswordUtils.hash_password(password_data.new_password)

    db.query(User).filter(User.id == getattr(current_user, "id")).update(
        {
            "hashed_password": new_hashed_password,
            "password_changed_at": datetime.utcnow(),
            "failed_login_attempts": 0,
        }
    )
    db.commit()

    # Revoke all existing sessions for security
    user_id_str = str(getattr(current_user, "id"))
    background_tasks.add_task(revoke_all_user_tokens, user_id_str, db)

    return {"message": "Password changed successfully. Please log in again."}


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    forgot_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
):
    """
    Initiate password reset process
    """
    check_rate_limit(request, "forgot_password")

    # Find user by email
    user = db.query(User).filter(User.email == forgot_data.email).first()

    # Always return success to prevent email enumeration
    success_message = {
        "message": "If the email exists, a password reset link has been sent."
    }

    if not user:
        # Add delay to prevent timing attacks
        import asyncio

        await asyncio.sleep(0.5)
        return success_message

    # Check if user is active
    if not getattr(user, "is_active", True):
        return success_message

    # Generate reset token
    reset_token = SecurityUtils.generate_password_reset_token(str(getattr(user, "id")))
    expires_at = datetime.utcnow() + timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS)

    # Store reset token in database
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    password_reset = PasswordResetToken(
        user_id=getattr(user, "id"),
        token=reset_token,
        expires_at=expires_at,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    db.add(password_reset)
    db.commit()

    # Send password reset email
    username = getattr(user, "username")
    background_tasks.add_task(
        send_password_reset_email,
        to_email=forgot_data.email,
        username=username,
        reset_token=reset_token,
        ip_address=client_ip,
        expires_in_hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS,
    )

    return success_message


@router.post("/reset-password")
async def reset_password(
    request: Request,
    reset_data: ResetPasswordRequest,
    db: Session = Depends(get_session),
):
    """
    Reset password using reset token
    """
    check_rate_limit(request, "reset_password")

    # Find valid reset token
    reset_token_record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == reset_data.token,
            PasswordResetToken.is_used.is_(False),
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not reset_token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Get user
    user = (
        db.query(User).filter(User.id == getattr(reset_token_record, "user_id")).first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token"
        )

    # Check 2FA if enabled
    is_2fa_enabled = getattr(user, "is_2fa_enabled", False)
    if is_2fa_enabled:
        if not reset_data.totp_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="2FA token required for password reset",
            )

        totp_secret = getattr(user, "totp_secret", "")
        if not TwoFactorUtils.verify_totp_token(totp_secret, reset_data.totp_token):
            rate_limiter.record_attempt(
                SecurityUtils.rate_limit_key(
                    request.client.host if request.client else "unknown",
                    "reset_password",
                )
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA token"
            )

    # Validate new password strength
    password_check = SecurityUtils.validate_password_strength(reset_data.new_password)
    if not password_check["is_valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password requirements not met: {', '.join(password_check['errors'])}",
        )

    # Update password
    new_hashed_password = PasswordUtils.hash_password(reset_data.new_password)

    db.query(User).filter(User.id == getattr(user, "id")).update(
        {
            "hashed_password": new_hashed_password,
            "password_changed_at": datetime.utcnow(),
            "failed_login_attempts": 0,
            "locked_until": None,  # Clear any account lock
        }
    )

    # Mark reset token as used
    db.query(PasswordResetToken).filter(
        PasswordResetToken.id == getattr(reset_token_record, "id")
    ).update({"is_used": True, "used_at": datetime.utcnow()})

    db.commit()

    # Revoke all existing sessions for security
    user_id_str = str(getattr(user, "id"))
    revoke_all_user_tokens(user_id_str, db)

    return {
        "message": "Password reset successfully. Please log in with your new password."
    }


@router.post(
    "/2fa/request-email-verification", response_model=EmailVerificationResponse
)
async def request_email_verification_for_2fa(
    request: Request,
    verification_request: EmailVerificationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    """
    Request email verification for 2FA setup
    """
    check_rate_limit(request, "email_verification")

    # Verify user password
    current_hashed = getattr(current_user, "hashed_password")
    if not PasswordUtils.verify_password(verification_request.password, current_hashed):
        rate_limiter.record_attempt(
            SecurityUtils.rate_limit_key(
                request.client.host if request.client else "unknown",
                "email_verification",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect"
        )

    # Check if 2FA is already enabled
    if getattr(current_user, "is_2fa_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is already enabled"
        )

    # Generate verification tokens
    verification_tokens = EmailVerificationUtils.create_verification_tokens()
    verification_code = verification_tokens["verification_code"]
    verification_token = verification_tokens["verification_token"]

    # Get client information
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # Create email verification record
    email_verification = EmailVerification(
        user_id=getattr(current_user, "id"),
        verification_token=verification_token,
        verification_code=verification_code,
        is_verified=False,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        purpose="2fa_setup",
        ip_address=client_ip,
        user_agent=user_agent,
    )

    db.add(email_verification)
    db.commit()

    # Send verification email
    username = getattr(current_user, "username")
    email = getattr(current_user, "email")

    background_tasks.add_task(
        send_email_verification,
        to_email=email,
        username=username,
        verification_code=verification_code,
        verification_token=verification_token,
        expires_in_minutes=15,
    )

    return EmailVerificationResponse(
        message="Verification email sent. Please check your email and enter the verification code.",
        expires_in_minutes=15,
    )


@router.post("/2fa/verify-email-and-setup", response_model=Enable2FAResponse)
async def verify_email_and_setup_2fa(
    request: Request,
    verify_request: EmailVerificationConfirmRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    """
    Verify email and complete 2FA setup
    """
    check_rate_limit(request, "verify_email_2fa")

    # Find verification record
    verification_record = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.verification_token == verify_request.verification_token,
            EmailVerification.user_id == getattr(current_user, "id"),
            EmailVerification.purpose == "2fa_setup",
            EmailVerification.is_verified.is_(False),
            EmailVerification.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not verification_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # Verify the 6-digit code
    if (
        getattr(verification_record, "verification_code")
        != verify_request.verification_code
    ):
        rate_limiter.record_attempt(
            SecurityUtils.rate_limit_key(
                request.client.host if request.client else "unknown", "verify_email_2fa"
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code"
        )

    # Mark email verification as completed
    db.query(EmailVerification).filter(
        EmailVerification.id == getattr(verification_record, "id")
    ).update({"is_verified": True, "verified_at": datetime.utcnow()})

    # Generate TOTP secret and QR code
    secret = TwoFactorUtils.generate_totp_secret()
    username = getattr(current_user, "username")
    qr_code = TwoFactorUtils.generate_qr_code(secret, username)

    # Generate backup codes
    backup_codes = PasswordUtils.generate_backup_codes()
    backup_codes_json = json.dumps(backup_codes)

    # Verify TOTP token to ensure user can generate codes
    if not TwoFactorUtils.verify_totp_token(secret, verify_request.totp_token):
        # Allow setup but require proper verification later
        pass

    # Store 2FA configuration (not yet enabled)
    db.query(User).filter(User.id == getattr(current_user, "id")).update(
        {
            "totp_secret": secret,
            "backup_codes": backup_codes_json,
            "is_2fa_enabled": False,  # Will be enabled after TOTP verification
        }
    )

    db.commit()

    return Enable2FAResponse(secret=secret, qr_code=qr_code, backup_codes=backup_codes)


@router.post("/2fa/setup", response_model=Enable2FAResponse)
async def setup_2fa(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    """
    Setup 2FA for user account
    """
    # Check if 2FA is already enabled
    if getattr(current_user, "is_2fa_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is already enabled"
        )

    # Generate TOTP secret
    secret = TwoFactorUtils.generate_totp_secret()
    username = getattr(current_user, "username")

    # Generate QR code
    qr_code = TwoFactorUtils.generate_qr_code(secret, username)

    # Generate backup codes
    backup_codes = PasswordUtils.generate_backup_codes()
    backup_codes_json = json.dumps(backup_codes)

    # Store secret and backup codes (not yet enabled)
    db.query(User).filter(User.id == getattr(current_user, "id")).update(
        {
            "totp_secret": secret,
            "backup_codes": backup_codes_json,
            "is_2fa_enabled": False,  # Will be enabled after verification
        }
    )
    db.commit()

    return Enable2FAResponse(secret=secret, qr_code=qr_code, backup_codes=backup_codes)


@router.post("/2fa/enable")
async def enable_2fa(
    request: Request,
    verify_data: Verify2FARequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    """
    Enable 2FA after verifying TOTP token
    """
    check_rate_limit(request, "enable_2fa")

    # Verify password
    current_hashed = getattr(current_user, "hashed_password")
    if not PasswordUtils.verify_password(verify_data.password, current_hashed):
        rate_limiter.record_attempt(
            SecurityUtils.rate_limit_key(
                request.client.host if request.client else "unknown", "enable_2fa"
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect"
        )

    # Get TOTP secret
    totp_secret = getattr(current_user, "totp_secret", "")
    if not totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup not initiated. Please call /2fa/setup first.",
        )

    # Verify TOTP token
    if not TwoFactorUtils.verify_totp_token(totp_secret, verify_data.totp_token):
        rate_limiter.record_attempt(
            SecurityUtils.rate_limit_key(
                request.client.host if request.client else "unknown", "enable_2fa"
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA token"
        )

    # Enable 2FA
    db.query(User).filter(User.id == getattr(current_user, "id")).update(
        {"is_2fa_enabled": True}
    )
    db.commit()

    return {"message": "2FA enabled successfully"}


@router.post("/2fa/disable")
async def disable_2fa(
    request: Request,
    disable_data: Disable2FARequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
):
    """
    Disable 2FA for user account
    """
    check_rate_limit(request, "disable_2fa")

    # Check if 2FA is enabled
    if not getattr(current_user, "is_2fa_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is not enabled"
        )

    # Verify password
    current_hashed = getattr(current_user, "hashed_password")
    if not PasswordUtils.verify_password(disable_data.password, current_hashed):
        rate_limiter.record_attempt(
            SecurityUtils.rate_limit_key(
                request.client.host if request.client else "unknown", "disable_2fa"
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect"
        )

    # Verify 2FA token if provided
    if disable_data.totp_token:
        totp_secret = getattr(current_user, "totp_secret", "")
        if not TwoFactorUtils.verify_totp_token(totp_secret, disable_data.totp_token):
            rate_limiter.record_attempt(
                SecurityUtils.rate_limit_key(
                    request.client.host if request.client else "unknown", "disable_2fa"
                )
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA token"
            )

    # Disable 2FA and clear secrets
    db.query(User).filter(User.id == getattr(current_user, "id")).update(
        {"is_2fa_enabled": False, "totp_secret": None, "backup_codes": None}
    )
    db.commit()

    return {"message": "2FA disabled successfully"}


@router.get("/2fa/status")
async def get_2fa_status(current_user: User = Depends(get_current_active_user)):
    """
    Get 2FA status for current user
    """
    is_enabled = getattr(current_user, "is_2fa_enabled", False)
    has_secret = bool(getattr(current_user, "totp_secret", ""))

    return {
        "is_2fa_enabled": is_enabled,
        "setup_completed": has_secret,
        "backup_codes_available": bool(getattr(current_user, "backup_codes", "")),
    }
