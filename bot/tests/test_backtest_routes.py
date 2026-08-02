"""Extraction contracts for the Phase 6 backtest API router."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute

import src.api.server as server
import src.api.v1.backtests as backtests

HTTP_OPERATIONS = {
    ("POST", "/api/v1/backtests"),
    ("POST", "/api/v1/backtests/run"),
    ("GET", "/api/v1/backtests"),
    ("GET", "/api/v1/backtests/interrupted"),
    ("POST", "/api/v1/backtests/interrupted/reconcile"),
    ("GET", "/api/v1/admin/backtests/interrupted"),
    ("POST", "/api/v1/admin/backtests/interrupted/reconcile"),
    ("POST", "/api/v1/admin/backtests/{run_id}/repair-request"),
    ("GET", "/api/v1/backtests/{run_id}"),
    ("GET", "/api/v1/backtests/{run_id}/status"),
    ("POST", "/api/v1/backtests/{run_id}/metadata"),
    ("GET", "/api/v1/backtests/{run_id}/websocket-metrics"),
    ("POST", "/api/v1/backtests/{run_id}/create-strategy"),
    ("GET", "/api/v1/backtests/{run_id}/trades"),
    ("GET", "/api/v1/backtests/{run_id}/logs"),
    ("POST", "/api/v1/backtests/{run_id}/cancel"),
    ("POST", "/api/v1/backtests/{run_id}/pause"),
    ("POST", "/api/v1/backtests/{run_id}/resume"),
    ("POST", "/api/v1/backtests/{run_id}/restart"),
    ("POST", "/api/v1/backtests/{run_id}/retry"),
    ("DELETE", "/api/v1/backtests/{run_id}"),
    ("GET", "/api/v1/backtests/stats/summary"),
    ("GET", "/api/v1/backtests/{run_id}/analytics"),
    ("GET", "/api/v1/backtests/{run_id}/analytics/summary"),
    ("GET", "/api/v1/backtests/{run_id}/position-snapshots"),
    ("POST", "/api/v1/backtests/compare"),
    ("GET", "/api/v1/backtests/sync-health"),
    ("GET", "/api/v1/backtests/{run_id}/dydx-validation"),
    ("GET", "/api/v1/backtests/{run_id}/performance-metrics"),
    ("GET", "/api/v1/backtests/{run_id}/live-progress"),
}

WEBSOCKET_PATHS = {
    "/api/v1/backtests/{run_id}/live",
    "/ws/backtests/{run_id}",
}

ADMIN_PATHS = {
    "/api/v1/admin/backtests/interrupted",
    "/api/v1/admin/backtests/interrupted/reconcile",
    "/api/v1/admin/backtests/{run_id}/repair-request",
}


def _router_http_operations():
    return {
        (method, route.path)
        for route in backtests.router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }


def test_router_owns_exact_backtest_surface():
    assert _router_http_operations() == HTTP_OPERATIONS
    assert {
        route.path
        for route in backtests.router.routes
        if isinstance(route, APIWebSocketRoute)
    } == WEBSOCKET_PATHS


def test_all_backtest_http_routes_keep_executable_auth_dependencies():
    for route in backtests.router.routes:
        if not isinstance(route, APIRoute):
            continue
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        expected = (
            server.get_admin_user
            if route.path in ADMIN_PATHS
            else server.get_current_active_user
        )
        assert expected in dependency_calls, route.path


def test_server_mounts_router_once_without_direct_backtest_routes():
    mounts = [
        route
        for route in server.app.routes
        if type(route).__name__ == "_IncludedRouter"
        and getattr(route, "original_router", None) is backtests.router
    ]
    assert len(mounts) == 1
    assert not any(
        isinstance(route, (APIRoute, APIWebSocketRoute)) and "backtest" in route.path
        for route in server.app.routes
    )


@pytest.mark.parametrize(
    "name",
    [
        "BacktestRunRequestCompat",
        "BacktestComparisonRequest",
        "backtest_service_scope",
        "_resolve_backtest_markets",
        "_resolve_strategy_backtest_request",
        "create_backtest",
        "run_backtest_compat",
        "list_backtests",
        "get_backtest_status",
        "websocket_backtest_progress",
        "websocket_backtest_progress_alias",
    ],
)
def test_server_preserves_backtest_reexport_identity(name):
    assert getattr(server, name) is getattr(backtests, name)


@pytest.mark.parametrize(
    ("handler_name", "expected_channel"),
    [
        ("websocket_backtest_progress", "backtest-run-42"),
        ("websocket_backtest_progress_alias", "backtest-run-42"),
    ],
)
def test_websocket_adapters_authorize_and_delegate(
    monkeypatch,
    handler_name,
    expected_channel,
):
    websocket = object()
    calls = []

    async def authorize(candidate):
        calls.append(("authorize", candidate))
        return True

    async def handle_connection(candidate, channel):
        calls.append(("delegate", candidate, channel))

    monkeypatch.setattr(backtests, "_websocket_authorizer", authorize)
    monkeypatch.setattr(
        backtests.WebSocketServer,
        "handle_connection",
        handle_connection,
    )

    asyncio.run(getattr(backtests, handler_name)(websocket, "run-42"))

    assert calls == [
        ("authorize", websocket),
        ("delegate", websocket, expected_channel),
    ]


def test_websocket_adapter_fails_closed_before_delegation(monkeypatch):
    async def deny(_websocket):
        return False

    async def unexpected_delegate(*_args):
        raise AssertionError("unauthorized websocket reached the handler")

    monkeypatch.setattr(backtests, "_websocket_authorizer", deny)
    monkeypatch.setattr(
        backtests.WebSocketServer,
        "handle_connection",
        unexpected_delegate,
    )

    asyncio.run(backtests.websocket_backtest_progress(object(), "run-42"))


def test_capabilities_and_openapi_include_every_extracted_contract():
    schema = server.app.openapi()
    for method, path in HTTP_OPERATIONS:
        assert method.lower() in schema["paths"][path]

    response = asyncio.run(server.api_capabilities())
    payload = json.loads(response.body)["data"]
    capability_operations = {
        f"{method} {path}"
        for method, path in HTTP_OPERATIONS
        if path not in ADMIN_PATHS
    }
    assert capability_operations.issubset(payload["http_endpoints"])
    assert {f"WS {path}" for path in WEBSOCKET_PATHS}.issubset(
        payload["websocket_channels"]
    )
