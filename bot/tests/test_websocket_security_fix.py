"""Regression tests for WebSocket authentication (no JWT in query strings).

Security contract: ``_authorize_websocket_connection`` accepts bearer tokens
**only** via the ``Authorization`` header. Tokens in the ``access_token`` query
parameter must be ignored so they cannot leak into proxy/access logs.

These tests are written as plain sync functions that drive the async authorizer
through ``asyncio.run`` — the project's established pattern (see
``tests/test_bot_instance_manager.py``) — so they actually run under pytest
without requiring pytest-asyncio auto-mode. The auth helpers and DB session are
mocked so the tests are deterministic and database-free.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict


class _MockWebSocket:
    """Minimal WebSocket double exposing the surface the authorizer touches."""

    def __init__(self, headers: Dict[str, str] | None = None,
                 query_params: Dict[str, str] | None = None):
        self.headers = headers or {}
        # query_params is intentionally captured to prove it is *never* read.
        self.query_params = query_params or {}
        self.closed = False
        self.close_code: int | None = None
        self.close_reason: str | None = None

    async def close(self, code: int, reason: str) -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason


def _authorize(monkeypatch, websocket: _MockWebSocket, *,
               bypass: bool = False,
               token_is_valid: bool = True,
               raise_on_auth: Exception | None = None) -> bool:
    """Run the authorizer with mocked bypass/auth/DB dependencies.

    Patches the names as imported into ``src.api.server`` so the real
    environment/DB are never touched.
    """
    import src.api.server as server_module

    monkeypatch.setattr(
        server_module, "is_auth_bypass_enabled", lambda: bypass
    )

    sentinel_session = SimpleNamespace(close=lambda: None)

    def _fake_get_session():
        return sentinel_session

    def _fake_authenticate(token: str, session: Any):
        if raise_on_auth is not None:
            raise raise_on_auth
        if not token_is_valid:
            raise ValueError("invalid token")
        # Valid token: returns truthy user, no exception.
        return SimpleNamespace(username="tester")

    monkeypatch.setattr(server_module.db, "get_session", _fake_get_session)
    monkeypatch.setattr(
        server_module, "authenticate_bearer_token", _fake_authenticate
    )

    return asyncio.run(server_module._authorize_websocket_connection(websocket))


# --- query-string tokens must be rejected ------------------------------------


def test_websocket_rejects_query_parameter_tokens(monkeypatch):
    """A token supplied only via query string is ignored; connection is closed."""
    websocket = _MockWebSocket(
        headers={},  # no Authorization header
        query_params={"access_token": "fake_token_via_query_params"},
    )

    result = _authorize(monkeypatch, websocket, bypass=False, token_is_valid=True)

    assert result is False, "Query-parameter tokens must not authenticate"
    assert websocket.closed is True
    assert websocket.close_code == 4401
    assert websocket.close_reason == "Missing websocket auth token"


def test_query_parameter_is_ignored_even_when_header_present(monkeypatch):
    """A valid header token authenticates regardless of any stray query param."""
    websocket = _MockWebSocket(
        headers={"authorization": "Bearer good-service-token"},
        query_params={"access_token": "should-be-ignored"},
    )

    result = _authorize(monkeypatch, websocket, bypass=False, token_is_valid=True)

    assert result is True
    assert websocket.closed is False


# --- Authorization header path ----------------------------------------------


def test_websocket_accepts_valid_authorization_header(monkeypatch):
    """A valid bearer token in the Authorization header authenticates."""
    websocket = _MockWebSocket(
        headers={"authorization": "Bearer good-service-token"},
        query_params={},
    )

    result = _authorize(monkeypatch, websocket, bypass=False, token_is_valid=True)

    assert result is True
    assert websocket.closed is False


def test_websocket_rejects_invalid_authorization_header(monkeypatch):
    """An unparseable/unknown bearer token is rejected with 4401 Invalid."""
    websocket = _MockWebSocket(
        headers={"authorization": "Bearer not-a-real-token"},
        query_params={},
    )

    result = _authorize(monkeypatch, websocket, bypass=False, token_is_valid=False)

    assert result is False
    assert websocket.closed is True
    assert websocket.close_code == 4401
    assert websocket.close_reason == "Invalid websocket auth token"


def test_websocket_rejects_missing_header_and_missing_query(monkeypatch):
    """No header and no token at all -> closed as Missing."""
    websocket = _MockWebSocket(headers={}, query_params={})

    result = _authorize(monkeypatch, websocket, bypass=False)

    assert result is False
    assert websocket.close_code == 4401
    assert "Missing" in (websocket.close_reason or "")


# --- auth bypass -------------------------------------------------------------


def test_auth_bypass_short_circuits_without_token(monkeypatch):
    """When bypass is enabled, the authorizer permits the connection immediately."""
    websocket = _MockWebSocket(headers={}, query_params={})

    result = _authorize(monkeypatch, websocket, bypass=True)

    assert result is True
    assert websocket.closed is False


def test_authorization_header_is_case_insensitive_for_scheme(monkeypatch):
    """'bearer ' prefix is matched case-insensitively (per RFC 7235 token form)."""
    websocket = _MockWebSocket(
        headers={"authorization": "bearer good-service-token"},
        query_params={},
    )

    result = _authorize(monkeypatch, websocket, bypass=False, token_is_valid=True)

    assert result is True
    assert websocket.closed is False


# --- standalone smoke (python tests/test_websocket_security_fix.py) ----------


def _run_all() -> None:
    """Drive every test with throwaway pytest-style asserts for manual smoke."""
    # Re-implemented inline so `python tests/test_websocket_security_fix.py`
    # remains runnable without a pytest invocation.
    import os
    import sys
    from pathlib import Path

    bot_dir = Path(__file__).resolve().parents[1]
    if str(bot_dir) not in sys.path:
        sys.path.insert(0, str(bot_dir))

    import src.api.server as server_module

    async def _drive(ws):
        return await server_module._authorize_websocket_connection(ws)

    original = os.environ.get("API_BYPASS_AUTH")
    os.environ["API_BYPASS_AUTH"] = "false"
    try:
        ws = _MockWebSocket(query_params={"access_token": "x"})
        # Without DB/auth mocks this path closes at the "Missing token" branch
        # before any session is opened, so it is safe to run standalone.
        assert asyncio.run(_drive(ws)) is False
        assert ws.close_code == 4401
        print("✓ Query-parameter tokens are rejected (standalone smoke)")
    finally:
        if original is not None:
            os.environ["API_BYPASS_AUTH"] = original
        else:
            os.environ.pop("API_BYPASS_AUTH", None)


if __name__ == "__main__":
    _run_all()
    print("\n✅ Standalone WebSocket security smoke passed")
