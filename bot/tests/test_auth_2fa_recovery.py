"""Tests for 2FA recovery: backup codes + self-service disable.

These exercise the real DB queries (issue / consume / disable / verify login
second-factor) against an in-memory SQLite session, so the hashing, single-use
consumption, and revoke semantics are validated faithfully. Route handlers are
invoked directly with the SQLite session (their ``Depends`` defaults are
bypassed on direct call, the same pattern used in ``test_auth_2fa_login.py``).
"""

import asyncio
from datetime import timedelta

import pyotp
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from internal.domain import Base
from src.api import server
from src.api.v1 import auth as auth_routes
from src.api.v1.auth import password_2fa
from src.api.v1.auth.totp_state import (
    is_two_factor_enabled,
    issue_backup_codes,
)
from src.infrastructure.domain.models.auth_models import User, UserToken
from src.shared.time_utils import utc_now

AUTH_TOKEN_KEYS = {"access_token", "refresh_token", "token_type", "expires_in"}


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[User.__table__, UserToken.__table__])
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def _future():
    return utc_now() + timedelta(days=3650)


def _make_user(s, username="alice"):
    user = User(
        username=username,
        email=f"{username}@example.local",
        hashed_password="x",
        is_active=True,
    )
    s.add(user)
    s.commit()
    return user


def _add_secret(s, user, secret):
    s.add(
        UserToken(
            user_id=user.id,
            token=secret,
            token_type="totp_secret",
            expires_at=_future(),
            is_revoked=False,
        )
    )
    s.commit()


def _add_enabled(s, user):
    s.add(
        UserToken(
            user_id=user.id,
            token=f"enabled:{user.id}",
            token_type="totp_enabled",
            expires_at=_future(),
            is_revoked=False,
        )
    )
    s.commit()


def _patch_token_plumbing(monkeypatch):
    monkeypatch.setattr(
        auth_routes.JWTUtils, "create_access_token", lambda _p: "acc-token"
    )
    monkeypatch.setattr(
        auth_routes.JWTUtils, "create_refresh_token", lambda _p: "ref-token"
    )
    monkeypatch.setattr(auth_routes.PasswordUtils, "verify_password", lambda *_a: True)


def _login(session, username, password, totp_code=None):
    payload = auth_routes.LoginRequest(
        username=username, password=password, totp_code=totp_code
    )
    return asyncio.run(auth_routes.login(payload, session=session))


# --------------------------------------------------------------------------- #
# /verify issues backup codes on enable
# --------------------------------------------------------------------------- #
def test_verify_issues_backup_codes_on_enable(session):
    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)  # not yet enabled

    resp = asyncio.run(
        password_2fa.verify_2fa(
            payload=password_2fa.Verify2FARequest(token=pyotp.TOTP(secret).now()),
            current_user=user,
            session=session,
        )
    )

    assert resp["is_enabled"] is True
    codes = resp["backup_codes"]
    assert len(codes) == 10
    assert all(isinstance(c, str) and len(c) == 16 for c in codes)

    rows = session.query(UserToken).filter(UserToken.token_type == "totp_backup").all()
    assert len(rows) == 10
    assert all(not r.is_revoked for r in rows)
    # stored hashed — no plaintext code appears in the DB
    assert all(r.token not in codes for r in rows)


def test_verify_when_already_enabled_does_not_reissue_codes(session):
    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)
    _add_enabled(session, user)

    resp = asyncio.run(
        password_2fa.verify_2fa(
            payload=password_2fa.Verify2FARequest(token=pyotp.TOTP(secret).now()),
            current_user=user,
            session=session,
        )
    )

    assert resp["is_enabled"] is True
    assert "backup_codes" not in resp  # only issued on the enable transition


# --------------------------------------------------------------------------- #
# Backup codes at login (consumption)
# --------------------------------------------------------------------------- #
def test_backup_code_works_at_login_and_is_consumed(session, monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)
    _add_enabled(session, user)
    codes = issue_backup_codes(session, user.id)

    result = _login(session, "alice", "pw", totp_code=codes[0])
    assert set(result.keys()) == AUTH_TOKEN_KEYS

    consumed = (
        session.query(UserToken)
        .filter(
            UserToken.token_type == "totp_backup",
            UserToken.is_revoked.is_(True),
        )
        .all()
    )
    assert len(consumed) == 1  # exactly the one used

    # single-use: the same code no longer works
    with pytest.raises(HTTPException) as exc:
        _login(session, "alice", "pw", totp_code=codes[0])
    assert exc.value.status_code == 401


