import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute

from src.api import server
from src.infrastructure.domain.models.auth_models import User
from src.middleware import auth_middleware


class _Dumpable:
    def __init__(self, payload):
        self._payload = payload
        for key, value in payload.items():
            setattr(self, key, value)

    def model_dump(self):
        return dict(self._payload)


class _RunResult:
    def __init__(self, payload):
        self._payload = payload
        self.name = payload.get("name", "auth-test")

    def model_dump(self):
        return dict(self._payload)


class _BacktestService:
    def list_backtest_runs(self, **_kwargs):
        return _Dumpable({"runs": [], "total": 0})

    def list_interrupted_runs_for_ops(self, limit=50):
        return {
            "interrupted_runs": [],
            "orphaned_in_progress": [],
            "interrupted_count": 0,
            "orphaned_count": 0,
            "limit": limit,
        }

    def get_runtime_health(self):
        return {"queue_depth": 0, "active_jobs": 0}

    async def create_and_run_backtest(self, request, _progress_callback=None):
        return _RunResult(
            {
                "run_id": "run-auth",
                "name": getattr(request, "name", None) or "auth-test",
                "status": "pending",
                "progress_pct": 0.0,
            }
        )

    def get_backtest_status(self, run_id):
        return _Dumpable(
            {
                "run_id": run_id,
                "status": "running",
                "progress_pct": 50.0,
                "request_available": True,
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )

    def cancel_backtest(self, _run_id):
        return True

    def pause_backtest(self, run_id):
        return {"run_id": run_id, "status": "paused"}

    def resume_backtest(self, run_id):
        return {"run_id": run_id, "status": "running"}

    async def restart_backtest(self, run_id, _progress_callback=None):
        return {"new_run_id": f"{run_id}-restart"}

    def delete_backtest(self, _run_id):
        return True

    def get_backtest_details(self, run_id):
        return _Dumpable({"run_id": run_id, "status": "running"})


class _DummySession:
    def close(self):
        return None


def _user(is_admin: bool = False):
    return SimpleNamespace(
        username="tester",
        is_active=True,
        is_admin=is_admin,
        is_superuser=is_admin,
    )


def _route(path: str, method: str) -> APIRoute:
    for route in server.app.routes:
        if (
            isinstance(route, APIRoute)
            and route.path == path
            and method in route.methods
        ):
            return route
    raise AssertionError(f"Route not found for {method} {path}")


@contextmanager
def _fake_backtest_scope():
    yield _BacktestService()


def test_backtest_routes_declare_executable_auth_dependencies():
    protected_routes = [
        ("/api/v1/backtests", "GET"),
        ("/api/v1/backtests", "POST"),
        ("/api/v1/backtests/{run_id}", "GET"),
        ("/api/v1/backtests/{run_id}/cancel", "POST"),
        ("/api/v1/backtests/{run_id}/pause", "POST"),
        ("/api/v1/backtests/{run_id}/resume", "POST"),
        ("/api/v1/backtests/{run_id}/restart", "POST"),
        ("/api/v1/backtests/{run_id}", "DELETE"),
    ]

    for path, method in protected_routes:
        route = _route(path, method)
        dependency_calls = [
            dependency.call for dependency in route.dependant.dependencies
        ]
        assert server.get_current_active_user in dependency_calls


def test_admin_backtest_routes_declare_admin_dependency():
    admin_routes = [
        ("/api/v1/admin/backtests/interrupted", "GET"),
        ("/api/v1/admin/backtests/interrupted/reconcile", "POST"),
        ("/api/v1/admin/backtests/{run_id}/repair-request", "POST"),
    ]

    for path, method in admin_routes:
        route = _route(path, method)
        dependency_calls = [
            dependency.call for dependency in route.dependant.dependencies
        ]
        assert server.get_admin_user in dependency_calls


def test_auth_dependencies_reject_unauthenticated_and_non_admin_users():
    with pytest.raises(Exception) as unauthenticated:
        asyncio.run(
            auth_middleware.get_current_user(
                credentials=None,
                session=_DummySession(),
            )
        )
    assert getattr(unauthenticated.value, "status_code", None) == 401

    with pytest.raises(Exception) as non_admin:
        asyncio.run(auth_middleware.get_admin_user(current_user=_user(False)))
    assert getattr(non_admin.value, "status_code", None) == 403


def test_authenticated_normal_user_can_access_allowed_backtest_handlers(monkeypatch):
    async def _resolve_markets(*_args, **_kwargs):
        return ["BTC-USD", "ETH-USD"]

    monkeypatch.setattr(
        server,
        "_list_backtests_sync",
        lambda *_args, **_kwargs: _Dumpable({"runs": [], "total": 0}),
    )
    monkeypatch.setattr(server, "_resolve_backtest_markets", _resolve_markets)
    monkeypatch.setattr(server, "backtest_service_scope", _fake_backtest_scope)

    list_response = asyncio.run(server.list_backtests(current_user=_user(False)))
    create_response = asyncio.run(
        server.run_backtest_compat(
            server.BacktestRunRequestCompat(
                start_date="2026-01-01",
                end_date="2026-01-02",
                pairs=["BTC-USD", "ETH-USD"],
                trading_parameters={"zscore_threshold": 1.5},
            ),
            current_user=_user(False),
        )
    )

    assert list_response.status_code == 200
    assert create_response.status_code == 200


def test_admin_user_can_access_admin_backtest_handlers(monkeypatch):
    monkeypatch.setattr(
        server,
        "_list_interrupted_backtests_response",
        lambda limit=50: server.api_response(
            success=True,
            data={"limit": limit},
            message="ok",
        ),
    )

    response = asyncio.run(
        server.list_interrupted_backtests_admin(current_user=_user(True))
    )
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["success"] is True


def test_backtest_openapi_security_matches_route_auth_requirement():
    server.app.openapi_schema = None
    schema = server.app.openapi()

    assert schema["paths"]["/api/v1/backtests"]["get"]["security"] == [
        {"BearerAuth": []}
    ]
    assert schema["paths"]["/api/v1/backtests"]["post"]["security"] == [
        {"BearerAuth": []}
    ]
    assert schema["paths"]["/api/v1/admin/backtests/interrupted"]["get"][
        "security"
    ] == [{"BearerAuth": []}]
