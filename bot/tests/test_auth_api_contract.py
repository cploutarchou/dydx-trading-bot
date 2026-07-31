"""Auth contract tests to lock token response shape for backend/frontend integrations."""

import asyncio
import importlib

AUTH_TOKEN_KEYS = {"access_token", "refresh_token", "token_type", "expires_in"}


def _load_auth_module():
    return importlib.import_module("src.api.v1.auth")


def test_build_token_response_shape_is_stable(monkeypatch):
    auth = _load_auth_module()

    monkeypatch.setattr(
        auth.JWTUtils, "create_access_token", lambda _payload: "acc-token"
    )
    monkeypatch.setattr(
        auth.JWTUtils, "create_refresh_token", lambda _payload: "ref-token"
    )

    payload = auth._build_token_response("svc-user")

    assert set(payload.keys()) == AUTH_TOKEN_KEYS
    assert payload["access_token"] == "acc-token"
    assert payload["refresh_token"] == "ref-token"
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["expires_in"], int)


def test_login_bypass_returns_only_token_contract_fields(monkeypatch):
    auth = _load_auth_module()

    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    monkeypatch.setattr(
        auth.JWTUtils, "create_access_token", lambda _payload: "acc-token"
    )
    monkeypatch.setattr(
        auth.JWTUtils, "create_refresh_token", lambda _payload: "ref-token"
    )

    payload = asyncio.run(
        auth.login(auth.LoginRequest(username="bot", password="x"), session=None)
    )

    assert set(payload.keys()) == AUTH_TOKEN_KEYS
    assert payload["token_type"] == "bearer"
