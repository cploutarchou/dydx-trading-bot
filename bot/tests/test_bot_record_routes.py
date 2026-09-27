"""Contracts for the extracted database-backed bot record router (Phase 5b)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.api.server as server
import src.api.v1.bot_records as records
from src.middleware.auth_middleware import get_current_active_user

_BOT_RECORD_OPERATIONS = {
    ("GET", "/api/v1/bots/{instance_id}/history"),
    ("GET", "/api/v1/bots/{instance_id}/jobs"),
    ("GET", "/api/v1/bots/{instance_id}/trades"),
    ("GET", "/api/v1/bots/{instance_id}/cointegrated-pairs"),
    ("GET", "/api/v1/bots/{instance_id}/stats"),
}

_COINTEGRATED_PAIRS_DDL = """
CREATE TABLE cointegrated_pairs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instance_id VARCHAR(64) NOT NULL UNIQUE,
  pairs_json TEXT NOT NULL DEFAULT '[]',
  pairs_count INTEGER NOT NULL DEFAULT 0,
  high_confidence_count INTEGER NOT NULL DEFAULT 0,
  analyzed_at DATETIME NOT NULL
)
"""

PLANTED_ADDRESS = "dydx1plantedaddressthatmustnotleak"
PLANTED_MNEMONIC = "planted mnemonic words that must never leave the bot"


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
            entry_size1=Decimal("0.01"),
            entry_size2=Decimal("0.2"),
            exit_size1=None,
            exit_size2=None,
            profit_loss=None,
            profit_loss_percentage=None,
            created_at=now,
            closed_at=None,
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
            entry_size1=Decimal("2"),
            entry_size2=Decimal("5"),
            exit_size1=Decimal("2"),
            exit_size2=Decimal("5"),
            profit_loss=Decimal("12.5"),
            profit_loss_percentage=Decimal("2.5"),
            created_at=now,
            closed_at=now,
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
        await _request("GET", "/api/v1/bots/bot-records-1/cointegrated-pairs"),
        await _request("GET", "/api/v1/bots/bot-records-1/stats"),
    ]

    assert [response.status_code for response in responses] == [401] * 5


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
@pytest.mark.parametrize(
    "suffix", ["history", "jobs", "trades", "cointegrated-pairs", "stats"]
)
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


# --- trades: newest first, paged on request ---------------------------------


def _paged_uow(now):
    """Three trades opened an hour apart, handed back in oldest-first DB order."""

    def _trade(trade_id, opened_at, status="CLOSED"):
        return SimpleNamespace(
            trade_id=trade_id,
            pair1="BTC-USD",
            pair2="ETH-USD",
            status=status,
            entry_price1=Decimal("1"),
            entry_price2=Decimal("2"),
            exit_price1=None,
            exit_price2=None,
            entry_size1=Decimal("1"),
            entry_size2=Decimal("1"),
            exit_size1=None,
            exit_size2=None,
            profit_loss=None,
            profit_loss_percentage=None,
            created_at=opened_at,
            closed_at=None,
        )

    uow = _sample_uow()
    uow.trades = _FakeTradesRepository(
        [
            _trade("t-oldest", now - timedelta(hours=2)),
            _trade("t-middle", now - timedelta(hours=1), status="OPEN"),
            _trade("t-newest", now),
        ]
    )
    return uow


@pytest.mark.asyncio
async def test_bot_trades_are_newest_first_and_page_only_when_asked(
    authed_app, monkeypatch
):
    _ = authed_app
    now = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(records.db, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(records, "UnitOfWork", lambda _session: _paged_uow(now))

    async def _trades(**params):
        response = await _request(
            "GET", "/api/v1/bots/bot-records-1/trades", params=params
        )
        assert response.status_code == 200
        data = response.json()["data"]
        return [trade["trade_id"] for trade in data["trades"]], data

    ids, data = await _trades()
    assert ids == ["t-newest", "t-middle", "t-oldest"]
    assert (data["total_trades"], data["count"]) == (3, 3)
    assert (data["limit"], data["offset"]) == (None, 0)

    ids, data = await _trades(limit=2)
    assert ids == ["t-newest", "t-middle"]
    assert (data["total_trades"], data["count"]) == (3, 2)
    assert (data["limit"], data["offset"]) == (2, 0)

    ids, data = await _trades(limit=2, offset=2)
    assert ids == ["t-oldest"]
    assert (data["total_trades"], data["count"], data["offset"]) == (3, 1, 2)

    ids, data = await _trades(limit=2, offset=10)
    assert ids == [] and data["total_trades"] == 3

    # A non-positive limit or a negative offset is the unbounded default.
    ids, data = await _trades(limit=0, offset=-3)
    assert ids == ["t-newest", "t-middle", "t-oldest"]
    assert (data["limit"], data["offset"]) == (None, 0)

    # Paging applies after the status filter, and the total is the filtered one.
    ids, data = await _trades(status="closed", limit=1)
    assert ids == ["t-newest"]
    assert (data["total_trades"], data["count"]) == (2, 1)


@pytest.mark.asyncio
async def test_bot_trades_status_filter_matches_stored_enum_values(
    authed_app, monkeypatch
):
    """The stored status is an enum with lower-case values; the filter must
    match it whatever spelling the caller sends, and emit the plain value."""
    from internal.domain.models import TradeStatusEnum

    _ = authed_app
    now = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    uow = _paged_uow(now)
    uow.trades.trades[0].status = TradeStatusEnum.CLOSED  # t-oldest
    uow.trades.trades[1].status = TradeStatusEnum.OPEN  # t-middle
    uow.trades.trades[2].status = TradeStatusEnum.CLOSED  # t-newest
    monkeypatch.setattr(records.db, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(records, "UnitOfWork", lambda _session: uow)

    for spelling in ("CLOSED", "closed", "Closed"):
        response = await _request(
            "GET", "/api/v1/bots/bot-records-1/trades", params={"status": spelling}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert [trade["trade_id"] for trade in data["trades"]] == [
            "t-newest",
            "t-oldest",
        ]
        assert data["total_trades"] == 2
        assert {trade["status"] for trade in data["trades"]} == {"closed"}

    response = await _request(
        "GET", "/api/v1/bots/bot-records-1/trades", params={"status": "open"}
    )
    assert [t["trade_id"] for t in response.json()["data"]["trades"]] == ["t-middle"]


def test_status_matches_compares_enum_values_and_strings():
    from internal.domain.models import TradeStatusEnum

    assert records._status_matches(TradeStatusEnum.CLOSED, "CLOSED")
    assert records._status_matches("CLOSED", "closed")
    assert records._status_matches(" closed ", "CLOSED")
    assert not records._status_matches(TradeStatusEnum.OPEN, "closed")
    assert not records._status_matches(None, "closed")


def test_newest_first_keeps_undated_rows_last_in_db_order():
    now = datetime(2026, 9, 26, 12, 0)
    rows = [
        SimpleNamespace(trade_id="u1", created_at=None),
        SimpleNamespace(trade_id="d1", created_at=now - timedelta(hours=1)),
        SimpleNamespace(trade_id="u2", created_at=None),
        SimpleNamespace(trade_id="d2", created_at=now),
    ]

    assert [r.trade_id for r in records._newest_first(rows)] == ["d2", "d1", "u1", "u2"]


# --- cointegrated pairs: the stored scan, statistics only ---------------------


@pytest.fixture
def pair_scan_store(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as connection:
        connection.execute(text(_COINTEGRATED_PAIRS_DDL))
    monkeypatch.setattr(records.db, "get_session", sessionmaker(bind=engine))
    uow = _sample_uow()
    # Account data on the bot row must never reach this route's response.
    uow.bots.bot.address = PLANTED_ADDRESS
    uow.bots.bot.mnemonic = PLANTED_MNEMONIC
    monkeypatch.setattr(records, "UnitOfWork", lambda _session: uow)
    return engine


def _store_scan(engine, instance_id, pairs, analyzed_at="2026-09-26 11:30:00"):
    """Insert a row the way PairStorage._db_save lays it out."""
    payload = {
        "timestamp": "2026-09-26T11:30:00.500000+00:00",
        "total_pairs": len(pairs),
        "high_confidence_pairs": 0,
        "pairs": pairs,
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO cointegrated_pairs "
                "(instance_id, pairs_json, pairs_count, high_confidence_count, "
                "analyzed_at) VALUES (:iid, :pj, :pc, :hc, :aa)"
            ),
            {
                "iid": instance_id,
                "pj": json.dumps(payload),
                "pc": len(pairs),
                "hc": 0,
                "aa": analyzed_at,
            },
        )


@pytest.mark.asyncio
async def test_cointegrated_pairs_route_reads_the_stored_scan(
    authed_app, pair_scan_store
):
    _ = authed_app
    _store_scan(
        pair_scan_store,
        "bot-records-1",
        [
            {
                # What CointegrationResult.to_dict() writes, extra fields included.
                "base_market": "BTC-USD",
                "quote_market": "ETH-USD",
                "hedge_ratio": 1.2,
                "half_life": 6.0,
                "zero_crossings": 8,
                "p_value": 0.01,
                "z_score_mean": 0.0,
                "z_score_std": 1.0,
                "analysis_timestamp": "2026-09-26T11:29:00+00:00",
                "confidence_score": 0.82,
                "creation_timestamp": "2026-09-26T11:30:00+00:00",
                "intercept": 0.5,
            },
            {
                # Unparseable statistics become null; the pair is still listed.
                "base_market": "SOL-USD",
                "quote_market": "AVAX-USD",
                "hedge_ratio": "n/a",
                "half_life": None,
                "zero_crossings": "3",
                "p_value": "NaN",
                "confidence_score": 0.2,
            },
            {"base_market": "", "quote_market": "ETH-USD", "hedge_ratio": 1.0},
            "not a pair",
        ],
    )
    _store_scan(
        pair_scan_store,
        "bot-records-2",
        [{"base_market": "XRP-USD", "quote_market": "DOGE-USD", "hedge_ratio": 1.0}],
    )

    response = await _request("GET", "/api/v1/bots/bot-records-1/cointegrated-pairs")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "instance_id": "bot-records-1",
        "analyzed_at": "2026-09-26T11:30:00+00:00",
        "count": 2,
        "pairs": [
            {
                "base_market": "BTC-USD",
                "quote_market": "ETH-USD",
                "hedge_ratio": 1.2,
                "half_life": 6.0,
                "zero_crossings": 8,
                "p_value": 0.01,
                "z_score_mean": 0.0,
                "z_score_std": 1.0,
                "confidence_score": 0.82,
                "analysis_timestamp": "2026-09-26T11:29:00+00:00",
            },
            {
                "base_market": "SOL-USD",
                "quote_market": "AVAX-USD",
                "hedge_ratio": None,
                "half_life": None,
                "zero_crossings": 3,
                "p_value": None,
                "z_score_mean": None,
                "z_score_std": None,
                "confidence_score": 0.2,
                "analysis_timestamp": None,
            },
        ],
    }
    body = response.text
    assert PLANTED_ADDRESS not in body and "mnemonic" not in body
    assert "XRP-USD" not in body  # another instance's scan


@pytest.mark.asyncio
async def test_cointegrated_pairs_failure_uses_the_global_500_envelope(
    authed_app, monkeypatch
):
    """The route has no catch-all; the app's handler answers with the envelope."""
    _ = authed_app

    def _raise_database_error():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(records.db, "get_session", _raise_database_error)

    response = await _request("GET", "/api/v1/bots/bot-records-1/cointegrated-pairs")

    assert response.status_code == 500
    assert response.json()["success"] is False
    assert response.json()["message"] == "Internal server error"
    # The global handler's envelope carries no trace_id (the trace context is
    # not visible at that outer layer), unlike the route-level catch-alls above.
    assert "database unavailable" not in response.text


@pytest.mark.asyncio
async def test_cointegrated_pairs_route_reports_no_scan_as_empty(
    authed_app, pair_scan_store
):
    _ = authed_app

    response = await _request("GET", "/api/v1/bots/bot-records-1/cointegrated-pairs")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "instance_id": "bot-records-1",
        "analyzed_at": None,
        "count": 0,
        "pairs": [],
    }


def test_iso_utc_normalises_naive_aware_and_textual_stamps():
    naive = datetime(2026, 9, 26, 11, 30)
    aware = datetime(2026, 9, 26, 13, 30, tzinfo=timezone(timedelta(hours=2)))

    assert records._iso_utc(naive) == "2026-09-26T11:30:00+00:00"
    assert records._iso_utc(aware) == "2026-09-26T11:30:00+00:00"
    assert records._iso_utc("2026-09-26 11:30:00") == "2026-09-26T11:30:00+00:00"
    assert records._iso_utc("last tuesday") == "last tuesday"
    assert records._iso_utc("  ") is None
    assert records._iso_utc(None) is None
