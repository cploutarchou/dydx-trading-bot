"""Tests for the extracted Celery admin route module (monolith-breakup Phase 2).

The 7 ``/api/v1/celery/*`` endpoints were moved from ``src/api/server.py`` into
``src/api/v1/celery_admin.py`` (an ``APIRouter`` mounted via ``app.include_router``).
They are admin-only (``get_admin_user``). FastAPI 0.138+ wraps included routers lazily
as ``_IncludedRouter``, so reachability is verified via the live ``TestClient`` rather
than ``app.routes`` introspection. Admin enforcement is tested by overriding the inner
``get_current_active_user`` dependency so the *real* ``get_admin_user`` runs its
``is_admin`` check.
"""

from types import SimpleNamespace

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import src.api.endpoint_timing as endpoint_timing
import src.api.server as server
from src.api.v1.celery_admin import router as celery_router
from src.middleware.auth_middleware import get_admin_user, get_current_active_user

_CELERY_PATHS = [
    ("GET", "/api/v1/celery/tasks"),
    ("GET", "/api/v1/celery/workers"),
    ("GET", "/api/v1/celery/queues"),
    ("GET", "/api/v1/celery/health"),
]


# --------------------------------------------------------------------------- #
# Prerequisite extraction identity
# --------------------------------------------------------------------------- #


def test_endpoint_timing_helpers_reexport_identity():
    """server.py aliases the shared timing helpers to the same callables."""
    assert server._log_endpoint_timing is endpoint_timing.log_endpoint_timing
    assert server._endpoint_perf_headers is endpoint_timing.endpoint_perf_headers
    assert server._payload_size_bytes is endpoint_timing.payload_size_bytes


# --------------------------------------------------------------------------- #
# Router shape
# --------------------------------------------------------------------------- #


def test_celery_router_has_seven_admin_routes():
    routes = [r for r in celery_router.routes if isinstance(r, APIRoute)]
    assert len(routes) == 7
    for route in routes:
        deps = [d.call for d in route.dependant.dependencies]
        assert get_admin_user in deps, f"{route.path} missing get_admin_user"
        assert route.path.startswith("/api/v1/celery/")


# --------------------------------------------------------------------------- #
# Runtime behaviour via TestClient
# --------------------------------------------------------------------------- #


def test_celery_routes_require_auth(monkeypatch):
    """No credentials → 401."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    server.app.dependency_overrides.pop(get_current_active_user, None)
    server.app.dependency_overrides.pop(get_admin_user, None)
    client = TestClient(server.app, raise_server_exceptions=False)
    for _, path in _CELERY_PATHS:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} returned {resp.status_code}"


def test_celery_routes_reject_non_admin(monkeypatch):
    """Authenticated but non-admin → 403 (real get_admin_user enforces is_admin)."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    # Override the INNER dep so the real get_admin_user still runs its is_admin check.
    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        lambda: SimpleNamespace(is_active=True, is_admin=False),
    )
    server.app.dependency_overrides.pop(get_admin_user, None)
    client = TestClient(server.app, raise_server_exceptions=False)
    for _, path in _CELERY_PATHS:
        resp = client.get(path)
        assert resp.status_code == 403, f"{path} returned {resp.status_code}"


def test_celery_health_returns_envelope_for_admin(monkeypatch):
    """Admin user → 200 with the standardized envelope."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        lambda: SimpleNamespace(is_active=True, is_admin=True),
    )
    server.app.dependency_overrides.pop(get_admin_user, None)
    monkeypatch.setattr(
        "src.api.v1.celery_admin.celery_health", lambda: {"broker": "ok"}
    )
    client = TestClient(server.app, raise_server_exceptions=False)
    resp = client.get("/api/v1/celery/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == {"broker": "ok"}
    assert "trace_id" in body
    # timing header emitted by the route
    assert "X-Endpoint-Duration-Ms" in resp.headers


def test_celery_task_detail_404_when_missing(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        lambda: SimpleNamespace(is_active=True, is_admin=True),
    )
    server.app.dependency_overrides.pop(get_admin_user, None)
    monkeypatch.setattr("src.api.v1.celery_admin.get_celery_task", lambda _tid: None)
    client = TestClient(server.app, raise_server_exceptions=False)
    resp = client.get("/api/v1/celery/tasks/nope")
    assert resp.status_code == 404
