"""Contracts for the extracted realtime bot HTTP/WebSocket router (Phase 5c)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException, WebSocketDisconnect
from fastapi.routing import APIRoute, APIWebSocketRoute

import src.api.server as server
import src.api.v1.bot_realtime as realtime
from src.middleware.auth_middleware import get_current_active_user

_HTTP_OPERATIONS = {
    ("GET", "/api/v1/bots/{bot_instance_id}/positions/current"),
    ("GET", "/api/v1/bots/{bot_instance_id}/positions/{position_id}"),
    ("GET", "/api/v1/bots/{bot_instance_id}/market-data"),
    ("GET", "/api/v1/bots/{bot_instance_id}/realtime-stats"),
    ("GET", "/api/v1/bots/{bot_instance_id}/alerts"),
    ("GET", "/api/v1/bots/{bot_instance_id}/position-history/{position_id}"),
}
_WEBSOCKET_PATHS = {
    "/api/v1/bots/{bot_instance_id}/alerts/live",
    "/ws/bots/{bot_instance_id}",
    "/ws/strategies",
}


async def _request(method: str, path: str, *, raise_app_exceptions=False, **kwargs):
    transport = httpx.ASGITransport(
        app=server.app,
        raise_app_exceptions=raise_app_exceptions,
    )
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
            username="operator",
            email="operator@example.test",
        )

    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        _active_user,
    )
    return server.app


class _FakeSession:
    def __init__(self):
        self.closes = 0

    def close(self):
        self.closes += 1


class _FakeCoreUnitOfWork:
    def __init__(self, session):
        assert isinstance(session, _FakeSession)
        self.bots = SimpleNamespace(
            get_by_instance_id=lambda instance_id: (
                SimpleNamespace(id=7) if instance_id == "strategy-1-7" else None
            )
        )


def _sample_position(now):
    return SimpleNamespace(
        bot_instance_id=7,
        position_id="position-1",
        pair1="BTC-USD",
        pair2="ETH-USD",
        status=SimpleNamespace(value="OPEN"),
        side1="SELL",
        side2="BUY",
        entry_price1=Decimal("65000.5"),
        entry_price2=Decimal("3500.25"),
        current_price1=Decimal("64000"),
        current_price2=Decimal("3550"),
        current_size1=Decimal("0.1"),
        current_size2=Decimal("1.8"),
        entry_cost=Decimal("1000"),
        current_value=Decimal("1012.5"),
        unrealized_pnl=Decimal("12.5"),
        unrealized_pnl_pct=Decimal("1.25"),
        realized_pnl=Decimal("0"),
        z_score_entry=Decimal("2.1"),
        z_score_current=Decimal("1.4"),
        hedge_ratio=Decimal("0.8"),
        correlation=Decimal("0.92"),
        half_life=Decimal("12"),
        entry_time=now,
        updated_at=now,
        closed_at=None,
    )


class _FakeRealtimeUnitOfWork:
    def __init__(self, session):
        assert isinstance(session, _FakeSession)
        now = datetime(2026, 8, 2, 20, 0, tzinfo=timezone.utc)
        position = _sample_position(now)
        market = SimpleNamespace(
            symbol="BTC-USD",
            current_price=Decimal("64000"),
            bid_price=Decimal("63999"),
            ask_price=Decimal("64001"),
            volume_24h=Decimal("123456"),
            volatility_24h=Decimal("0.05"),
            rsi=Decimal("55"),
            macd=Decimal("1.5"),
            moving_avg_20=Decimal("63500"),
            moving_avg_50=Decimal("62000"),
            funding_rate=Decimal("0.0001"),
            timestamp=now,
        )
        stats = SimpleNamespace(
            total_open_positions=1,
            total_unrealized_pnl=Decimal("12.5"),
            total_unrealized_pnl_pct=Decimal("1.25"),
            daily_pnl=Decimal("10"),
            daily_pnl_pct=Decimal("1"),
            daily_trades_opened=2,
            daily_trades_closed=1,
            daily_wins=1,
            daily_losses=0,
            daily_win_rate=Decimal("100"),
            max_drawdown_session=Decimal("2"),
            current_drawdown=Decimal("0.5"),
            var_95=Decimal("3.25"),
            avg_trade_duration_seconds=90,
            is_healthy=True,
            updated_at=now,
        )
        alerts = [
            SimpleNamespace(
                id=1,
                alert_type="risk",
                severity="warning",
                message="drawdown threshold",
                notified=False,
                notified_via=None,
                timestamp=now,
                details={"drawdown": 2},
            ),
            SimpleNamespace(
                id=2,
                alert_type="runtime",
                severity="info",
                message="worker online",
                notified=False,
                notified_via={"telegram": False},
                timestamp=now,
                details=None,
            ),
        ]
        snapshots = [
            SimpleNamespace(
                pair1="BTC-USD",
                pair2="ETH-USD",
                unrealized_pnl=Decimal("12.5"),
                unrealized_pnl_pct=Decimal("1.25"),
                current_price1=Decimal("64000"),
                current_price2=Decimal("3550"),
                z_score=Decimal("1.4"),
                timestamp=now,
            )
        ]

        self.positions = SimpleNamespace(
            get_open_positions=lambda bot_id: [position] if bot_id == 7 else [],
            get_position_by_id=lambda position_id: (
                position if position_id == "position-1" else None
            ),
        )
        self.market_data = SimpleNamespace(
            get_all_market_data=lambda bot_id: [market] if bot_id == 7 else []
        )
        self.stats = SimpleNamespace(
            get_stats=lambda bot_id: stats if bot_id == 7 else None
        )
        self.alerts = SimpleNamespace(
            get_unnotified_alerts=lambda bot_id: alerts if bot_id == 7 else []
        )
        self.snapshots = SimpleNamespace(
            get_position_history=lambda position_id, *, hours: (
                snapshots if position_id == "position-1" and hours == 12 else []
            )
        )


class _MockWebSocket:
    def __init__(self, *, headers=None, incoming=None):
        self.headers = headers or {}
        self.query_params = {}
        self.incoming = list(incoming or [])
        self.closed = False
        self.close_code = None
        self.close_reason = None

    async def close(self, code, reason):
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    async def receive_text(self):
        if self.incoming:
            return self.incoming.pop(0)
        raise WebSocketDisconnect(code=1000)


def test_realtime_router_shape_auth_registration_and_reexports():
    http_routes = [
        route for route in realtime.router.routes if isinstance(route, APIRoute)
    ]
    websocket_routes = [
        route
        for route in realtime.router.routes
        if isinstance(route, APIWebSocketRoute)
    ]
    operations = {
        (method, route.path)
        for route in http_routes
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert operations == _HTTP_OPERATIONS
    assert {route.path for route in websocket_routes} == _WEBSOCKET_PATHS

    for route in http_routes:
        dependencies = [dependency.call for dependency in route.dependant.dependencies]
        assert get_current_active_user in dependencies
        assert route.endpoint.__module__ == "src.api.v1.bot_realtime"
    for route in websocket_routes:
        assert route.endpoint.__module__ == "src.api.v1.bot_realtime"

    direct_duplicates = []
    for route in server.app.routes:
        path = getattr(route, "path", None)
        if isinstance(route, APIRoute):
            for method in route.methods or set():
                if (method, path) in _HTTP_OPERATIONS:
                    direct_duplicates.append((method, path))
        elif isinstance(route, APIWebSocketRoute) and path in _WEBSOCKET_PATHS:
            direct_duplicates.append(("WS", path))
    mounts = [
        route
        for route in server.app.routes
        if getattr(route, "original_router", None) is realtime.router
    ]
    assert direct_duplicates == []
    assert len(mounts) == 1

    for name in (
        "get_alerts",
        "get_current_positions",
        "get_market_data",
        "get_position",
        "get_position_history",
        "get_realtime_stats",
        "websocket_alerts",
        "websocket_bot_runtime",
        "websocket_strategies",
    ):
        assert getattr(server, name) is getattr(realtime, name)
    assert (
        server._authorize_websocket_connection
        is realtime._authorize_websocket_connection
    )
    assert server._resolve_realtime_bot_id is realtime._resolve_realtime_bot_id


@pytest.mark.asyncio
async def test_realtime_http_routes_require_auth(monkeypatch):
    async def _reject_credentials():
        raise HTTPException(status_code=401, detail="Missing credentials")

    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        _reject_credentials,
    )

    responses = [
        await _request("GET", "/api/v1/bots/strategy-1-7/positions/current"),
        await _request("GET", "/api/v1/bots/strategy-1-7/positions/position-1"),
        await _request("GET", "/api/v1/bots/strategy-1-7/market-data"),
        await _request("GET", "/api/v1/bots/strategy-1-7/realtime-stats"),
        await _request("GET", "/api/v1/bots/strategy-1-7/alerts"),
        await _request("GET", "/api/v1/bots/strategy-1-7/position-history/position-1"),
    ]

    assert [response.status_code for response in responses] == [401] * 6


@pytest.mark.asyncio
async def test_realtime_http_routes_serialize_canonical_data(
    authed_app,
    monkeypatch,
):
    _ = authed_app
    fake_session = _FakeSession()
    monkeypatch.setattr(server.db, "get_session", lambda: fake_session)
    monkeypatch.setattr(server, "UnitOfWork", _FakeCoreUnitOfWork)
    monkeypatch.setattr(server, "UnitOfWorkRealtime", _FakeRealtimeUnitOfWork)

    current = await _request("GET", "/api/v1/bots/strategy-1-7/positions/current")
    position = await _request("GET", "/api/v1/bots/strategy-1-7/positions/position-1")
    market = await _request("GET", "/api/v1/bots/strategy-1-7/market-data")
    stats = await _request("GET", "/api/v1/bots/strategy-1-7/realtime-stats")
    alerts = await _request(
        "GET",
        "/api/v1/bots/strategy-1-7/alerts",
        params={"limit": 1},
    )
    history = await _request(
        "GET",
        "/api/v1/bots/strategy-1-7/position-history/position-1",
        params={"hours": 12},
    )

    assert [
        current.status_code,
        position.status_code,
        market.status_code,
        stats.status_code,
        alerts.status_code,
        history.status_code,
    ] == [200] * 6
    assert current.json()["data"]["positions"][0]["position_id"] == "position-1"
    assert current.json()["data"]["positions"][0]["updated_at"]
    assert position.json()["data"]["current_value"] == 1012.5
    assert market.json()["data"]["market_data"][0]["symbol"] == "BTC-USD"
    assert stats.json()["data"]["stats"]["daily_win_rate"] == 100.0
    assert alerts.json()["data"]["count"] == 1
    assert history.json()["data"]["hours"] == 12
    assert history.json()["data"]["snapshots"][0]["z_score"] == 1.4
    assert fake_session.closes == 6


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/bots/missing/positions/current",
        "/api/v1/bots/missing/positions/position-1",
        "/api/v1/bots/missing/market-data",
        "/api/v1/bots/missing/realtime-stats",
        "/api/v1/bots/missing/alerts",
        "/api/v1/bots/missing/position-history/position-1",
    ],
)
async def test_realtime_http_routes_return_404_for_unknown_bot(
    path,
    authed_app,
    monkeypatch,
):
    _ = authed_app
    fake_session = _FakeSession()
    monkeypatch.setattr(server.db, "get_session", lambda: fake_session)
    monkeypatch.setattr(server, "UnitOfWork", _FakeCoreUnitOfWork)
    monkeypatch.setattr(server, "UnitOfWorkRealtime", _FakeRealtimeUnitOfWork)

    response = await _request("GET", path)

    assert response.status_code == 404
    assert response.json()["success"] is False
    assert fake_session.closes == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/bots/strategy-1-7/positions/current",
        "/api/v1/bots/strategy-1-7/positions/position-1",
        "/api/v1/bots/strategy-1-7/market-data",
        "/api/v1/bots/strategy-1-7/realtime-stats",
        "/api/v1/bots/strategy-1-7/alerts",
        "/api/v1/bots/strategy-1-7/position-history/position-1",
    ],
)
async def test_realtime_session_acquisition_failure_stays_in_response_envelope(
    path,
    authed_app,
    monkeypatch,
):
    _ = authed_app

    def _raise_database_error():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(server.db, "get_session", _raise_database_error)

    response = await _request(
        "GET",
        path,
        raise_app_exceptions=True,
    )

    assert response.status_code == 500
    assert response.json()["success"] is False
    assert response.json()["message"] == "Internal server error"
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_bot_websocket_adapters_authorize_and_delegate(monkeypatch):
    calls = []

    class _FakeWebSocketServer:
        @staticmethod
        async def handle_connection(websocket, channel):
            calls.append((websocket, channel))

    monkeypatch.setattr(server, "is_auth_bypass_enabled", lambda: True)
    monkeypatch.setattr(realtime, "WebSocketServer", _FakeWebSocketServer)
    alerts_ws = _MockWebSocket()
    runtime_ws = _MockWebSocket()

    await server.websocket_alerts(alerts_ws, "strategy-1-7")
    await server.websocket_bot_runtime(runtime_ws, "strategy-1-7")

    assert calls == [
        (alerts_ws, "strategy-1-7"),
        (runtime_ws, "strategy-1-7"),
    ]


@pytest.mark.asyncio
async def test_strategy_websocket_sends_snapshot_ping_pong_and_disconnects(
    monkeypatch,
):
    class _FakeConnectionManager:
        def __init__(self):
            self.connects = []
            self.messages = []
            self.disconnects = []

        async def connect(self, websocket, channel):
            self.connects.append((websocket, channel))

        async def send_personal_message(self, message, websocket):
            self.messages.append((message, websocket))

        def disconnect(self, websocket, channel):
            self.disconnects.append((websocket, channel))

    fake_manager = _FakeConnectionManager()
    fake_bot_manager = SimpleNamespace(
        get_strategy_status_snapshot=lambda: [
            {
                "strategyId": 7,
                "instance_id": "strategy-1-7",
                "status": "running",
            }
        ]
    )
    websocket = _MockWebSocket(incoming=["not-json", json.dumps({"type": "ping"})])
    monkeypatch.setattr(server, "is_auth_bypass_enabled", lambda: True)
    monkeypatch.setattr(server, "bot_manager", fake_bot_manager)
    monkeypatch.setattr(realtime, "manager", fake_manager)

    await server.websocket_strategies(websocket)

    assert fake_manager.connects == [(websocket, "strategies")]
    assert fake_manager.messages[0][0]["type"] == "strategy_status_snapshot"
    assert fake_manager.messages[0][0]["count"] == 1
    assert fake_manager.messages[1][0]["type"] == "pong"
    assert fake_manager.disconnects == [(websocket, "strategies")]


@pytest.mark.asyncio
async def test_strategy_websocket_degraded_manager_sends_connected_message(
    monkeypatch,
):
    class _FakeConnectionManager:
        def __init__(self):
            self.messages = []

        async def connect(self, _websocket, _channel):
            return None

        async def send_personal_message(self, message, _websocket):
            self.messages.append(message)

        def disconnect(self, _websocket, _channel):
            return None

    fake_manager = _FakeConnectionManager()
    websocket = _MockWebSocket()
    monkeypatch.setattr(server, "is_auth_bypass_enabled", lambda: True)
    monkeypatch.setattr(server, "bot_manager", None)
    monkeypatch.setattr(realtime, "manager", fake_manager)

    await server.websocket_strategies(websocket)

    assert fake_manager.messages[0]["type"] == "strategy_channel_connected"
    assert fake_manager.messages[0]["channel"] == "strategies"


@pytest.mark.asyncio
async def test_websocket_database_failure_rejects_connection(monkeypatch):
    websocket = _MockWebSocket(headers={"authorization": "Bearer service-token"})
    monkeypatch.setattr(server, "is_auth_bypass_enabled", lambda: False)
    monkeypatch.setattr(
        server.db,
        "get_session",
        lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    authorized = await server._authorize_websocket_connection(websocket)

    assert authorized is False
    assert websocket.closed is True
    assert websocket.close_code == 4401
    assert websocket.close_reason == "Invalid websocket auth token"


@pytest.mark.asyncio
async def test_capabilities_and_openapi_preserve_realtime_contract(authed_app):
    _ = authed_app
    response = await _request("GET", "/api/v1/capabilities")
    assert response.status_code == 200
    data = response.json()["data"]
    advertised_http = set(data["http_endpoints"])
    advertised_websockets = set(data["websocket_channels"])
    assert {f"{method} {path}" for method, path in _HTTP_OPERATIONS} <= advertised_http
    assert {f"WS {path}" for path in _WEBSOCKET_PATHS} <= advertised_websockets

    generated = server.app.openapi()
    checked = json.loads(Path("openapi.json").read_text())
    for path in {path for _, path in _HTTP_OPERATIONS}:
        assert generated["paths"][path] == checked["paths"][path]
