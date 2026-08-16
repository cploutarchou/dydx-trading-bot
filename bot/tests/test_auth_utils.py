"""Unit tests for the authentication utilities (passwords, JWT, 2FA, blacklist)."""

import base64
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jose import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api import auth_utils  # noqa: E402
from src.api.auth_utils import (  # noqa: E402
    EmailVerificationUtils,
    JWTUtils,
    PasswordUtils,
    SecurityUtils,
    TokenBlacklist,
    TwoFactorUtils,
)


@pytest.fixture(autouse=True)
def _clean_blacklist(monkeypatch):
    """Keep TokenBlacklist class state hermetic: memory fallback, no Redis."""
    monkeypatch.setenv("REDIS_ENABLED", "false")
    TokenBlacklist._fallback_tokens.clear()
    TokenBlacklist._redis_client = None
    TokenBlacklist._redis_initialised = False
    yield
    TokenBlacklist._fallback_tokens.clear()


def _token(payload):
    return jwt.encode(payload, auth_utils.SECRET_KEY, algorithm=auth_utils.ALGORITHM)


# ---------------------------------------------------------------- passwords


def test_password_hash_and_verify_roundtrip():
    hashed = PasswordUtils.hash_password("S3cret!Password")

    assert hashed != "S3cret!Password"
    assert PasswordUtils.verify_password("S3cret!Password", hashed) is True
    assert PasswordUtils.verify_password("wrong-password", hashed) is False


def test_password_truncation_at_72_bytes_matches_bcrypt_limit():
    long_password = "a" * 80
    hashed = PasswordUtils.hash_password(long_password)

    # bcrypt only considers the first 72 bytes; a password differing only
    # beyond that boundary still verifies (documented truncation behavior)
    assert PasswordUtils.verify_password("a" * 80, hashed) is True
    assert PasswordUtils.verify_password("a" * 72 + "DIFFERENT-TAIL", hashed) is True


def test_generate_secure_token_and_backup_codes():
    assert (
        PasswordUtils.generate_secure_token() != PasswordUtils.generate_secure_token()
    )

    codes = PasswordUtils.generate_backup_codes()
    assert len(codes) == 10
    assert all(len(code) == 16 for code in codes)
    assert all(all(c in "0123456789abcdef" for c in code) for code in codes)
    assert len(set(codes)) == 10  # unique


# ---------------------------------------------------------------- JWT


def test_create_and_decode_access_token_roundtrip():
    token = JWTUtils.create_access_token({"sub": "user-1", "roles": ["admin"]})

    payload = JWTUtils.decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["roles"] == ["admin"]
    assert payload["type"] == "access"
    assert payload["jti"]
    assert isinstance(payload["exp"], int)
    # Default expiry is ACCESS_TOKEN_EXPIRE_MINUTES from now (30 min default)
    expected_exp = datetime.now(timezone.utc) + timedelta(
        minutes=auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    assert abs(payload["exp"] - int(expected_exp.timestamp())) < 10


def test_create_refresh_token_roundtrip_with_custom_expiry():
    delta = timedelta(hours=2)
    token = JWTUtils.create_refresh_token({"sub": "user-2"}, expires_delta=delta)

    payload = JWTUtils.decode_token(token)
    assert payload["type"] == "refresh"
    assert payload["exp"] == pytest.approx(
        int((datetime.now(timezone.utc) + delta).timestamp()), abs=10
    )
    assert JWTUtils.get_token_jti(token) == payload["jti"]


def test_decode_token_rejects_tampered_signature():
    token = JWTUtils.create_access_token({"sub": "user-1"})
    tampered = token[:-6] + ("AAAAAA" if not token.endswith("AAAAAA") else "BBBBBB")

    assert JWTUtils.decode_token(tampered) is None
    assert JWTUtils.decode_token("not-a-jwt") is None


def test_is_token_expired_matrix():
    now = datetime.now(timezone.utc)
    future = int((now + timedelta(hours=1)).timestamp())
    past = int((now - timedelta(hours=1)).timestamp())

    assert JWTUtils.is_token_expired(_token({"sub": "u", "exp": future})) is False
    # jose rejects expired tokens at decode time -> treated as expired
    assert JWTUtils.is_token_expired(_token({"sub": "u", "exp": past})) is True
    # Missing exp counts as expired
    assert JWTUtils.is_token_expired(_token({"sub": "u"})) is True
    # Numeric-string exp parses
    assert JWTUtils.is_token_expired(_token({"sub": "u", "exp": str(future)})) is False


def test_is_token_expired_parses_iso_string_exp(monkeypatch):
    # jose itself refuses to decode ISO-string exp claims, so this defensive
    # branch is only reachable by stubbing the decode step
    iso = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    monkeypatch.setattr(JWTUtils, "decode_token", lambda _: {"sub": "u", "exp": iso})
    assert JWTUtils.is_token_expired("stubbed") is False

    past_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    monkeypatch.setattr(
        JWTUtils, "decode_token", lambda _: {"sub": "u", "exp": past_iso}
    )
    assert JWTUtils.is_token_expired("stubbed") is True


def test_verify_token_accepts_valid_and_rejects_invalid():
    future = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())

    good = JWTUtils.verify_token(_token({"sub": "u", "exp": future, "jti": "j-1"}))
    assert good is not None and good["sub"] == "u"

    # numeric-string exp is accepted
    string_exp = JWTUtils.verify_token(
        _token({"sub": "u", "exp": str(future), "jti": "j-2"})
    )
    assert string_exp is not None

    # missing jti / missing exp / garbage
    assert JWTUtils.verify_token(_token({"sub": "u", "exp": future})) is None
    assert JWTUtils.verify_token(_token({"sub": "u", "jti": "j-3"})) is None
    assert JWTUtils.verify_token("garbage") is None


