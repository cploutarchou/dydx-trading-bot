"""
Authentication utilities for JWT, password hashing, and 2FA
Provides secure authentication services for the trading bot API
"""

import base64
import hashlib
import io
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pyotp
import qrcode
from decouple import config
from jose import JWTError, jwt
from passlib.context import CryptContext

# Configuration
SECRET_KEY = str(config("SECRET_KEY", default=secrets.token_urlsafe(32)))
ALGORITHM = str(config("JWT_ALGORITHM", default="HS256"))
ACCESS_TOKEN_EXPIRE_MINUTES = config(
    "ACCESS_TOKEN_EXPIRE_MINUTES", default=30, cast=int
)
REFRESH_TOKEN_EXPIRE_DAYS = config("REFRESH_TOKEN_EXPIRE_DAYS", default=7, cast=int)
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = config(
    "PASSWORD_RESET_TOKEN_EXPIRE_HOURS", default=1, cast=int
)
MAX_LOGIN_ATTEMPTS = config("MAX_LOGIN_ATTEMPTS", default=5, cast=int)
LOCKOUT_DURATION_MINUTES = config("LOCKOUT_DURATION_MINUTES", default=15, cast=int)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordUtils:
    """Password hashing and verification utilities"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        import bcrypt

        # Truncate to 72 bytes for bcrypt compatibility
        password_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        import bcrypt

        # Truncate to 72 bytes for bcrypt compatibility
        password_bytes = plain_password.encode("utf-8")[:72]
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """Generate backup codes for 2FA"""
        return [secrets.token_hex(4).upper() for _ in range(count)]


class JWTUtils:
    """JWT token creation and validation utilities"""

    @staticmethod
    def create_access_token(
        data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update(
            {
                "exp": expire,
                "type": "access",
                "jti": secrets.token_urlsafe(16),  # JWT ID for blacklisting
            }
        )

        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def create_refresh_token(
        data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT refresh token"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode.update(
            {
                "exp": expire,
                "type": "refresh",
                "jti": secrets.token_urlsafe(16),  # JWT ID for blacklisting
            }
        )

        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None

    @staticmethod
    def get_token_jti(token: str) -> Optional[str]:
        """Extract JWT ID from token"""
        payload = JWTUtils.decode_token(token)
        return payload.get("jti") if payload else None

    @staticmethod
    def is_token_expired(token: str) -> bool:
        """Check if token is expired"""
        payload = JWTUtils.decode_token(token)
        if not payload:
            return True

        exp = payload.get("exp")
        if not exp:
            return True

        return datetime.utcnow() > datetime.fromtimestamp(exp)


class TwoFactorUtils:
    """Two-Factor Authentication utilities using TOTP"""

    @staticmethod
    def generate_totp_secret() -> str:
        """Generate a new TOTP secret"""
        return pyotp.random_base32()

    @staticmethod
    def generate_totp_uri(
        secret: str, username: str, issuer: str = "dYdX Trading Bot"
    ) -> str:
        """Generate a TOTP URI for QR code generation"""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=username, issuer_name=issuer)

    @staticmethod
    def generate_qr_code(
        secret: str, username: str, issuer: str = "dYdX Trading Bot"
    ) -> str:
        """Generate a QR code for TOTP setup as base64 string"""
        uri = TwoFactorUtils.generate_totp_uri(secret, username, issuer)

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, "PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_base64}"

    @staticmethod
    def verify_totp_token(secret: str, token: str, window: int = 1) -> bool:
        """Verify a TOTP token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=window)

    @staticmethod
    def get_current_totp_token(secret: str) -> str:
        """Get current TOTP token (for testing)"""
        totp = pyotp.TOTP(secret)
        return totp.now()


class SecurityUtils:
    """General security utilities"""

    @staticmethod
    def hash_string(data: str, salt: str = "") -> str:
        """Hash a string using SHA-256"""
        return hashlib.sha256((data + salt).encode()).hexdigest()

    @staticmethod
    def generate_password_reset_token(user_id: str) -> str:
        """Generate a secure password reset token"""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"{user_id}:{timestamp}:{secrets.token_urlsafe(32)}"
        return base64.urlsafe_b64encode(data.encode()).decode()

    @staticmethod
    def generate_email_verification_code() -> str:
        """Generate a 6-digit email verification code"""
        return f"{secrets.randbelow(1000000):06d}"

    @staticmethod
    def generate_email_verification_token() -> str:
        """Generate a secure email verification token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """Validate password strength and return requirements"""
        errors = []

        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")

        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "strength_score": max(0, 5 - len(errors)),
        }

    @staticmethod
    def is_email_valid(email: str) -> bool:
        """Basic email validation"""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    @staticmethod
    def sanitize_input(data: str, max_length: int = 255) -> str:
        """Sanitize user input"""
        if not data:
            return ""

        # Remove null bytes and control characters
        sanitized = "".join(
            char for char in data if ord(char) >= 32 or char in "\n\r\t"
        )

        # Truncate if too long
        return sanitized[:max_length]

    @staticmethod
    def rate_limit_key(ip_address: str, endpoint: str) -> str:
        """Generate a rate limiting key"""
        return f"rate_limit:{SecurityUtils.hash_string(ip_address)}:{endpoint}"


class EmailVerificationUtils:
    """Email verification utilities for 2FA setup and password reset"""

    @staticmethod
    def create_verification_tokens() -> Dict[str, str]:
        """Create both verification code and token"""
        return {
            "verification_code": SecurityUtils.generate_email_verification_code(),
            "verification_token": SecurityUtils.generate_email_verification_token(),
        }

    @staticmethod
    def is_verification_expired(
        created_at: datetime, expires_in_minutes: int = 15
    ) -> bool:
        """Check if verification has expired"""
        expiry_time = created_at + timedelta(minutes=expires_in_minutes)
        return datetime.utcnow() > expiry_time


class TokenBlacklist:
    """In-memory token blacklist (should be replaced with Redis in production)"""

    _blacklisted_tokens: set = set()

    @classmethod
    def blacklist_token(cls, jti: str) -> None:
        """Add token to blacklist"""
        cls._blacklisted_tokens.add(jti)

    @classmethod
    def is_token_blacklisted(cls, jti: str) -> bool:
        """Check if token is blacklisted"""
        return jti in cls._blacklisted_tokens

    @classmethod
    def clear_expired_tokens(cls) -> None:
        """Clear expired tokens from blacklist (implement with actual expiry tracking)"""
        # In production, this should be handled by Redis TTL
        pass


if __name__ == "__main__":
    # Test utilities
    print("Testing authentication utilities...")

    # Test password hashing
    password = "TestPassword123!"
    hashed = PasswordUtils.hash_password(password)
    print(f"Password verified: {PasswordUtils.verify_password(password, hashed)}")

    # Test JWT tokens
    data = {"sub": "test_user", "roles": ["user"]}
    access_token = JWTUtils.create_access_token(data)
    decoded = JWTUtils.decode_token(access_token)
    print(f"JWT decoded: {decoded}")

    # Test 2FA
    secret = TwoFactorUtils.generate_totp_secret()
    token = TwoFactorUtils.get_current_totp_token(secret)
    print(f"TOTP verified: {TwoFactorUtils.verify_totp_token(secret, token)}")

    # Test password strength
    strength = SecurityUtils.validate_password_strength(password)
    print(f"Password strength: {strength}")

    print("All tests completed!")
