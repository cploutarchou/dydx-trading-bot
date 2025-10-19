"""
JWT Authentication module with user management.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "your-secret-key-change-in-production-use-strong-key-32-chars"
)
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing - use argon2 for better compatibility and security
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# Pydantic models
class TokenData(BaseModel):
    """JWT token payload data."""

    sub: str  # user_id or username
    exp: datetime
    type: str = "access"  # access or refresh


class Token(BaseModel):
    """Token response model."""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    """User creation schema."""

    username: str
    email: EmailStr
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "username": "user@example.com",
                "email": "user@example.com",
                "password": "securepassword123",
            }
        }


class UserLogin(BaseModel):
    """User login schema."""

    username: str
    password: str


class UserResponse(BaseModel):
    """User response schema (no password)."""

    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.

    Args:
        subject: User ID or username to encode
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {"sub": subject, "exp": expire, "type": "access"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str) -> str:
    """
    Create JWT refresh token with longer expiration.

    Args:
        subject: User ID or username to encode

    Returns:
        Encoded JWT refresh token
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": subject, "exp": expire, "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenData if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        exp = payload.get("exp")
        token_type = payload.get("type", "access")

        if subject is None:
            return None

        return TokenData(
            sub=subject,
            exp=datetime.fromtimestamp(exp, tz=timezone.utc),
            type=token_type,
        )
    except JWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None


def verify_token(token: str, token_type: str = "access") -> bool:
    """
    Verify token is valid and correct type.

    Args:
        token: JWT token string
        token_type: Expected token type ('access' or 'refresh')

    Returns:
        True if valid, False otherwise
    """
    token_data = decode_token(token)
    if token_data is None:
        return False

    # Check token type
    if token_data.type != token_type:
        return False

    # Check expiration
    if token_data.exp < datetime.now(timezone.utc):
        return False

    return True


def extract_user_from_token(token: str) -> Optional[str]:
    """
    Extract user ID/username from token.

    Args:
        token: JWT token string

    Returns:
        User subject if valid token, None otherwise
    """
    token_data = decode_token(token)
    if token_data is None:
        return None

    return token_data.sub
