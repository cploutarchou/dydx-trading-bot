"""Contracts for the extracted bot lifecycle router (API breakup Phase 5a)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException, Request
from fastapi.routing import APIRoute

import src.api.server as server
import src.api.v1.bot_lifecycle as lifecycle
from src.infrastructure.domain.bot_api_models import (
    BotInstanceStatus,
    BotOperationResult,
    BotStatus,
)
from src.middleware.auth_middleware import get_admin_user, get_current_active_user

_CREATE_PAYLOAD = {
    "instance_id": "bot-flow-1",
    "instance_name": "Lifecycle Flow",
    "credentials": {
        "address": "dydx1testaddress",
        "mnemonic": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
    },
    "trading_params": {
        "place_trades": False,
        "selected_markets": ["BTC-USD", "ETH-USD"],
    },
}

_LIFECYCLE_OPERATIONS = {
    ("POST", "/api/v1/bots"),
    ("GET", "/api/v1/bots"),
    ("GET", "/api/v1/bots/{instance_id}"),
    ("DELETE", "/api/v1/bots/{instance_id}"),
    ("POST", "/api/v1/bots/{instance_id}/start"),
    ("POST", "/api/v1/bots/{instance_id}/stop"),
    ("POST", "/api/v1/bots/{instance_id}/restart"),
    ("POST", "/api/v1/bots/quick-deploy"),
}


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, **kwargs)


@pytest.fixture
def authed_app(monkeypatch):
    async def _active_user():
        return SimpleNamespace(
            is_active=True,
            is_admin=True,
            username="operator",
            email="operator@example.test",
        )

    async def _rate_limit(request: Request):
        lifecycle._instance_rate_limiter(request)

    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        _active_user,
    )
    # The installed legacy TestClient/AnyIO combination deadlocks on synchronous
    # dependencies. Keep the production dependency synchronous, but exercise its
    # exact provider through an async test override.
    monkeypatch.setitem(
        server.app.dependency_overrides,
        lifecycle._check_instance_rate_limit,
        _rate_limit,
    )
    return server.app


class _FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closes += 1


class _FakeBotsRepository:
    def __init__(self):
        self.record = None
        self.status_updates = []

    def get_by_instance_id(self, instance_id):
        if self.record is not None and self.record.instance_id == instance_id:
            return self.record
        return None

    def create_bot(self, *, instance_id, network, strategy, config):
        self.record = SimpleNamespace(
            id=1,
            instance_id=instance_id,
            network=network,
            strategy=strategy,
            config=config,
        )
        return self.record

    def update_status(self, instance_id, status, process_id=None):
        self.status_updates.append((instance_id, status, process_id))

    def delete_bot(self, instance_id):
        if self.record is not None and self.record.instance_id == instance_id:
            self.record = None


class _FakeEventsRepository:
    def __init__(self):
        self.events = []

    def log_event(self, bot_id, event_type, severity, message, details=None):
        self.events.append((bot_id, event_type, severity, message, details))


class _FakeUnitOfWork:
    def __init__(self):
        self.bots = _FakeBotsRepository()
        self.events = _FakeEventsRepository()


class _FakeManager:
    def __init__(self):
        self.status = BotStatus.STOPPED
        self.calls = []

    def _build_config_meta(self, _payload):
        return {"source": "test"}

    async def create_instance(self, config):
        self.calls.append(("create", config.instance_id))
        self.status = BotStatus.STOPPED
        return BotOperationResult(
            success=True,
            message="created",
            instance_id=config.instance_id,
            status=self.status,
        )

    async def start_instance(self, instance_id):
        self.calls.append(("start", instance_id))
        self.status = BotStatus.RUNNING
        return BotOperationResult(
            success=True,
            message="started",
            instance_id=instance_id,
            status=self.status,
            data={"process_id": 4321},
        )

    async def stop_instance(self, instance_id, force=False):
        self.calls.append(("stop", instance_id, force))
        self.status = BotStatus.STOPPED
        return BotOperationResult(
            success=True,
            message="stopped",
            instance_id=instance_id,
            status=self.status,
        )

    async def get_instance_status(self, instance_id):
        self.calls.append(("status", instance_id))
        return BotInstanceStatus(
            instance_id=instance_id,
            status=self.status,
            process_id=4321 if self.status == BotStatus.RUNNING else None,
            last_update=datetime.now(timezone.utc),
            config={},
            trading_stats={},
        )

    async def list_instances(self):
        return [await self.get_instance_status("bot-flow-1")]

    async def delete_instance(self, instance_id):
        self.calls.append(("delete", instance_id))
        return BotOperationResult(
            success=True,
            message="deleted",
            instance_id=instance_id,
            status=BotStatus.STOPPED,
        )


def test_lifecycle_router_shape_auth_registration_and_reexports():
    routes = [route for route in lifecycle.router.routes if isinstance(route, APIRoute)]
    operations = {
        (method, route.path)
        for route in routes
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert operations == _LIFECYCLE_OPERATIONS

    for route in routes:
        dependencies = [dependency.call for dependency in route.dependant.dependencies]
        methods = (route.methods or set()) - {"HEAD", "OPTIONS"}
        # Anything that creates, starts, stops or deletes a trading runtime
        # needs an admin; reads need an authenticated active user.
        if methods & {"POST", "PUT", "PATCH", "DELETE"}:
            assert get_admin_user in dependencies, route.path
        else:
            assert get_current_active_user in dependencies, route.path
        assert route.endpoint.__module__ == "src.api.v1.bot_lifecycle"

    create_route = next(
        route
        for route in routes
        if route.path == "/api/v1/bots" and route.methods == {"POST"}
    )
    assert lifecycle._check_instance_rate_limit in [
        dependency.call for dependency in create_route.dependant.dependencies
    ]

    direct_duplicates = []
    for route in server.app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if (method, route.path) in _LIFECYCLE_OPERATIONS:
                direct_duplicates.append((method, route.path))
    mounts = [
        route
        for route in server.app.routes
        if getattr(route, "original_router", None) is lifecycle.router
    ]
    assert direct_duplicates == []
    assert len(mounts) == 1

    for name in (
        "create_bot_instance",
        "delete_bot_instance",
        "get_bot_instance",
        "list_bot_instances",
        "quick_deploy_bot",
        "restart_bot_instance",
        "start_bot_instance",
        "stop_bot_instance",
    ):
        assert getattr(server, name) is getattr(lifecycle, name)


@pytest.mark.asyncio
async def test_lifecycle_routes_require_auth(monkeypatch):
    async def _reject_credentials():
        raise HTTPException(status_code=401, detail="Missing credentials")

    async def _skip_rate_limit():
        return None

    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        _reject_credentials,
    )
    monkeypatch.setitem(
        server.app.dependency_overrides,
        lifecycle._check_instance_rate_limit,
        _skip_rate_limit,
    )

    quick_payload = {
        "credentials": _CREATE_PAYLOAD["credentials"],
        "trading_params": _CREATE_PAYLOAD["trading_params"],
    }
    responses = [
        await _request("POST", "/api/v1/bots", json=_CREATE_PAYLOAD),
        await _request("GET", "/api/v1/bots"),
        await _request("GET", "/api/v1/bots/bot-flow-1"),
        await _request("DELETE", "/api/v1/bots/bot-flow-1"),
        await _request("POST", "/api/v1/bots/bot-flow-1/start"),
        await _request("POST", "/api/v1/bots/bot-flow-1/stop"),
        await _request("POST", "/api/v1/bots/bot-flow-1/restart"),
        await _request(
            "POST",
            "/api/v1/bots/quick-deploy",
            params={"instance_name": "Quick Bot", "auto_start": "false"},
            json=quick_payload,
        ),
    ]

    assert [response.status_code for response in responses] == [401] * 8


@pytest.mark.asyncio
async def test_create_start_status_stop_flow_uses_canonical_manager(
    authed_app, monkeypatch
):
    _ = authed_app
    fake_manager = _FakeManager()
    fake_session = _FakeSession()
    fake_uow = _FakeUnitOfWork()
    rate_limited_paths = []
    notifications = []

    monkeypatch.setattr(server, "bot_manager", fake_manager)
    monkeypatch.setattr(lifecycle.db, "get_session", lambda: fake_session)
    monkeypatch.setattr(lifecycle, "UnitOfWork", lambda _session: fake_uow)
    monkeypatch.setattr(lifecycle, "seal_config_secrets", lambda payload: payload)
    monkeypatch.setattr(lifecycle, "open_config_secrets", lambda payload: payload)
    monkeypatch.setattr(
        lifecycle,
        "_instance_rate_limiter",
        lambda request: rate_limited_paths.append(request.url.path),
    )
    monkeypatch.setattr(
        lifecycle,
        "_send_bot_lifecycle_notification",
        lambda action, *_args, **_kwargs: notifications.append(action) or True,
    )

    create_response = await _request("POST", "/api/v1/bots", json=_CREATE_PAYLOAD)
    start_response = await _request("POST", "/api/v1/bots/bot-flow-1/start")
    status_response = await _request("GET", "/api/v1/bots/bot-flow-1")
    stop_response = await _request("POST", "/api/v1/bots/bot-flow-1/stop")

    for response in (
        create_response,
        start_response,
        status_response,
        stop_response,
    ):
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["trace_id"]

    assert status_response.json()["data"]["status"] == "running"
    assert fake_manager.calls == [
        ("create", "bot-flow-1"),
        ("start", "bot-flow-1"),
        ("status", "bot-flow-1"),
        ("stop", "bot-flow-1", False),
    ]
    assert rate_limited_paths == ["/api/v1/bots"]
    assert notifications == ["created", "started", "stopped"]
    assert [event[1] for event in fake_uow.events.events] == [
        "bot_created",
        "bot_started",
        "bot_stopped",
    ]


@pytest.mark.asyncio
async def test_create_db_failure_cleans_up_manager_instance(authed_app, monkeypatch):
    _ = authed_app
    fake_manager = _FakeManager()
    notifications = []

    monkeypatch.setattr(server, "bot_manager", fake_manager)
    monkeypatch.setattr(
        lifecycle.db,
        "get_session",
        lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    monkeypatch.setattr(
        lifecycle,
        "_send_bot_lifecycle_notification",
        lambda action, *_args, **_kwargs: notifications.append(action) or True,
    )

    response = await _request("POST", "/api/v1/bots", json=_CREATE_PAYLOAD)

    assert response.status_code == 500
    assert response.json()["success"] is False
    assert response.json()["message"] == "Internal server error"
    assert fake_manager.calls == [
        ("create", "bot-flow-1"),
        ("delete", "bot-flow-1"),
    ]
    assert notifications == []


@pytest.mark.asyncio
async def test_restart_then_delete_preserves_lifecycle_side_effects(
    authed_app, monkeypatch
):
    _ = authed_app
    fake_manager = _FakeManager()
    fake_session = _FakeSession()
    fake_uow = _FakeUnitOfWork()
    notifications = []

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(server, "bot_manager", fake_manager)
    monkeypatch.setattr(lifecycle.db, "get_session", lambda: fake_session)
    monkeypatch.setattr(lifecycle, "UnitOfWork", lambda _session: fake_uow)
    monkeypatch.setattr(lifecycle, "seal_config_secrets", lambda payload: payload)
    monkeypatch.setattr(lifecycle, "open_config_secrets", lambda payload: payload)
    monkeypatch.setattr(lifecycle.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(
        lifecycle,
        "_send_bot_lifecycle_notification",
        lambda action, *_args, **_kwargs: notifications.append(action) or True,
    )

    create_response = await _request("POST", "/api/v1/bots", json=_CREATE_PAYLOAD)
    restart_response = await _request("POST", "/api/v1/bots/bot-flow-1/restart")
    delete_response = await _request("DELETE", "/api/v1/bots/bot-flow-1")

    assert [
        create_response.status_code,
        restart_response.status_code,
        delete_response.status_code,
    ] == [200, 200, 200]
    assert fake_manager.calls == [
        ("create", "bot-flow-1"),
        ("stop", "bot-flow-1", False),
        ("start", "bot-flow-1"),
        ("delete", "bot-flow-1"),
    ]
    assert notifications == ["created", "restarted", "deleted"]
    assert [event[1] for event in fake_uow.events.events] == [
        "bot_created",
        "bot_restarted",
        "bot_deleted",
    ]
    assert fake_uow.bots.record is None


@pytest.mark.asyncio
async def test_quick_deploy_without_autostart_preserves_contract(
    authed_app, monkeypatch
):
    _ = authed_app
    fake_manager = _FakeManager()
    monkeypatch.setattr(server, "bot_manager", fake_manager)

    response = await _request(
        "POST",
        "/api/v1/bots/quick-deploy",
        params={"instance_name": "Quick Bot!", "auto_start": "false"},
        json={
            "credentials": _CREATE_PAYLOAD["credentials"],
            "trading_params": _CREATE_PAYLOAD["trading_params"],
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["instance_id"].startswith("quick-bot--")
    assert response.json()["data"]["status"] == "stopped"
    assert [call[0] for call in fake_manager.calls] == ["create"]


@pytest.mark.asyncio
async def test_degraded_manager_behavior_remains_fail_safe(authed_app, monkeypatch):
    _ = authed_app
    monkeypatch.setattr(server, "bot_manager", None)

    list_response = await _request("GET", "/api/v1/bots")
    get_response = await _request("GET", "/api/v1/bots/missing")

    assert list_response.status_code == 200
    assert list_response.json()["data"] == {"bots": [], "total": 0}
    assert get_response.status_code == 503
    assert get_response.json()["success"] is False


@pytest.mark.asyncio
async def test_capabilities_and_openapi_preserve_lifecycle_contract(authed_app):
    _ = authed_app
    response = await _request("GET", "/api/v1/capabilities")
    assert response.status_code == 200
    advertised = set(response.json()["data"]["http_endpoints"])
    expected = {f"{method} {path}" for method, path in _LIFECYCLE_OPERATIONS}
    assert expected <= advertised

    generated = server.app.openapi()
    checked = json.loads(Path("openapi.json").read_text())
    for path in {path for _, path in _LIFECYCLE_OPERATIONS}:
        assert generated["paths"][path] == checked["paths"][path]


@pytest.mark.asyncio
async def test_readiness_remains_strict_for_manager_availability(monkeypatch):
    class _BacktestService:
        def get_runtime_health(self):
            return {}

    @contextmanager
    def _service_scope():
        yield _BacktestService()

    monkeypatch.setattr(server, "backtest_service_scope", _service_scope)
    monkeypatch.setattr(
        server,
        "_backtest_storage_health",
        lambda _service: {"ready": True},
    )
    monkeypatch.setattr(server, "_backtest_capacity_snapshot", lambda _health: {})
    monkeypatch.setattr(
        server,
        "_strategy_resolution_metrics_snapshot",
        lambda: {"alerts": {}},
    )
    monkeypatch.setattr(server, "_bot_recovery_diagnostics", lambda: {})
    monkeypatch.setattr(server, "_bot_db_sync_diagnostics", lambda: {})
    monkeypatch.setattr(
        server.manager,
        "get_backtest_send_failure_summary",
        lambda: {},
    )

    monkeypatch.setattr(server, "bot_manager", None)
    not_ready = await _request("GET", "/ready")
    monkeypatch.setattr(server, "bot_manager", _FakeManager())
    ready = await _request("GET", "/ready")

    assert not_ready.status_code == 503
    assert not_ready.json()["data"]["bot_manager_ready"] is False
    assert ready.status_code == 200
    assert ready.json()["data"]["bot_manager_ready"] is True


# --- authorization: lifecycle mutations need an admin ------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/v1/bots"),
        ("DELETE", "/api/v1/bots/bot-x"),
        ("POST", "/api/v1/bots/bot-x/start"),
        ("POST", "/api/v1/bots/bot-x/stop"),
        ("POST", "/api/v1/bots/bot-x/restart"),
        ("POST", "/api/v1/bots/quick-deploy?instance_name=bot-x"),
    ],
)
async def test_lifecycle_mutations_reject_a_non_admin_user(monkeypatch, method, path):
    async def _plain_user():
        return SimpleNamespace(
            is_active=True,
            is_admin=False,
            is_superuser=False,
            username="viewer",
            email="viewer@example.test",
        )

    monkeypatch.setitem(
        server.app.dependency_overrides, get_current_active_user, _plain_user
    )

    response = await _request(method, path, json=_CREATE_PAYLOAD)

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_service_token_principal_passes_the_admin_gate():
    """The backend's service token maps to a superuser principal."""
    principal = SimpleNamespace(is_active=True, is_superuser=True, username="svc")

    assert await get_admin_user(principal) is principal
