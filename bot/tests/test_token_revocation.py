"""Token revocation tests for logout / logout-all.

Covers:
  - logout blacklists the presented JTI (single session).
  - logout-all bumps users.token_version so prior tokens mismatch on verify.
  - legacy tokens without an ``stv`` claim keep working against version 0.
  - bypass mode short-circuits to a no-op success.
  - service-token principals get a rotation message, not revocation.
  - _build_token_response embeds ``stv`` in the issued JWT.
"""

from datetime import datetime, timezone
from typing import Any, cast

import pytest

from src.api.auth_utils import JWTUtils, TokenBlacklist
from src.api.v1 import auth as auth_router
from src.middleware.auth_middleware import (
    AuthenticationError,
    authenticate_bearer_token,
)


class _StubUser:
    def __init__(self, username: str, token_version: int = 0):
        self.username = username
        self.token_version = token_version
        self.is_active = True
        self.is_admin = False
        self.is_superuser = False


class _Query:
    def __init__(self, result):
        self._result = result

    def filter(self, *_, **__):
        return self

    def first(self):
        return self._result


class _StubSession:
    def __init__(self, user):
        self._user = user
        self.committed_token_version = None

    def query(self, _model):
        return _Query(self._user)

    def commit(self):
        if self._user is not None:
            self.committed_token_version = int(
                getattr(self._user, "token_version", 0) or 0
            )


class _FakeRequest:
    def __init__(self, token: str):
        self.headers = {"authorization": f"Bearer {token}"} if token else {}


@pytest.fixture(autouse=True)
def _isolate_blacklist(monkeypatch):
    """Reset the in-memory blacklist and force Redis off for every test."""
    monkeypatch.delenv("REDIS_ENABLED", raising=False)
    TokenBlacklist._fallback_tokens = set()
    TokenBlacklist._redis_client = None
    TokenBlacklist._redis_initialised = False
    yield
    TokenBlacklist._fallback_tokens = set()
    TokenBlacklist._redis_client = None
    TokenBlacklist._redis_initialised = False


def _make_token(sub: str = "alice", stv: Any = 0) -> str:
    claims = {"sub": sub}
    if stv is not None:
        claims["stv"] = stv
    return JWTUtils.create_access_token(claims)


def test_logout_blacklists_presented_token(monkeypatch):
    import asyncio
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    token = _make_token("alice", stv=0)

    user = _StubUser("alice", token_version=0)
    response = asyncio.run(auth_router.logout(
        request=_FakeRequest(token),
        current_user=user,
    ))

    assert response == {"message": "Logged out"}

    # The same token must now be rejected at the verify choke point.
    session = _StubSession(_StubUser("alice", token_version=0))
    with pytest.raises(AuthenticationError):
        authenticate_bearer_token(token, cast(Any, session))


def test_logout_all_bumps_version_and_invalidates_prior_tokens(monkeypatch):
    import asyncio
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    old_token = _make_token("alice", stv=0)

    user = _StubUser("alice", token_version=0)
    session = _StubSession(user)

    # Pre-condition: the old token currently authenticates.
    authenticate_bearer_token(old_token, cast(Any, _StubSession(_StubUser("alice", 0))))

    response = asyncio.run(auth_router.logout_all(
        request=_FakeRequest(old_token),
        current_user=user,
        session=session,
    ))

    assert response["message"] == "Logged out from all sessions"
    assert response["token_version"] == 1
    assert user.token_version == 1
    assert session.committed_token_version == 1

    # Old token (stv=0) is now rejected because the user is on version 1.
    with pytest.raises(AuthenticationError):
        authenticate_bearer_token(
            old_token, cast(Any, _StubSession(_StubUser("alice", 1)))
        )

    # A freshly minted token carrying the new stamp still authenticates.
    fresh = _make_token("alice", stv=1)
    authenticate_bearer_token(fresh, cast(Any, _StubSession(_StubUser("alice", 1))))


def test_legacy_token_without_stv_works_against_version_zero(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    legacy = _make_token("bob", stv=None)  # no stv claim at all

    decoded = JWTUtils.decode_token(legacy)
    assert "stv" not in decoded

    # Treated as version 0 -> matches a user still on version 0.
    user = authenticate_bearer_token(
        legacy, cast(Any, _StubSession(_StubUser("bob", 0)))
    )
    assert user.username == "bob"


def test_logout_in_bypass_mode_is_noop(monkeypatch):
    import asyncio
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")

    token = _make_token("alice", stv=0)
    response = asyncio.run(auth_router.logout(
        request=_FakeRequest(token),
        current_user=_StubUser("alice", 0),
    ))

    assert response == {"message": "Logged out"}

    # Blacklist untouched -> token still verifies through the JWT layer.
    assert TokenBlacklist.is_token_blacklisted(JWTUtils.get_token_jti(token)) is False


def test_logout_returns_rotation_message_for_service_token_principal(monkeypatch):
    import asyncio
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)

    # Service-token stand-ins expose no token_version.
    class _ServicePrincipal:
        username = "backend-service-token"
        is_active = True
        is_admin = True
        is_superuser = True

    token = _make_token("backend-service-token", stv=0)
    response = asyncio.run(auth_router.logout(
        request=_FakeRequest(token),
        current_user=_ServicePrincipal(),
    ))

    assert "rotated via environment" in response["message"]
    # JTI was not blacklisted.
    assert TokenBlacklist.is_token_blacklisted(JWTUtils.get_token_jti(token)) is False


def test_build_token_response_embeds_security_stamp():
    payload = auth_router._build_token_response("alice", token_version=3)

    decoded = JWTUtils.decode_token(payload["access_token"])
    assert decoded["sub"] == "alice"
    assert decoded["stv"] == 3
    assert decoded["type"] == "access"

    refresh = JWTUtils.decode_token(payload["refresh_token"])
    assert refresh["stv"] == 3
    assert refresh["type"] == "refresh"


def test_revoke_presented_token_uses_remaining_lifetime():
    token = _make_token("alice", stv=0)
    decoded = JWTUtils.decode_token(token)
    jti = decoded["jti"]
    exp = datetime.fromtimestamp(int(decoded["exp"]), tz=timezone.utc)

    auth_router._revoke_presented_token(token)

    assert TokenBlacklist.is_token_blacklisted(jti) is True
    # Sanity: expiry used for blacklisting is the token's own exp.
    assert exp > datetime.now(tz=timezone.utc)
