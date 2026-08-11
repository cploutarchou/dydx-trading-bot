"""Regression tests for TOTP (2FA) enforcement at login.

Closes the gap left by the 2FA-router mount (IMPROVEMENTS.md dead-code item):
once a user enables 2FA, ``POST /auth/login`` (and the OAuth2 ``/token`` path)
must require a valid TOTP code. Users without 2FA enabled log in unchanged.

The suite drives the real :func:`_authenticate_user` branch logic through the
real :mod:`src.api.v1.auth.totp_state` helpers (including a genuine ``pyotp``
code), using a stub session that serves controllable ``User`` / ``UserToken``
rows. JWT creation and password verification are monkeypatched so the assertions
focus on the 2FA gate, not token plumbing.
"""

import asyncio
from types import SimpleNamespace

import pyotp
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api import server
from src.api.v1 import auth
from src.infrastructure.domain.models.auth_models import User, UserToken

AUTH_TOKEN_KEYS = {"access_token", "refresh_token", "token_type", "expires_in"}


# --------------------------------------------------------------------------- #
# Stub session
# --------------------------------------------------------------------------- #
class _UserQuery:
    def __init__(self, user):
        self._user = user

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._user


class _TokenQuery:
    """Serves a ``UserToken`` row keyed by the ``token_type`` filter clause."""

    def __init__(self, rows):
        # rows: {"totp_secret": record|None, "totp_enabled": record|None}
        self._rows = rows
        self._token_type = None

    def filter(self, *clauses):
        for clause in clauses:
            value = getattr(getattr(clause, "right", None), "value", None)
            if value in ("totp_secret", "totp_enabled"):
                self._token_type = value
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._rows.get(self._token_type) if self._token_type else None


class _FakeSession:
    def __init__(self, user=None, token_rows=None):
        self._user = user
        self._token_rows = token_rows or {}

    def query(self, model):
        if model is User:
            return _UserQuery(self._user)
        return _TokenQuery(self._token_rows)


def _token_row(token):
    return SimpleNamespace(token=token)


def _make_user(*, user_id=42, username="alice", token_version=3):
    return SimpleNamespace(
        id=user_id,
        username=username,
        hashed_password="$2b$12$irrelevant",
        token_version=token_version,
    )


def _patch_token_plumbing(monkeypatch):
    """Replace JWT/password internals so success is observable without secrets."""
    monkeypatch.setattr(
        auth.JWTUtils, "create_access_token", lambda _payload: "acc-token"
    )
    monkeypatch.setattr(
        auth.JWTUtils, "create_refresh_token", lambda _payload: "ref-token"
    )
    monkeypatch.setattr(auth.PasswordUtils, "verify_password", lambda *_a: True)


def _login(payload, session):
    return asyncio.run(auth.login(payload, session=session))