def test_verify_token_rejects_blacklisted_jti():
    future = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    token = _token({"sub": "u", "exp": future, "jti": "blacklisted-jti"})

    assert JWTUtils.verify_token(token) is not None
    TokenBlacklist.blacklist_token("blacklisted-jti")
    assert JWTUtils.verify_token(token) is None


def test_verify_token_rejects_unparseable_exp(monkeypatch):
    # Defensive branch: a decode result whose exp is neither number, numeric
    # string, ISO string, nor datetime is rejected
    monkeypatch.setattr(
        JWTUtils, "decode_token", lambda _: {"sub": "u", "jti": "j", "exp": [1, 2]}
    )
    assert JWTUtils.verify_token("whatever") is None


# ---------------------------------------------------------------- 2FA


def test_totp_secret_uri_qrcode_and_verification():
    secret = TwoFactorUtils.generate_totp_secret()
    assert len(secret) >= 16  # pyotp base32 default

    uri = TwoFactorUtils.generate_totp_uri(secret, "alice", issuer="TestBot")
    assert uri.startswith("otpauth://totp/")
    assert "TestBot" in uri and "alice" in uri

    qr = TwoFactorUtils.generate_qr_code(secret, "alice")
    assert qr.startswith("data:image/png;base64,")
    payload = qr.split(",", 1)[1]
    assert base64.b64decode(payload).startswith(b"\x89PNG")  # valid PNG magic

    current = TwoFactorUtils.get_current_totp_token(secret)
    assert len(current) == 6 and current.isdigit()
    assert TwoFactorUtils.verify_totp_token(secret, current) is True
    assert (
        TwoFactorUtils.verify_totp_token(secret, "000000") is False
        or current == "000000"
    )


# ---------------------------------------------------------------- security


def test_validate_password_strength_reports_each_requirement():
    ok, weak = "Str0ng!Pass", "short"
    result = SecurityUtils.validate_password_strength(ok)
    assert result["is_valid"] is True
    assert result["errors"] == []
    assert result["strength_score"] == 5

    result = SecurityUtils.validate_password_strength(weak)
    assert result["is_valid"] is False
    # short + no upper + no digit + no special (has lower via 'short')
    assert len(result["errors"]) == 4
    assert result["strength_score"] == 1

    result = SecurityUtils.validate_password_strength("nocaps0!")
    assert any("uppercase" in e for e in result["errors"])
    result = SecurityUtils.validate_password_strength("NOLOWER0!")
    assert any("lowercase" in e for e in result["errors"])
    assert len(result["errors"]) == 1


