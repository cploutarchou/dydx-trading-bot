"""
JWT Authentication middleware and FastAPI security dependencies
Provide JWT token validation, user authentication, and role-based access control
"""

import os
import secrets
from dataclasses import dataclass
from typing import Optional, cast

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.api.auth_utils import JWTUtils
from src.infrastructure.database import get_session
from src.infrastructure.domain.models.auth_models import User

# FastAPI security scheme for JWT Bearer tokens
security = HTTPBearer(auto_error=False)

_AUTH_BYPASS_ALLOWED_ENVIRONMENTS = {
    "development",
    "dev",
    "local",
    "test",
    "testing",
    "ci",
}


@dataclass
class _BypassUser:
    username: str
    email: str
    is_active: bool
    is_superuser: bool


@dataclass
class _ServiceTokenUser:
    username: str
    email: str
    is_active: bool
    is_superuser: bool


def current_environment_name() -> str:
    for key in ("APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return "development"


def auth_bypass_requested() -> bool:
    return os.getenv("API_BYPASS_AUTH", "false").strip().lower() == "true"


_ENVIRONMENT_VARIABLES = ("APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV")


def _explicit_environment_values() -> list[str]:
    values = (os.getenv(key, "").strip().lower() for key in _ENVIRONMENT_VARIABLES)
    return [value for value in values if value]


def auth_bypass_is_allowed_environment(environment: Optional[str] = None) -> bool:
    """Whether the auth bypass may be honoured. Fails closed.

    With an explicit ``environment`` only that value is checked. Otherwise the
    process environment decides: at least one environment variable must be set
    and every one that is set must name a local/dev/test environment. An unset
    environment is NOT development (a production image that forgot the
    variable must not accept the bypass), and a development label cannot
    override a production label in another variable.
    """
    if environment is not None and str(environment).strip():
        return str(environment).strip().lower() in _AUTH_BYPASS_ALLOWED_ENVIRONMENTS
    explicit = _explicit_environment_values()
    return bool(explicit) and all(
        value in _AUTH_BYPASS_ALLOWED_ENVIRONMENTS for value in explicit
    )


def validate_auth_bypass_configuration() -> None:
    if not auth_bypass_requested():
        return

    if auth_bypass_is_allowed_environment():
        return

    explicit = _explicit_environment_values()
    raise RuntimeError(
        "API_BYPASS_AUTH=true is forbidden outside explicit local/dev/test environments. "
        f"Environment variables ({', '.join(_ENVIRONMENT_VARIABLES)}) resolve to "
        f"{explicit or 'unset'}; every one that is set must be one of: "
        "development, dev, local, test, testing, ci, and at least one must be set."
    )


def is_auth_bypass_enabled() -> bool:
    return auth_bypass_requested() and auth_bypass_is_allowed_environment()


def _configured_service_tokens() -> list[str]:
    """Load service tokens for backend->bot delegation with overlap support for rotation."""
    candidates: list[str] = []

    # Primary token name used in backend docs/config.
    primary = os.getenv("BOT_API_TOKEN", "").strip()
    if primary:
        candidates.append(primary)

    # Explicit overlap token for zero-downtime rotation windows.
    previous = os.getenv("BOT_API_TOKEN_PREVIOUS", "").strip()
    if previous:
        candidates.append(previous)

    # Optional comma-separated pool when operators prefer a list-based rollout.
    token_list = os.getenv("BOT_API_TOKENS", "")
    if token_list:
        candidates.extend(
            token.strip() for token in token_list.split(",") if token.strip()
        )

    # Preserve order while removing duplicates.
    unique_tokens: list[str] = []
    for token in candidates:
        if token not in unique_tokens:
            unique_tokens.append(token)
    return unique_tokens


def _is_valid_service_token(token: str) -> bool:
    token = token.strip()
    if not token:
        return False

    for configured in _configured_service_tokens():
        if secrets.compare_digest(token, configured):
            return True
    return False


def authenticate_bearer_token(token: str, session: Session) -> User:
    """Authenticate a bearer token as either service-token principal or user JWT."""
    normalized = token.strip()
    if normalized.lower().startswith("bearer "):
        normalized = normalized[7:].strip()

    if _is_valid_service_token(normalized):
        return cast(
            User,
            _ServiceTokenUser(
                username="backend-service-token",
                email="service-token@internal.local",
                is_active=True,
                is_superuser=True,
            ),
        )

    payload = JWTUtils.verify_token(normalized)
    if payload is None:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: Optional[str] = payload.get("sub")
    if username is None:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = session.query(User).filter(User.username == username).first()
    if not user:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Security-stamp check: a mismatch means the user (or admin) bumped
    # ``token_version`` via logout-all, so this token is no longer trusted.
    # Legacy tokens without an ``stv`` claim are treated as version 0.
    token_stv = payload.get("stv")
    user_stv = int(getattr(user, "token_version", 0) or 0)
    claim_stv = int(token_stv) if token_stv is not None else 0
    if claim_stv != user_stv:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


class AuthenticationError(HTTPException):
    """Raised when authentication fails"""

    pass


class AuthorizationError(HTTPException):
    """Raised when a user lacks required permissions"""

    pass


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    """
    Get the current authenticated user from JWT token

    Args:
        credentials: HTTP Bearer token credentials
        session: Database session

    Returns:
        User: Authenticated user object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    if is_auth_bypass_enabled():
        return cast(
            User,
            _BypassUser(
                username="dev-bypass-user",
                email="dev-bypass@example.local",
                is_active=True,
                is_superuser=True,
            ),
        )

    if not credentials:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return authenticate_bearer_token(credentials.credentials, session)
    except Exception as e:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user - verify user is not disabled

    Args:
        current_user: Current authenticated user

    Returns:
        User: Active user object

    Raises:
        HTTPException: If user is disabled
    """
    if not current_user.is_active:
        raise AuthorizationError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get current admin user - verify user has admin role

    Args:
        current_user: Current authenticated user

    Returns:
        User: Admin user object

    Raises:
        HTTPException: If user doesn't have admin role
    """
    is_admin = getattr(current_user, "is_admin", None)
    if is_admin is None:
        is_admin = getattr(current_user, "is_superuser", False)

    if not is_admin:
        raise AuthorizationError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user