# --------------------------------------------------------------------------- #
# Non-2FA login is unchanged (backward compatibility)
# --------------------------------------------------------------------------- #
def test_login_without_2fa_enabled_succeeds_without_code(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    fake = _FakeSession(user=_make_user(), token_rows={})  # no totp_enabled row
    result = _login(auth.LoginRequest(username="alice", password="pw"), session=fake)

    assert set(result.keys()) == AUTH_TOKEN_KEYS
    assert result["token_type"] == "bearer"


# --------------------------------------------------------------------------- #
# 2FA-enabled login must supply a valid code
# --------------------------------------------------------------------------- #
def test_login_with_2fa_enabled_rejects_missing_code(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    secret = pyotp.random_base32()
    fake = _FakeSession(
        user=_make_user(),
        token_rows={
            "totp_secret": _token_row(secret),
            "totp_enabled": _token_row("enabled:42"),
        },
    )

    with pytest.raises(HTTPException) as exc:
        _login(auth.LoginRequest(username="alice", password="pw"), session=fake)

    assert exc.value.status_code == 401
    assert exc.value.detail == "2FA code required"


def test_login_with_2fa_enabled_rejects_wrong_code(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    secret = pyotp.random_base32()
    fake = _FakeSession(
        user=_make_user(),
        token_rows={
            "totp_secret": _token_row(secret),
            "totp_enabled": _token_row("enabled:42"),
        },
    )

    with pytest.raises(HTTPException) as exc:
        _login(
            auth.LoginRequest(username="alice", password="pw", totp_code="000000"),
            session=fake,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid 2FA token"


def test_login_with_2fa_enabled_accepts_correct_code(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    secret = pyotp.random_base32()
    fake = _FakeSession(
        user=_make_user(),
        token_rows={
            "totp_secret": _token_row(secret),
            "totp_enabled": _token_row("enabled:42"),
        },
    )

    result = _login(
        auth.LoginRequest(
            username="alice", password="pw", totp_code=pyotp.TOTP(secret).now()
        ),
        session=fake,
    )

    assert set(result.keys()) == AUTH_TOKEN_KEYS
    assert result["access_token"] == "acc-token"


def test_login_with_2fa_enabled_rejects_wrong_length_code(monkeypatch):
    """A 7-digit code passes Pydantic but fails the handler {6,8} format check."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    secret = pyotp.random_base32()
    fake = _FakeSession(
        user=_make_user(),
        token_rows={
            "totp_secret": _token_row(secret),
            "totp_enabled": _token_row("enabled:42"),
        },
    )

    with pytest.raises(HTTPException) as exc:
        _login(
            auth.LoginRequest(username="alice", password="pw", totp_code="1234567"),
            session=fake,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid 2FA token"


def test_login_with_2fa_enabled_normalizes_spaced_code(monkeypatch):
    """Internal spaces are stripped, matching the setup/verify handler."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    secret = pyotp.random_base32()
    fake = _FakeSession(
        user=_make_user(),
        token_rows={
            "totp_secret": _token_row(secret),
            "totp_enabled": _token_row("enabled:42"),
        },
    )

    spaced = f"  {pyotp.TOTP(secret).now()[:3]} {pyotp.TOTP(secret).now()[3:]} "
    result = _login(
        auth.LoginRequest(username="alice", password="pw", totp_code=spaced),
        session=fake,
    )

    assert set(result.keys()) == AUTH_TOKEN_KEYS


# --------------------------------------------------------------------------- #
# Fail-closed and bypass semantics
# --------------------------------------------------------------------------- #
def test_wrong_password_returns_generic_error_before_2fa_check(monkeypatch):
    """A wrong password must not reach the 2FA branch (fail closed, no signal)."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    monkeypatch.setattr(auth.JWTUtils, "create_access_token", lambda _p: "acc-token")
    monkeypatch.setattr(auth.JWTUtils, "create_refresh_token", lambda _p: "ref-token")
    monkeypatch.setattr(auth.PasswordUtils, "verify_password", lambda *_a: False)

    fake = _FakeSession(
        user=_make_user(),
        token_rows={
            "totp_secret": _token_row(pyotp.random_base32()),
            "totp_enabled": _token_row("enabled:42"),
        },
    )

    with pytest.raises(HTTPException) as exc:
        _login(
            auth.LoginRequest(username="alice", password="pw", totp_code="123456"),
            session=fake,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid username or password"


def test_auth_bypass_skips_2fa_check(monkeypatch):
    """Bypass mode issues tokens without a code even when 2FA is enabled."""
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    monkeypatch.setattr(auth.JWTUtils, "create_access_token", lambda _p: "acc-token")
    monkeypatch.setattr(auth.JWTUtils, "create_refresh_token", lambda _p: "ref-token")

    # session is not even consulted in bypass mode
    result = _login(auth.LoginRequest(username="alice", password="pw"), session=None)

    assert set(result.keys()) == AUTH_TOKEN_KEYS


# --------------------------------------------------------------------------- #
# Boundary validation at the API layer
# --------------------------------------------------------------------------- #
def test_login_totp_code_pattern_rejected_at_boundary(monkeypatch):
    """A totp_code with non-alphanumeric chars is 422'd before the handler runs.

    (Hex backup codes are now valid, so the check uses a value the broadened
    ``^[A-Za-z0-9 ]+$`` pattern still rejects.)
    """
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    monkeypatch.setenv("APP_CONFIG_ENV", "development")
    client = TestClient(server.app)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "pw", "totp_code": "abc!def"},
    )

    assert response.status_code == 422


def test_login_totp_code_too_short_rejected_at_boundary(monkeypatch):
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    monkeypatch.setenv("APP_CONFIG_ENV", "development")
    client = TestClient(server.app)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "pw", "totp_code": "123"},
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# OAuth2 /token path also enforces
# --------------------------------------------------------------------------- #
def test_token_endpoint_forwards_totp_code_and_enforces(monkeypatch):
    """The OAuth2 form path applies the same 2FA gate as the JSON login."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    _patch_token_plumbing(monkeypatch)

    secret = pyotp.random_base32()
    fake = _FakeSession(
        user=_make_user(),
        token_rows={
            "totp_secret": _token_row(secret),
            "totp_enabled": _token_row("enabled:42"),
        },
    )

    # Missing code -> rejected. (totp_code must be passed explicitly: the
    # parameter's default is a Form() object, not None, when invoked directly.)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            auth.token_login(
                form_data=_Form("alice", "pw"), session=fake, totp_code=None
            )
        )
    assert exc.value.status_code == 401
    assert exc.value.detail == "2FA code required"

    # Correct code -> tokens issued.
    result = asyncio.run(
        auth.token_login(
            form_data=_Form("alice", "pw"),
            session=fake,
            totp_code=pyotp.TOTP(secret).now(),
        )
    )
    assert set(result.keys()) == AUTH_TOKEN_KEYS


class _Form:
    """Minimal stand-in for ``OAuth2PasswordRequestForm``."""

    def __init__(self, username, password):
        self.username = username
        self.password = password
