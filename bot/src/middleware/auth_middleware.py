"""
JWT Authentication middleware and FastAPI security dependencies
Provides JWT token validation, user authentication, and role-based access control
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.infrastructure.domain.models.auth_models import JWTToken, LoginAttempt, User
from src.api.auth_utils import JWTUtils, SecurityUtils, TokenBlacklist
from src.infrastructure.database import get_session

# FastAPI security scheme for JWT Bearer tokens
security = HTTPBearer(auto_error=False)


class AuthenticationError(HTTPException):
    """Raised when authentication fails"""
    pass


class AuthorizationError(HTTPException):
    """Raised when user lacks required permissions"""
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
    if not credentials:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token = credentials.credentials
        payload = JWTUtils.verify_token(token)
        username: str = payload.get("sub")

        if username is None:
            raise AuthenticationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = session.query(User).filter(User.username == username).first()
    if not user:
        raise AuthenticationError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


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
    if not current_user.is_admin:
        raise AuthorizationError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user

