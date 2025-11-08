"""
Authentication API routes for dYdX Trading Bot
Provides login, logout, refresh, register, and user management endpoints
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from auth_middleware import (
    check_rate_limit,
    get_admin_user,
    get_current_active_user,
    get_current_user,
    rate_limiter,
    record_login_attempt,
    revoke_all_user_tokens,
    revoke_token,
    validate_refresh_token,
)
from auth_models import JWTToken, User
from auth_utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    JWTUtils,
    PasswordUtils,
    SecurityUtils,
    TwoFactorUtils,
)
from database import get_session

# Create router
router = APIRouter(prefix="/auth", tags=["Authentication"])


# Pydantic models for request/response
class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1)
    totp_token: Optional[str] = Field(None, min_length=6, max_length=6)


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    is_2fa_enabled: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    user_data: UserLogin,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
):
    """
    User login endpoint with optional 2FA support
    """
    # Rate limiting
    check_rate_limit(request, "login")

    # Get client information
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # Find user
    user = db.query(User).filter(User.username == user_data.username).first()

    if not user:
        # Record failed attempt
        background_tasks.add_task(
            record_login_attempt,
            db,
            user_data.username,
            client_ip,
            user_agent,
            success=False,
            failure_reason="user_not_found",
        )
        rate_limiter.record_attempt(SecurityUtils.rate_limit_key(client_ip, "login"))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Check password
    if not PasswordUtils.verify_password(
        user_data.password, getattr(user, "hashed_password")
    ):
        # Record failed attempt
        background_tasks.add_task(
            record_login_attempt,
            db,
            user_data.username,
            client_ip,
            user_agent,
            success=False,
            failure_reason="invalid_password",
        )
        rate_limiter.record_attempt(SecurityUtils.rate_limit_key(client_ip, "login"))

        # Increment failed login attempts
        db.query(User).filter(User.id == user.id).update(
            {"failed_login_attempts": getattr(user, "failed_login_attempts", 0) + 1}
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Check if user is active
    if not getattr(user, "is_active", True):
        background_tasks.add_task(
            record_login_attempt,
            db,
            user_data.username,
            client_ip,
            user_agent,
            success=False,
            failure_reason="user_inactive",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive"
        )

    # Check 2FA if enabled
    is_2fa_enabled = getattr(user, "is_2fa_enabled", False)
    if is_2fa_enabled:
        if not user_data.totp_token:
            background_tasks.add_task(
                record_login_attempt,
                db,
                user_data.username,
                client_ip,
                user_agent,
                success=False,
                failure_reason="2fa_required",
                two_fa_required=True,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="2FA token required"
            )

        totp_secret = getattr(user, "totp_secret", "")
        if not TwoFactorUtils.verify_totp_token(totp_secret, user_data.totp_token):
            background_tasks.add_task(
                record_login_attempt,
                db,
                user_data.username,
                client_ip,
                user_agent,
                success=False,
                failure_reason="invalid_2fa",
                two_fa_required=True,
                two_fa_success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA token"
            )

    # Login successful - create tokens
    user_id_str = str(getattr(user, "id"))
    token_data = {"sub": user_id_str, "username": user_data.username}

    access_token = JWTUtils.create_access_token(token_data)
    refresh_token = JWTUtils.create_refresh_token(token_data)

    # Store tokens in database
    access_jti = JWTUtils.get_token_jti(access_token)
    refresh_jti = JWTUtils.get_token_jti(refresh_token)

    if access_jti:
        access_token_record = JWTToken(
            user_id=getattr(user, "id"),
            token_id=access_jti,
            token_type="access",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow()
            + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            user_agent=user_agent,
            ip_address=client_ip,
        )
        db.add(access_token_record)

    if refresh_jti:
        refresh_token_record = JWTToken(
            user_id=getattr(user, "id"),
            token_id=refresh_jti,
            token_type="refresh",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=client_ip,
        )
        db.add(refresh_token_record)

    # Reset failed login attempts and update last login
    db.query(User).filter(User.id == user.id).update(
        {"failed_login_attempts": 0, "last_login": datetime.utcnow()}
    )

    db.commit()

    # Record successful attempt
    background_tasks.add_task(
        record_login_attempt,
        db,
        user_data.username,
        client_ip,
        user_agent,
        success=True,
        two_fa_required=is_2fa_enabled,
        two_fa_success=is_2fa_enabled,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_session),
):
    """
    Refresh access token using refresh token
    """
    check_rate_limit(request, "refresh")

    # Validate refresh token
    user = validate_refresh_token(refresh_data.refresh_token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    # Create new access token
    user_id_str = str(getattr(user, "id"))
    username = getattr(user, "username")
    token_data = {"sub": user_id_str, "username": username}

    new_access_token = JWTUtils.create_access_token(token_data)

    # Store new access token in database
    access_jti = JWTUtils.get_token_jti(new_access_token)
    if access_jti:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

        access_token_record = JWTToken(
            user_id=getattr(user, "id"),
            token_id=access_jti,
            token_type="access",
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow()
            + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            user_agent=user_agent,
            ip_address=client_ip,
        )
        db.add(access_token_record)
        db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_data.refresh_token,  # Keep same refresh token
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Logout current user (revoke current access token)
    """
    # Get current token from request
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        revoke_token(token, db)

    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all_sessions(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_session)
):
    """
    Logout from all sessions (revoke all user tokens)
    """
    user_id_str = str(getattr(current_user, "id"))
    revoked_count = revoke_all_user_tokens(user_id_str, db)

    return {"message": f"Successfully logged out from {revoked_count} sessions"}


@router.post("/register", response_model=UserResponse)
async def register(
    request: Request, user_data: UserRegister, db: Session = Depends(get_session)
):
    """
    Register new user (admin only for now)
    """
    check_rate_limit(request, "register")

    # Check if username exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Validate password strength
    password_check = SecurityUtils.validate_password_strength(user_data.password)
    if not password_check["is_valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password requirements not met: {', '.join(password_check['errors'])}",
        )

    # Create user
    hashed_password = PasswordUtils.hash_password(user_data.password)

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        is_active=True,
        is_superuser=False,
        is_2fa_enabled=False,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current user information
    """
    return current_user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
):
    """
    List all users (admin only)
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_session),
):
    """
    Get user by ID (admin only)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


# Email test endpoint (admin only)
@router.post("/test-email")
async def test_email_service(
    email: str,
    current_user: User = Depends(get_admin_user),
):
    """
    Test email service configuration (admin only)
    """
    try:
        from email_service import email_service

        success = await email_service.send_test_email(email)

        if success:
            return {
                "success": True,
                "message": f"Test email sent successfully to {email}",
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            return {
                "success": False,
                "message": "Failed to send test email. Check email configuration.",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Email service error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
        }


# Health check endpoint (no authentication required)
@router.get("/health")
async def auth_health_check():
    """
    Authentication service health check
    """
    return {
        "service": "authentication",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
