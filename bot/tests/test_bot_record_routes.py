"""Contracts for the extracted database-backed bot record router (Phase 5b)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

import src.api.server as server
import src.api.v1.bot_records as records
from src.middleware.auth_middleware import get_current_active_user

_BOT_RECORD_OPERATIONS = {
    ("GET", "/api/v1/bots/{instance_id}/history"),
    ("GET", "/api/v1/bots/{instance_id}/jobs"),
    ("GET", "/api/v1/bots/{instance_id}/trades"),
    ("GET", "/api/v1/bots/{instance_id}/stats"),
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


class _FakeBotsRepository:
    def __init__(self, bot):
        self.bot = bot

    def get_by_instance_id(self, instance_id):
        if self.bot is not None and self.bot.instance_id == instance_id:
            return self.bot
        return None

    def get_statistics(self, instance_id):
        assert instance_id == "bot-records-1"
        return {
            "total_trades": 3,
            "successful_trades": 2,
            "failed_trades": 1,
            "total_profit_loss": Decimal("12.5"),
            "win_rate": Decimal("66.67"),
        }


class _FakeEventsRepository:
    def __init__(self, events):
        self.events = events
        self.requested_days = []

    def get_bot_events(self, bot_id, *, days):
        assert bot_id == 7
        self.requested_days.append(days)
        return self.events


class _FakeJobsRepository:
    def __init__(self, jobs):
        self.jobs = jobs
        self.requested_days = []

    def get_job_history(self, bot_id, *, days):
        assert bot_id == 7
        self.requested_days.append(days)
        return self.jobs


class _FakeTradesRepository:
    def __init__(self, trades):
        self.trades = trades

    def get_bot_trades(self, bot_id):
        assert bot_id == 7
        return list(self.trades)

    def get_trade_statistics(self, bot_id):
        assert bot_id == 7
        return {
            "total_trades": 3,
            "winning_trades": 2,
            "losing_trades": 1,
            "total_profit": Decimal("15.25"),
            "total_loss": Decimal("2.75"),
            "net_profit": Decimal("12.5"),
            "average_profit": Decimal("6.25"),
            "win_rate": Decimal("66.67"),
            "average_duration_seconds": 90,
        }


def _sample_uow():
    now = datetime(2026, 8, 2, 20, 0, tzinfo=timezone.utc)
    bot = SimpleNamespace(
        id=7,
        instance_id="bot-records-1",
        uptime_seconds=123,
    )
    events = [
        SimpleNamespace(
            created_at=now,
            event_type="bot_started",
            severity="info",
            message="started",
            details={"process_id": 4321},
        )
    ]
    jobs = [
        SimpleNamespace(
            job_id="job-complete",
            job_type="live_runtime",
            status=SimpleNamespace(value="completed"),
            progress_pct=100,
            process_id=4321,
            execution_time_ms=250,
            retry_count=0,
            max_retries=3,
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now,
            error_message=None,
            cancellation_reason=None,
            metadata_json={"source": "test"},
        ),
        SimpleNamespace(
            job_id="job-failed",
            job_type="live_runtime",
            status="failed",
            progress_pct=40,
            process_id=None,
            execution_time_ms=None,
            retry_count=1,
            max_retries=3,
            created_at=now,
            updated_at=None,
            started_at=None,
            completed_at=None,
            error_message="worker stopped",
            cancellation_reason=None,
            metadata_json=None,
        ),
    ]
    trades = [
        SimpleNamespace(
            trade_id="trade-open",
            pair1="BTC-USD",
            pair2="ETH-USD",
            status="OPEN",
            entry_price1=Decimal("65000.5"),
            entry_price2=Decimal("3500.25"),
            exit_price1=None,
            exit_price2=None,
            entry_cost=Decimal("1000"),
            exit_proceeds=None,
            profit_loss=None,
            profit_loss_percentage=None,
            opened_at=now,
            closed_at=None,
            duration_seconds=None,
        ),
        SimpleNamespace(
            trade_id="trade-closed",
            pair1="SOL-USD",
            pair2="AVAX-USD",
            status="CLOSED",
            entry_price1=Decimal("150"),
            entry_price2=Decimal("40"),
            exit_price1=Decimal("152"),
            exit_price2=Decimal("39"),
            entry_cost=Decimal("500"),
            exit_proceeds=Decimal("512.5"),
            profit_loss=Decimal("12.5"),
            profit_loss_percentage=Decimal("2.5"),
            opened_at=now,
            closed_at=now,
            duration_seconds=90,
        ),
    ]
    return SimpleNamespace(
        bots=_FakeBotsRepository(bot),
        events=_FakeEventsRepository(events),
        jobs=_FakeJobsRepository(jobs),
        trades=_FakeTradesRepository(trades),
    )


def test_bot_record_router_shape_auth_registration_and_reexports():
    routes = [route for route in records.router.routes if isinstance(route, APIRoute)]
    operations = {
        (method, route.path)
        for route in routes
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert operations == _BOT_RECORD_OPERATIONS

    for route in routes:
        dependencies = [dependency.call for dependency in route.dependant.dependencies]
        assert get_current_active_user in dependencies
        assert route.endpoint.__module__ == "src.api.v1.bot_records"

    direct_duplicates = []
    for route in server.app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if (method, route.path) in _BOT_RECORD_OPERATIONS:
                direct_duplicates.append((method, route.path))
    mounts = [
        route
        for route in server.app.routes
        if getattr(route, "original_router", None) is records.router
    ]
    assert direct_duplicates == []
    assert len(mounts) == 1

    for name in (
        "get_bot_history",
        "get_bot_jobs",
        "get_bot_stats",
        "get_bot_trades",
    ):
        assert getattr(server, name) is getattr(records, name)


@pytest.mark.asyncio
async def test_bot_record_routes_require_auth(monkeypatch):
    async def _reject_credentials():
        raise HTTPException(status_code=401, detail="Missing credentials")

    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        _reject_credentials,
    )

    responses = [
        await _request("GET", "/api/v1/bots/bot-records-1/history"),
        await _request("GET", "/api/v1/bots/bot-records-1/jobs"),
        await _request("GET", "/api/v1/bots/bot-records-1/trades"),
        await _request("GET", "/api/v1/bots/bot-records-1/stats"),
    ]

    assert [response.status_code for response in responses] == [401] * 4


@pytest.mark.asyncio
async def test_bot_record_routes_serialize_database_results(authed_app, monkeypatch):
    _ = authed_app
    fake_session = _FakeSession()
    fake_uow = _sample_uow()
    monkeypatch.setattr(records.db, "get_session", lambda: fake_session)
    monkeypatch.setattr(records, "UnitOfWork", lambda _session: fake_uow)

    history = await _request(
        "GET",
        "/api/v1/bots/bot-records-1/history",
        params={"days": 14},
    )
    jobs = await _request(
        "GET",
        "/api/v1/bots/bot-records-1/jobs",
        params={"days": 30},
    )
    trades = await _request(
        "GET",
        "/api/v1/bots/bot-records-1/trades",
        params={"status": "open"},
    )
    stats = await _request("GET", "/api/v1/bots/bot-records-1/stats")

    assert [
        history.status_code,
        jobs.status_code,
        trades.status_code,
        stats.status_code,
    ] == [
        200,
        200,
        200,
        200,
    ]
    assert history.json()["data"]["days_requested"] == 14
    assert history.json()["data"]["events"][0]["event_type"] == "bot_started"
    assert fake_uow.events.requested_days == [14]

    assert jobs.json()["data"]["statistics"] == {
        "total_jobs": 2,
        "completed": 1,
        "failed": 1,
        "cancelled": 0,
        "pending": 0,
        "running": 0,
    }
    assert jobs.json()["data"]["jobs"][0]["metadata"] == {"source": "test"}
    assert fake_uow.jobs.requested_days == [30]

    assert trades.json()["data"]["filter_status"] == "open"
    assert trades.json()["data"]["total_trades"] == 1
    assert trades.json()["data"]["trades"][0]["entry_price1"] == 65000.5

    assert stats.json()["data"]["bot_statistics"]["uptime_seconds"] == 123
    assert stats.json()["data"]["trade_statistics"]["net_profit"] == 12.5
    assert fake_session.closes == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["history", "jobs", "trades", "stats"])
async def test_bot_record_routes_return_404_and_close_session(
    suffix,
    authed_app,
    monkeypatch,
):
    _ = authed_app
    fake_session = _FakeSession()
    fake_uow = _sample_uow()
    fake_uow.bots.bot = None
    monkeypatch.setattr(records.db, "get_session", lambda: fake_session)
    monkeypatch.setattr(records, "UnitOfWork", lambda _session: fake_uow)

    response = await _request("GET", f"/api/v1/bots/missing/{suffix}")

    assert response.status_code == 404
    assert response.json()["success"] is False
    assert fake_session.closes == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["history", "jobs", "trades", "stats"])
async def test_bot_record_session_acquisition_failure_stays_in_response_envelope(
    suffix,
    authed_app,
    monkeypatch,
):
    _ = authed_app

    def _raise_database_error():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(records.db, "get_session", _raise_database_error)

    response = await _request(
        "GET",
        f"/api/v1/bots/bot-records-1/{suffix}",
        raise_app_exceptions=True,
    )

    assert response.status_code == 500
    assert response.json()["success"] is False
    assert response.json()["message"] == "Internal server error"
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_capabilities_and_openapi_preserve_bot_record_contract(authed_app):
    _ = authed_app
    response = await _request("GET", "/api/v1/capabilities")
    assert response.status_code == 200
    advertised = set(response.json()["data"]["http_endpoints"])
    expected = {f"{method} {path}" for method, path in _BOT_RECORD_OPERATIONS}
    assert expected <= advertised

    generated = server.app.openapi()
    checked = json.loads(Path("openapi.json").read_text())
    for path in {path for _, path in _BOT_RECORD_OPERATIONS}:
        assert generated["paths"][path] == checked["paths"][path]
