"""Authentication router."""

from datetime import datetime, timezone
from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.api.auth_utils import JWTUtils, PasswordUtils, SecurityUtils, TokenBlacklist
from src.api.v1.auth.totp_state import (
    is_two_factor_enabled,
    verify_login_second_factor,
)
from src.infrastructure.database import get_session
from src.infrastructure.domain.models.auth_models import User
from src.middleware.auth_middleware import (
    get_current_active_user,
    is_auth_bypass_enabled,
)
from src.shared.time_utils import utc_now

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class LoginRequest(BaseModel):
    """JSON login payload expected by the frontend.

    ``totp_code`` is required only when the user has 2FA enabled; it accepts a
    TOTP code or a single-use backup code. It is omitted otherwise. The field is
    validated (422) at the API boundary; ``None`` bypasses the constraints for
    non-2FA logins.
    """

    username: str
    password: str
    totp_code: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=32,
        pattern=r"^[A-Za-z0-9 ]+$",
        description=(
            "A TOTP code or a single-use backup code; required only when 2FA is "
            "enabled. Optional internal spaces are stripped before verification."
        ),
    )


class RegisterRequest(BaseModel):
    """JSON registration payload."""

    username: str
    email: EmailStr
    password: str
    full_name: str = ""


def _build_token_response(username: str, token_version: int = 0) -> dict[str, Any]:
    """Build access/refresh tokens carrying the user's security stamp (``stv``).

    ``stv`` is checked against ``users.token_version`` on every authenticated
    request so ``logout-all`` (which bumps the column) invalidates prior tokens.
    """
    claims = {"sub": username, "stv": int(token_version or 0)}
    access_token = JWTUtils.create_access_token(claims)
    refresh_token = JWTUtils.create_refresh_token(claims)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 3600,
    }


def _username_value(user: User) -> str:
    return str(cast(object, user.username))


def _hashed_password_value(user: User) -> str:
    return str(cast(object, user.hashed_password))


def _has_db_revocation_state(user: object) -> bool:
    """True for principals backed by a real ``users`` row.

    Service-token and dev-bypass stand-ins expose no ``token_version``, so they
    cannot be revoked per session and are handled separately at logout time.
    """
    return getattr(user, "token_version", None) is not None


def _bearer_token_from_request(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return header.strip()


def _revoke_presented_token(token: str) -> None:
    """Blacklist the JTI carried by ``token`` for the remainder of its lifetime."""
    payload = JWTUtils.decode_token(token) if token else None
    if not payload:
        return

    jti = payload.get("jti")
    if not jti:
        return

    expires_at: Optional[datetime] = None
    exp = payload.get("exp")
    if exp is not None:
        try:
            expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            expires_at = None

    TokenBlacklist.blacklist_token(jti, expires_at)


def _authenticate_user(
    username: str,
    password: str,
    session: Session,
    totp_code: Optional[str] = None,
) -> dict[str, Any]:
    if is_auth_bypass_enabled():
        return _build_token_response(username)

    user = session.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    hashed_password = _hashed_password_value(user)
    if not PasswordUtils.verify_password(password, hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # 2FA enforcement: a user with TOTP enabled must supply a valid code. This
    # runs *after* the password check so a wrong password still returns the
    # generic "Invalid username or password" (fail closed; no enumeration). The
    # code is accepted as either a TOTP code or a single-use backup code (the
    # backup is consumed on success — the lost-device recovery path).
    user_id = int(getattr(user, "id", 0) or 0)
    if is_two_factor_enabled(session, user_id):
        normalized_totp_code = (totp_code or "").strip()
        if not normalized_totp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="2FA code required",
            )
        if not verify_login_second_factor(session, user_id, normalized_totp_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA token",
            )

    return _build_token_response(
        _username_value(user),
        int(getattr(user, "token_version", 0) or 0),
    )


@router.post("/token")
async def token_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
    totp_code: Optional[str] = Form(default=None),
) -> dict[str, Any]:
    """OAuth2 login endpoint (also used by the Swagger UI Authorize dialog).

    ``totp_code`` is an additional optional form field; users with 2FA enabled
    must supply it. The standard Swagger Authorize dialog cannot send it, so
    2FA-enabled accounts cannot log in via the Swagger UI — by design.
    """
    return _authenticate_user(
        form_data.username, form_data.password, session, totp_code=totp_code
    )


@router.post("/login")
async def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Frontend-compatible JSON login endpoint."""
    return _authenticate_user(
        payload.username, payload.password, session, totp_code=payload.totp_code
    )


@router.post("/register")
async def register(
    payload: RegisterRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Register endpoint."""
    username = SecurityUtils.sanitize_input(payload.username, max_length=50)
    full_name = SecurityUtils.sanitize_input(payload.full_name, max_length=100)
    email = payload.email.strip().lower()

    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is required",
        )

    if not SecurityUtils.is_email_valid(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    password_strength = SecurityUtils.validate_password_strength(payload.password)
    if not password_strength["is_valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(password_strength["errors"]),
        )

    existing_user = (
        session.query(User)
        .filter((User.username == username) | (User.email == email))
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    user = User(
        username=username,
        email=email,
        hashed_password=PasswordUtils.hash_password(payload.password),
        full_name=full_name or None,
        is_active=True,
        is_admin=False,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    token_response = _build_token_response(
        _username_value(user),
        int(getattr(user, "token_version", 0) or 0),
    )
    return {
        "message": "User registered successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        **token_response,
    }


_SERVICE_TOKEN_REVOCATION_MESSAGE = (
    "Service tokens are rotated via environment configuration "
    "(BOT_API_TOKEN / BOT_API_TOKEN_PREVIOUS / BOT_API_TOKENS), not revoked per session."
)


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Logout the current session by revoking the presented JWT (JTI blacklist)."""
    if is_auth_bypass_enabled():
        return {"message": "Logged out"}

    if not _has_db_revocation_state(current_user):
        return {"message": _SERVICE_TOKEN_REVOCATION_MESSAGE}

    _revoke_presented_token(_bearer_token_from_request(request))
    return {"message": "Logged out"}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Revoke every outstanding token for the current user.

    Bumps ``users.token_version`` so all previously issued JWTs (whose ``stv``
    claim no longer matches) are rejected on the next request, and also
    blacklists the caller's current token for immediate effect.
    """
    if is_auth_bypass_enabled():
        return {"message": "Logged out from all sessions"}

    if not _has_db_revocation_state(current_user):
        return {"message": _SERVICE_TOKEN_REVOCATION_MESSAGE}

    user = (
        session.query(User)
        .filter(User.username == _username_value(current_user))
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    new_version = int(getattr(user, "token_version", 0) or 0) + 1
    setattr(user, "token_version", new_version)
    session.commit()

    _revoke_presented_token(_bearer_token_from_request(request))
    return {
        "message": "Logged out from all sessions",
        "token_version": new_version,
    }
