"""Tests for the extracted monitoring route module (monolith-breakup Phase 1).

The monitoring endpoints were moved from ``src/api/server.py`` into
``src/api/v1/monitoring.py`` (an ``APIRouter`` mounted via ``app.include_router``).
FastAPI 0.138+ wraps included routers lazily as ``_IncludedRouter``, so these routes
are NOT materialized in ``app.routes`` — they are verified here via the live
``TestClient`` (reachability + auth + envelope) and via the router's own route table.
"""

from types import SimpleNamespace

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import src.api.responses as responses
import src.api.server as server
from src.api.v1.monitoring import router as monitoring_router
from src.middleware.auth_middleware import get_current_active_user

_MONITORING_PATHS = [
    "/api/v1/monitoring/dataframe/memory",
    "/api/v1/monitoring/database/pool",
    "/api/v1/monitoring/database/pool/health",
    "/api/v1/monitoring/database/diagnostics",
]


# --------------------------------------------------------------------------- #
# Re-export identity (the prerequisite extraction)
# --------------------------------------------------------------------------- #


def test_response_helpers_reexport_identity():
    """server.py must re-export the same objects that now live in responses.py."""
    assert server.api_response is responses.api_response
    assert server.trace_id_ctx is responses.trace_id_ctx
    assert server.INTERNAL_ERROR_MESSAGE == responses.INTERNAL_ERROR_MESSAGE


# --------------------------------------------------------------------------- #
# Router shape
# --------------------------------------------------------------------------- #


def test_monitoring_router_has_six_routes_all_with_auth():
    routes = [r for r in monitoring_router.routes if isinstance(r, APIRoute)]
    assert len(routes) == 6
    for route in routes:
        deps = [d.call for d in route.dependant.dependencies]
        assert (
            get_current_active_user in deps
        ), f"{route.path} missing get_current_active_user dependency"
        assert route.path.startswith("/api/v1/monitoring/")


# --------------------------------------------------------------------------- #
# Runtime behaviour via TestClient
# --------------------------------------------------------------------------- #


def _bypass_auth(monkeypatch):
    """Override the auth dependency so we can exercise the route bodies.

    Uses ``monkeypatch.setitem`` so the override is auto-restored on teardown.
    """
    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        lambda: SimpleNamespace(is_active=True),
    )


def test_monitoring_routes_return_envelope_when_authenticated(monkeypatch):
    _bypass_auth(monkeypatch)
    monkeypatch.setattr(
        server.db, "get_pool_metrics", lambda: {"checked_out": 1, "size": 5}
    )
    monkeypatch.setattr(server.db, "get_pool_health_status", lambda: {"healthy": True})
    monkeypatch.setattr(server.db, "get_diagnostics", lambda: {"ok": True})

    client = TestClient(server.app, raise_server_exceptions=False)
    for path in _MONITORING_PATHS:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
        body = resp.json()
        assert body["success"] is True
        assert "trace_id" in body  # envelope preserved


def test_monitoring_routes_require_auth(monkeypatch):
    """No credentials → 401 (auth dep is enforced on the extracted routes)."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    server.app.dependency_overrides.pop(get_current_active_user, None)
    client = TestClient(server.app, raise_server_exceptions=False)
    for path in _MONITORING_PATHS:
        resp = client.get(path)
        assert (
            resp.status_code == 401
        ), f"{path} returned {resp.status_code} (expected 401)"


def test_monitoring_pool_history_clamps_limit(monkeypatch):
    """The history route clamps ``limit`` into [1, 500] before hitting the DB."""
    captured: dict = {}

    def _fake_history(limit=50):
        captured["limit"] = limit
        return [{"t": 1}]

    _bypass_auth(monkeypatch)
    monkeypatch.setattr(server.db, "get_pool_metrics_history", _fake_history)
    client = TestClient(server.app, raise_server_exceptions=False)

    resp = client.get(
        "/api/v1/monitoring/database/pool/history", params={"limit": 99999}
    )
    assert resp.status_code == 200
    assert captured["limit"] == 500  # clamped to the max