def test_totp_still_works_at_login_when_backups_exist(session, monkeypatch):
    """verify_login_second_factor tries TOTP first; backups don't shadow it."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)
    _add_enabled(session, user)
    issue_backup_codes(session, user.id)

    result = _login(session, "alice", "pw", totp_code=pyotp.TOTP(secret).now())
    assert set(result.keys()) == AUTH_TOKEN_KEYS
    # no backup consumed when TOTP succeeds
    consumed = (
        session.query(UserToken)
        .filter(
            UserToken.token_type == "totp_backup",
            UserToken.is_revoked.is_(True),
        )
        .all()
    )
    assert consumed == []


# --------------------------------------------------------------------------- #
# /backup-codes/regenerate
# --------------------------------------------------------------------------- #
def test_regenerate_requires_valid_totp(session):
    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)
    _add_enabled(session, user)
    issue_backup_codes(session, user.id)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            password_2fa.regenerate_backup_codes(
                payload=password_2fa.Verify2FARequest(token="000000"),
                current_user=user,
                session=session,
            )
        )
    assert exc.value.status_code == 401


def test_regenerate_invalidates_old_codes(session, monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)
    _add_enabled(session, user)
    old_codes = issue_backup_codes(session, user.id)

    resp = asyncio.run(
        password_2fa.regenerate_backup_codes(
            payload=password_2fa.Verify2FARequest(token=pyotp.TOTP(secret).now()),
            current_user=user,
            session=session,
        )
    )
    new_codes = resp["backup_codes"]
    assert len(new_codes) == 10
    assert set(new_codes).isdisjoint(old_codes)

    # old backup code is now dead at login
    with pytest.raises(HTTPException) as exc:
        _login(session, "alice", "pw", totp_code=old_codes[0])
    assert exc.value.status_code == 401

    # new backup code works
    result = _login(session, "alice", "pw", totp_code=new_codes[0])
    assert set(result.keys()) == AUTH_TOKEN_KEYS


# --------------------------------------------------------------------------- #
# /disable
# --------------------------------------------------------------------------- #
def test_disable_with_totp_turns_off_2fa(session, monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)
    _add_enabled(session, user)
    issue_backup_codes(session, user.id)

    resp = asyncio.run(
        password_2fa.disable_2fa(
            payload=password_2fa.SecondFactorRequest(token=pyotp.TOTP(secret).now()),
            current_user=user,
            session=session,
        )
    )
    assert resp["is_enabled"] is False
    assert not is_two_factor_enabled(session, user.id)

    # login no longer requires a code
    result = _login(session, "alice", "pw")
    assert set(result.keys()) == AUTH_TOKEN_KEYS


def test_disable_with_backup_code_consumes_and_disables(session, monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)
    _add_enabled(session, user)
    codes = issue_backup_codes(session, user.id)

    resp = asyncio.run(
        password_2fa.disable_2fa(
            payload=password_2fa.SecondFactorRequest(token=codes[0]),
            current_user=user,
            session=session,
        )
    )
    assert resp["is_enabled"] is False
    assert not is_two_factor_enabled(session, user.id)
    # the backup used to disable is consumed
    consumed = (
        session.query(UserToken)
        .filter(
            UserToken.token_type == "totp_backup",
            UserToken.is_revoked.is_(True),
        )
        .all()
    )
    # disable revokes all backups, but at least the one used is revoked
    assert len(consumed) >= 1


def test_disable_with_wrong_token_keeps_2fa_enabled(session):
    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)
    _add_enabled(session, user)
    issue_backup_codes(session, user.id)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            password_2fa.disable_2fa(
                payload=password_2fa.SecondFactorRequest(token="000000"),
                current_user=user,
                session=session,
            )
        )
    assert exc.value.status_code == 401
    assert is_two_factor_enabled(session, user.id) is True
    # no backup was consumed by the failed attempt
    consumed = (
        session.query(UserToken)
        .filter(
            UserToken.token_type == "totp_backup",
            UserToken.is_revoked.is_(True),
        )
        .all()
    )
    assert consumed == []


def test_disable_when_not_enabled_returns_400(session):
    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)  # secret but not enabled

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            password_2fa.disable_2fa(
                payload=password_2fa.SecondFactorRequest(
                    token=pyotp.TOTP(secret).now()
                ),
                current_user=user,
                session=session,
            )
        )
    assert exc.value.status_code == 400


def test_re_enable_after_disable_does_not_raise(session, monkeypatch):
    """Regression: ``totp_enabled`` uses a unique deterministic token, so
    disable→re-enable must un-revoke the existing row (not insert a duplicate
    and hit IntegrityError)."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    user = _make_user(session)
    secret = pyotp.random_base32()
    _add_secret(session, user, secret)
    _add_enabled(session, user)
    issue_backup_codes(session, user.id)

    asyncio.run(
        password_2fa.disable_2fa(
            payload=password_2fa.SecondFactorRequest(token=pyotp.TOTP(secret).now()),
            current_user=user,
            session=session,
        )
    )
    assert not is_two_factor_enabled(session, user.id)

    # fresh secret (old one is revoked after disable)
    new_secret = pyotp.random_base32()
    _add_secret(session, user, new_secret)

    resp = asyncio.run(
        password_2fa.verify_2fa(
            payload=password_2fa.Verify2FARequest(token=pyotp.TOTP(new_secret).now()),
            current_user=user,
            session=session,
        )
    )
    assert resp["is_enabled"] is True
    assert len(resp["backup_codes"]) == 10
    assert is_two_factor_enabled(session, user.id)


# --------------------------------------------------------------------------- #
# Boundary validation at the API layer
# --------------------------------------------------------------------------- #
def test_disable_malformed_token_rejected_at_boundary(monkeypatch):
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    monkeypatch.setenv("APP_CONFIG_ENV", "development")
    client = TestClient(server.app)

    response = client.post("/api/v1/auth/2fa/disable", json={"token": "!!!bad"})
    assert response.status_code == 422


def test_login_accepts_hex_backup_code_at_boundary(monkeypatch):
    """The login ``totp_code`` pattern was broadened to admit hex backup codes
    (previously ``^[\\d ]+$`` → 422). A hex code must now pass the boundary."""
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    monkeypatch.setenv("APP_CONFIG_ENV", "development")
    client = TestClient(server.app)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "alice",
            "password": "pw",
            "totp_code": "abcdef0123456789",
        },
    )
    assert response.status_code != 422  # reached the handler (no real user → 401)