def test_email_validation_and_sanitization():
    assert SecurityUtils.is_email_valid("user@example.com") is True
    assert SecurityUtils.is_email_valid("not-an-email") is False
    assert SecurityUtils.is_email_valid("a@b") is False

    assert SecurityUtils.sanitize_input("") == ""
    assert SecurityUtils.sanitize_input("clean") == "clean"
    # Control chars removed, tabs/newlines kept, length truncated
    assert SecurityUtils.sanitize_input("a\x00b\x01c") == "abc"
    assert SecurityUtils.sanitize_input("a\nb\tc\r") == "a\nb\tc\r"
    assert len(SecurityUtils.sanitize_input("x" * 500)) == 255


def test_hash_string_reset_tokens_and_rate_limit_keys():
    assert SecurityUtils.hash_string("data") == SecurityUtils.hash_string("data")
    assert SecurityUtils.hash_string("data") != SecurityUtils.hash_string(
        "data", "salt"
    )

    raw = base64.urlsafe_b64decode(
        SecurityUtils.generate_password_reset_token("user-9")
    ).decode()
    assert raw.startswith("user-9:")

    code = SecurityUtils.generate_email_verification_code()
    assert len(code) == 6 and code.isdigit()

    key = SecurityUtils.rate_limit_key("1.2.3.4", "/api/v1/bots")
    assert key.startswith("rate_limit:") and key.endswith(":/api/v1/bots")


# ------------------------------------------------------- email verification


def test_email_verification_utils():
    tokens = EmailVerificationUtils.create_verification_tokens()
    assert set(tokens) == {"verification_code", "verification_token"}
    assert len(tokens["verification_code"]) == 6

    fresh = datetime.now(timezone.utc)
    assert EmailVerificationUtils.is_verification_expired(fresh) is False
    assert (
        EmailVerificationUtils.is_verification_expired(
            fresh - timedelta(minutes=20), expires_in_minutes=15
        )
        is True
    )
    # Naive datetimes are interpreted as UTC per the documented contract —
    # build one from a UTC timestamp (naive local time would be wrong here)
    naive_utc = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20)
    assert (
        EmailVerificationUtils.is_verification_expired(naive_utc, expires_in_minutes=15)
        is True
    )


# ---------------------------------------------------------------- blacklist


def test_token_blacklist_memory_fallback():
    assert TokenBlacklist.is_token_blacklisted("jti-a") is False
    TokenBlacklist.blacklist_token("jti-a")
    assert TokenBlacklist.is_token_blacklisted("jti-a") is True
    TokenBlacklist.clear_expired_tokens()  # documented no-op


def test_token_blacklist_uses_redis_with_ttl():
    class FakeRedis:
        def __init__(self):
            self.store = {}

        def setex(self, key, ttl, value):
            self.store[key] = (ttl, value)

        def exists(self, key):
            return int(key in self.store)

    fake = FakeRedis()
    TokenBlacklist._redis_client = fake
    TokenBlacklist._redis_initialised = True

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    TokenBlacklist.blacklist_token("jti-redis", expires_at)

    key = TokenBlacklist._REDIS_PREFIX + "jti-redis"
    assert key in fake.store
    ttl, value = fake.store[key]
    assert 1 <= ttl <= 600  # remaining lifetime, clamped to >= 1s
    assert value == "1"
    assert TokenBlacklist.is_token_blacklisted("jti-redis") is True
    assert "jti-redis" not in TokenBlacklist._fallback_tokens


def test_token_blacklist_redis_errors_fall_back_to_memory():
    class BrokenRedis:
        def setex(self, *a, **k):
            raise ConnectionError("redis down")

        def exists(self, *a, **k):
            raise ConnectionError("redis down")

    TokenBlacklist._redis_client = BrokenRedis()
    TokenBlacklist._redis_initialised = True

    TokenBlacklist.blacklist_token("jti-broken")
    assert "jti-broken" in TokenBlacklist._fallback_tokens
    assert TokenBlacklist.is_token_blacklisted("jti-broken") is True
