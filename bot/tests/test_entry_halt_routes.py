"""Operator surface of the entry halt: see it, and clear it on the record."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.api.server as server
import src.api.v1.bot_lifecycle as lifecycle
from src.bot_instance_manager import BotInstanceManager
from src.infrastructure import database
from src.middleware.auth_middleware import get_current_active_user
from src.trading import bot_agents_state, entry_halt
from src.trading.entry_halt import HaltScope
from tests.test_entry_halt_durable import _DDL

INSTANCE_ID = "strategy-85-1"
RUNTIME = HaltScope(INSTANCE_ID, "testnet", "dydx1probe", 0)


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        return await client.request(method, path, **kwargs)


@pytest.fixture
def operator_api(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as connection:
        connection.execute(text(_DDL))
    monkeypatch.setattr(database.db, "get_session", sessionmaker(bind=engine))
    monkeypatch.setattr(
        bot_agents_state, "BOT_AGENTS_PATH", tmp_path / "bot_agents_x.json"
    )
    monkeypatch.setattr(entry_halt, "_runtime_scope", None)

    async def _operator():
        return SimpleNamespace(
            is_active=True, is_admin=True, username="operator", email="op@example.test"
        )

    monkeypatch.setitem(
        server.app.dependency_overrides, get_current_active_user, _operator
    )

    instance = SimpleNamespace(
        config=SimpleNamespace(
            credentials=SimpleNamespace(address="dydx1probe"),
            trading_params=SimpleNamespace(is_testnet=True, subaccount_number=0),
        )
    )
    monkeypatch.setattr(
        server,
        "bot_manager",
        SimpleNamespace(
            instances={INSTANCE_ID: instance},
            subaccount_scope=BotInstanceManager.subaccount_scope,
        ),
    )

    events = []
    monkeypatch.setattr(
        lifecycle,
        "_persist_bot_status_and_event",
        lambda instance_id, **event: events.append((instance_id, event)),
    )
    return SimpleNamespace(engine=engine, events=events)


def _halt_rows(engine):
    with engine.connect() as connection:
        return [
            dict(row._mapping)
            for row in connection.execute(text("SELECT * FROM entry_halts"))
        ]


@pytest.mark.asyncio
async def test_no_halt_reads_as_not_halted(operator_api):
    response = await _request("GET", f"/api/v1/bots/{INSTANCE_ID}/entry-halt")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "halted": False,
        "unverified": False,
        "halt": None,
    }


@pytest.mark.asyncio
async def test_the_halt_a_runtime_set_is_shown_with_its_account_and_reason(
    operator_api,
):
    entry_halt.halt_entries(
        "emergency close failed", {"market_1": "AVAX-USD"}, scope=RUNTIME
    )

    response = await _request("GET", f"/api/v1/bots/{INSTANCE_ID}/entry-halt")

    data = response.json()["data"]
    assert data["halted"] is True and data["unverified"] is False
    assert data["halt"]["reason"] == "emergency close failed"
    assert data["halt"]["details"] == {"market_1": "AVAX-USD"}
    assert (data["halt"]["network"], data["halt"]["subaccount_number"]) == (
        "testnet",
        0,
    )


@pytest.mark.asyncio
async def test_an_unreadable_halt_state_is_reported_as_unverified(
    operator_api, monkeypatch
):
    def _down(_scope):
        raise RuntimeError("database is down")

    monkeypatch.setattr(entry_halt, "_db_active_halt", _down)

    response = await _request("GET", f"/api/v1/bots/{INSTANCE_ID}/entry-halt")

    assert response.json()["data"] == {
        "halted": True,
        "unverified": True,
        "halt": None,
    }


@pytest.mark.asyncio
async def test_clearing_needs_the_acknowledgement(operator_api):
    entry_halt.halt_entries("emergency close failed", scope=RUNTIME)

    response = await _request(
        "POST", f"/api/v1/bots/{INSTANCE_ID}/entry-halt/clear", json={"note": "ok"}
    )

    assert response.status_code == 400
    assert entry_halt.entries_halted(RUNTIME) is not None
    assert operator_api.events == []


@pytest.mark.asyncio
async def test_clearing_records_the_operator_and_resumes_entries(operator_api):
    entry_halt.halt_entries("emergency close failed", scope=RUNTIME)

    response = await _request(
        "POST",
        f"/api/v1/bots/{INSTANCE_ID}/entry-halt/clear",
        json={
            "acknowledged": True,
            "cleared_by": "chris",
            "note": "no AVAX position on chain",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"halted": False, "cleared": 1}
    assert entry_halt.entries_halted(RUNTIME) is None
    (row,) = _halt_rows(operator_api.engine)
    assert row["cleared_at"] is not None
    assert (row["cleared_by"], row["clear_note"]) == (
        "chris",
        "no AVAX position on chain",
    )
    ((instance_id, event),) = operator_api.events
    assert instance_id == INSTANCE_ID
    assert event["event_type"] == "entry_halt_cleared"


@pytest.mark.asyncio
async def test_clearing_falls_back_to_the_authenticated_user(operator_api):
    entry_halt.halt_entries("emergency close failed", scope=RUNTIME)

    await _request(
        "POST",
        f"/api/v1/bots/{INSTANCE_ID}/entry-halt/clear",
        json={"acknowledged": True},
    )

    (row,) = _halt_rows(operator_api.engine)
    assert row["cleared_by"] == "operator"


@pytest.mark.asyncio
async def test_an_unknown_instance_is_not_found(operator_api):
    read = await _request("GET", "/api/v1/bots/strategy-85-404/entry-halt")
    clear = await _request(
        "POST",
        "/api/v1/bots/strategy-85-404/entry-halt/clear",
        json={"acknowledged": True},
    )

    assert (read.status_code, clear.status_code) == (404, 404)
