"""
JWT Authentication middleware and FastAPI security dependencies
Provides JWT token validation, user authentication, and role-based access control
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from internal.domain.models.auth_models import JWTToken, LoginAttempt, User
from auth_utils import JWTUtils, SecurityUtils, TokenBlacklist
from database import get_session

# FastAPI security scheme for JWT Bearer tokens
security = HTTPBearer(auto_error=False)


class AuthenticationError(HTTPException):
    """Custom authentication error"""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    """Custom authorization error"""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


def get_current_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_session),
) -> Optional[User]:
    """
    Extract and validate user from JWT token
    Returns None if no valid token is provided
    """
    if not credentials:
        return None

    token = credentials.credentials

    # Decode JWT token
    payload = JWTUtils.decode_token(token)
    if not payload:
        return None

    # Check token type
    if payload.get("type") != "access":
        return None

    # Check if token is blacklisted
    jti = payload.get("jti")
    if jti and TokenBlacklist.is_token_blacklisted(jti):
        return None

    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # Check if user is active (using direct database update to avoid SQLAlchemy column issues)
    if hasattr(user, "is_active") and not getattr(user, "is_active", True):
        return None

    # Update last seen using database update to avoid column assignment issues
    db.query(User).filter(User.id == user_id).update({"last_login": datetime.utcnow()})
    db.commit()

    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_session),
) -> User:
    """
    Get current authenticated user (required)
    Raises 401 if no valid token is provided
    """
    user = get_current_user_from_token(credentials, db)
    if not user:
        raise AuthenticationError("Invalid or missing authentication token")

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get current active user
    Raises 403 if user is inactive or locked
    """
    if not getattr(current_user, "is_active", True):
        raise AuthorizationError("User account is inactive")

    # Check if account is locked
    locked_until = getattr(current_user, "locked_until", None)
    if locked_until and datetime.utcnow() < locked_until:
        raise AuthorizationError("User account is temporarily locked")

    return current_user


def get_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Get current user with admin privileges
    Raises 403 if user is not an admin
    """
    if not getattr(current_user, "is_superuser", False):
        raise AuthorizationError("Administrator privileges required")

    return current_user


def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_session),
) -> Optional[User]:
    """
    Optional authentication - returns user if token is provided and valid
    Does not raise error if no token is provided
    """
    return get_current_user_from_token(credentials, db)


class RateLimitMiddleware:
    """Rate limiting middleware for authentication endpoints"""

    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self._attempts: Dict[str, List[datetime]] = {}

    def is_rate_limited(self, key: str) -> bool:
        """Check if key is rate limited"""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)

        # Clean old attempts
        if key in self._attempts:
            self._attempts[key] = [
                attempt for attempt in self._attempts[key] if attempt > window_start
            ]

        # Check current attempts
        attempts = self._attempts.get(key, [])
        return len(attempts) >= self.max_attempts

    def record_attempt(self, key: str) -> None:
        """Record an attempt"""
        now = datetime.utcnow()
        if key not in self._attempts:
            self._attempts[key] = []
        self._attempts[key].append(now)


# Global rate limiter instance
rate_limiter = RateLimitMiddleware()


def check_rate_limit(request: Request, endpoint: str = "default") -> None:
    """
    Check rate limiting for specific endpoint
    Raises 429 if rate limit is exceeded
    """
    client_ip = request.client.host if request.client else "unknown"
    key = SecurityUtils.rate_limit_key(client_ip, endpoint)

    if rate_limiter.is_rate_limited(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )


def record_login_attempt(
    db: Session,
    username: str,
    ip_address: str,
    user_agent: Optional[str] = None,
    success: bool = False,
    failure_reason: Optional[str] = None,
    two_fa_required: bool = False,
    two_fa_success: Optional[bool] = None,
) -> None:
    """Record a login attempt for security monitoring"""
    attempt = LoginAttempt(
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        failure_reason=failure_reason,
        two_fa_required=two_fa_required,
        two_fa_success=two_fa_success,
    )

    db.add(attempt)
    db.commit()


def validate_refresh_token(refresh_token: str, db: Session) -> Optional[User]:
    """
    Validate refresh token and return associated user
    Returns None if token is invalid
    """
    # Decode refresh token
    payload = JWTUtils.decode_token(refresh_token)
    if not payload:
        return None

    # Check token type
    if payload.get("type") != "refresh":
        return None

    # Check if token is blacklisted
    jti = payload.get("jti")
    if jti and TokenBlacklist.is_token_blacklisted(jti):
        return None

    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not getattr(user, "is_active", True):
        return None

    # Check if refresh token exists in database
    token_record = (
        db.query(JWTToken)
        .filter(
            JWTToken.token_id == jti,
            JWTToken.user_id == user.id,
            JWTToken.token_type == "refresh",
            JWTToken.is_revoked.is_(False),
        )
        .first()
    )

    if not token_record:
        return None

    return user


def revoke_token(token: str, db: Session) -> bool:
    """
    Revoke a token (add to blacklist and mark as revoked in database)
    Returns True if token was successfully revoked
    """
    # Get token JTI
    jti = JWTUtils.get_token_jti(token)
    if not jti:
        return False

    # Add to blacklist
    TokenBlacklist.blacklist_token(jti)

    # Mark as revoked in database using update query
    updated_rows = (
        db.query(JWTToken)
        .filter(JWTToken.token_id == jti)
        .update({"is_revoked": True, "revoked_at": datetime.utcnow()})
    )

    if updated_rows > 0:
        db.commit()

    return True


def revoke_all_user_tokens(user_id: str, db: Session) -> int:
    """
    Revoke all tokens for a specific user
    Returns number of tokens revoked
    """
    # Get all active tokens for user
    tokens = (
        db.query(JWTToken)
        .filter(JWTToken.user_id == user_id, JWTToken.is_revoked.is_(False))
        .all()
    )

    # Revoke each token
    revoked_count = 0
    for token_record in tokens:
        # Get token_id value for blacklisting
        token_id_value = getattr(token_record, "token_id")
        if token_id_value:
            TokenBlacklist.blacklist_token(token_id_value)
            revoked_count += 1

    # Batch update all tokens as revoked
    if revoked_count > 0:
        db.query(JWTToken).filter(
            JWTToken.user_id == user_id, JWTToken.is_revoked.is_(False)
        ).update({"is_revoked": True, "revoked_at": datetime.utcnow()})
        db.commit()

    return revoked_count


# Dependency for specific permissions/roles
def require_permissions(*required_permissions: str):
    """
    Decorator factory for endpoints that require specific permissions
    Usage: @require_permissions("read:users", "write:trades")
    """

    def permission_dependency(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        # For now, just check if user is admin for any permission requirement
        # In a more complex system, you'd check actual user permissions
        if required_permissions and not getattr(current_user, "is_superuser", False):
            raise AuthorizationError(
                f"Missing required permissions: {', '.join(required_permissions)}"
            )
        return current_user

    return permission_dependency


if __name__ == "__main__":
    print("Authentication middleware loaded successfully!")
    print(
        f"Rate limiter configured: {rate_limiter.max_attempts} attempts per {rate_limiter.window_minutes} minutes"
    )
