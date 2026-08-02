"""Tests for the extracted strategies route module (monolith-breakup Phase 3).

The 8 ``/api/v1/strategies/*`` endpoints (+ ``StrategyRequest`` /
``StrategyVersionRevertRequest`` / ``InMemoryStrategyStore``) were moved from
``src/api/server.py`` into ``src/api/v1/strategies.py``. ``list_public_strategies``
is intentionally unauthenticated (public catalog); the other 7 require auth.
FastAPI 0.138+ lazy ``_IncludedRouter`` means reachability is verified via the live
``TestClient``, not ``app.routes`` introspection.
"""

from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import src.api.server as server
import src.api.v1.strategies as strategies_module
from src.api.v1.strategies import router as strategies_router
from src.middleware.auth_middleware import get_current_active_user

_VALID_STRATEGY = {
    "name": "Test Strategy",
    "zscore_threshold": 1.5,
    "usd_per_trade": 10.0,
}


# --------------------------------------------------------------------------- #
# Re-export identity
# --------------------------------------------------------------------------- #


def test_strategy_names_reexport_identity():
    """server.py re-imports the moved strategy names (same objects)."""
    assert server.StrategyRequest is strategies_module.StrategyRequest
    assert server.InMemoryStrategyStore is strategies_module.InMemoryStrategyStore
    assert (
        server.StrategyVersionRevertRequest
        is strategies_module.StrategyVersionRevertRequest
    )


# --------------------------------------------------------------------------- #
# Router shape
# --------------------------------------------------------------------------- #


def test_strategies_router_has_eight_routes():
    routes = [r for r in strategies_router.routes if isinstance(r, APIRoute)]
    assert len(routes) == 8
    # The /public route is the only one WITHOUT the auth dependency.
    authed = [
        r
        for r in routes
        if get_current_active_user in [d.call for d in r.dependant.dependencies]
    ]
    assert len(authed) == 7
    public = [r for r in routes if "/public" in r.path]
    assert len(public) == 1
    assert get_current_active_user not in [
        d.call for d in public[0].dependant.dependencies
    ]


# --------------------------------------------------------------------------- #
# Runtime behaviour via TestClient
# --------------------------------------------------------------------------- #


@pytest.fixture
def authed_client(monkeypatch):
    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        lambda: SimpleNamespace(is_active=True),
    )
    return TestClient(server.app, raise_server_exceptions=False)


def test_protected_strategy_routes_require_auth(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    server.app.dependency_overrides.pop(get_current_active_user, None)
    client = TestClient(server.app, raise_server_exceptions=False)
    for path in [
        "/api/v1/strategies",
        "/api/v1/strategies/1",
        "/api/v1/strategies/1/versions",
    ]:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} returned {resp.status_code}"


def test_public_strategies_route_does_not_require_auth(monkeypatch):
    """The /public catalog is reachable without credentials."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    server.app.dependency_overrides.pop(get_current_active_user, None)
    monkeypatch.setattr(
        strategies_module.InMemoryStrategyStore,
        "list_public",
        lambda: {"strategies": []},
    )
    client = TestClient(server.app, raise_server_exceptions=False)
    resp = client.get("/api/v1/strategies/public")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_get_strategy_404_when_missing(authed_client, monkeypatch):
    monkeypatch.setattr(
        strategies_module.InMemoryStrategyStore, "get", lambda _sid: None
    )
    resp = authed_client.get("/api/v1/strategies/999")
    assert resp.status_code == 404


def test_create_then_get_strategy_roundtrip(authed_client, monkeypatch):
    created = {"id": 7, "name": "Test Strategy", **_VALID_STRATEGY}

    monkeypatch.setattr(
        strategies_module.InMemoryStrategyStore, "create", lambda _payload: created
    )
    resp = authed_client.post("/api/v1/strategies", json=_VALID_STRATEGY)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == 7

    monkeypatch.setattr(
        strategies_module.InMemoryStrategyStore, "get", lambda _sid: created
    )
    resp = authed_client.get("/api/v1/strategies/7")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Test Strategy"


def test_delete_strategy_404_when_missing(authed_client, monkeypatch):
    monkeypatch.setattr(
        strategies_module.InMemoryStrategyStore, "delete", lambda _sid: False
    )
    resp = authed_client.delete("/api/v1/strategies/999")
    assert resp.status_code == 404


def test_create_strategy_rejects_invalid_payload(authed_client):
    """Input-validation constraints (gt=0 etc.) still apply on the extracted route."""
    resp = authed_client.post(
        "/api/v1/strategies", json={**_VALID_STRATEGY, "usd_per_trade": -5.0}
    )
    assert resp.status_code == 422
