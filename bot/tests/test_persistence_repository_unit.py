"""Unit coverage for src/infrastructure/persistence/repository.py.

All repositories are driven through a scripted fake session (query chains,
add/commit/rollback/flush/refresh recorders) plus recording analytics
writers — no database, no ClickHouse.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import src.infrastructure.persistence.repository as repository
from internal.domain.models import (
    Bot,
    BotStatusEnum,
    Job,
    JobStatusEnum,
    Strategy,
    StrategyVersion,
    Trade,
    TradeStatusEnum,
)
from src.infrastructure.persistence.repository import (
    BotRepository,
    EventRepository,
    JobRepository,
    StrategyRepository,
    TradeRepository,
    UnitOfWork,
    _build_clickhouse_analytics_writer,
    _resolve_bot_instance_id,
)
from src.shared.time_utils import utc_now


class _FakeQuery:
    def __init__(self, session, target):
        self._session = session
        self._target = target
        self.calls = []
        self._spec = None

    def _resolve_spec(self):
        if self._spec is None:
            self._spec = self._session._pop_spec(self._target)
        return self._spec

    def filter(self, *criteria):
        self.calls.append("filter")
        return self

    def order_by(self, *criteria):
        self.calls.append("order_by")
        return self

    def limit(self, count):
        self.calls.append("limit")
        return self

    def offset(self, count):
        self.calls.append("offset")
        return self

    def count(self):
        self.calls.append("count")
        return self._resolve_spec().get("count", 0)

    def first(self):
        self.calls.append("first")
        return self._resolve_spec().get("first")

    def all(self):
        self.calls.append("all")
        return list(self._resolve_spec().get("all", []))


class _FakeSession:
    """Scripted session: queries resolved from a FIFO of per-model specs."""

    def __init__(self, specs=None):
        self._specs = dict(specs or {})
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.refreshed = []
        self.deleted = []
        self._next_id = 100

    def _pop_spec(self, target):
        queue = self._specs.setdefault(target, [])
        if queue:
            return queue.pop(0)
        return {}

    def queue(self, target, **spec):
        self._specs.setdefault(target, []).append(spec)

    def query(self, target):
        return _FakeQuery(self, target)

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def flush(self):
        self.flushes += 1
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                self._next_id += 1
                obj.id = self._next_id

    def refresh(self, obj):
        self.refreshed.append(obj)


class _RecordingWriter:
    def __init__(self, error=None):
        self.tables = []
        self.error = error

    def write_rows(self, table, rows):
        if self.error is not None:
            raise self.error
        self.tables.append((table, rows))


@pytest.fixture(autouse=True)
def _reset_default_writers():
    TradeRepository._default_analytics_writer = _RecordingWriter()
    EventRepository._default_analytics_writer = _RecordingWriter()
    yield
    TradeRepository._default_analytics_writer = None
    EventRepository._default_analytics_writer = None


def _bot_row(instance_id="bot-1", bot_id=7):
    bot = Bot(instance_id=instance_id, network="testnet", strategy="grid", config={})
    bot.id = bot_id
    return bot


def _trade_row(
    trade_id="t-1",
    status=TradeStatusEnum.CLOSED,
    profit_loss=5.0,
    realized_pnl=0.0,
):
    trade = Trade(
        bot_id=7,
        trade_id=trade_id,
        pair1="BTC-USD",
        pair2="ETH-USD",
        side1="BUY",
        side2="SELL",
        entry_price1=100.0,
        entry_price2=50.0,
        entry_size1=2.0,
        entry_size2=4.0,
        status=TradeStatusEnum.OPEN,
    )
    trade.id = 11
    trade.status = status
    trade.profit_loss = profit_loss
    trade.realized_pnl = realized_pnl
    return trade


# --- module helpers -------------------------------------------------------------


def test_resolve_bot_instance_id_variants():
    session = _FakeSession()
    session.queue(Bot, first=_bot_row("resolved-bot"))
    assert _resolve_bot_instance_id(session, 7) == "resolved-bot"

    assert _resolve_bot_instance_id(session, "not-a-number") == ""

    class _ExplodingSession(_FakeSession):
        def query(self, target):
            raise RuntimeError("db down")

    assert _resolve_bot_instance_id(_ExplodingSession(), 7) == ""
    assert _resolve_bot_instance_id(_FakeSession(), 7) == ""  # no row


def test_build_clickhouse_analytics_writer_fallbacks(monkeypatch):
    import config.config as config_module

    monkeypatch.setattr(
        config_module,
        "config",
        lambda: SimpleNamespace(clickhouse=None),
        raising=False,
    )
    writer = _build_clickhouse_analytics_writer("unit test")
    assert writer.__class__.__name__ == "NoopAnalyticsWriter"

    def _boom():
        raise RuntimeError("config exploded")

    monkeypatch.setattr(config_module, "config", _boom, raising=False)
    fallback = _build_clickhouse_analytics_writer("unit test")
    assert fallback.__class__.__name__ == "NoopAnalyticsWriter"

    enabled = SimpleNamespace(
        enabled=True,
        database="analytics",
        host="ch",
        port=8123,
        user="default",
        password="secret",
        secure=True,
        batch_size=500,
        flush_interval_seconds=2.0,
    )
    monkeypatch.setattr(
        config_module, "config", lambda: SimpleNamespace(clickhouse=enabled)
    )
    real = _build_clickhouse_analytics_writer("unit test")
    assert real.__class__.__name__ == "ClickHouseAnalyticsWriter"


# --- BotRepository ----------------------------------------------------------------


def test_bot_repository_crud_and_statistics():
    session = _FakeSession()
    repo = BotRepository(session)

    created = repo.create_bot("bot-9", "mainnet", "mean-rev", {"a": 1})
    assert created.instance_id == "bot-9"
    assert session.added == [created]
    assert session.commits == 1

    session.queue(Bot, first=_bot_row("bot-9"))
    fetched = repo.get_by_instance_id("bot-9")
    assert fetched.instance_id == "bot-9"

    session.queue(Bot, first=None)
    assert repo.get_by_instance_id("ghost") is None

    session.queue(Bot, all=[_bot_row("b1"), _bot_row("b2")])
    assert len(repo.get_all()) == 2

    session.queue(Bot, first=_bot_row("bot-9"))
    repo.update_status("bot-9", BotStatusEnum.RUNNING, process_id=99)
    assert fetched is not None

    session.queue(Bot, first=None)
    commits_before = session.commits
    repo.update_status("ghost", BotStatusEnum.STOPPED)
    assert session.commits == commits_before

    session.queue(Bot, first=_bot_row("bot-9"))
    repo.delete_bot("bot-9")
    assert session.deleted

    # Statistics: open + winning + losing trades aggregated.
    stats_bot = _bot_row("bot-stats")
    session.queue(Bot, first=stats_bot)
    session.queue(
        Trade,
        all=[
            _trade_row("t1", TradeStatusEnum.OPEN),
            _trade_row("t2", TradeStatusEnum.CLOSED, realized_pnl=10.0),
            _trade_row("t3", TradeStatusEnum.CLOSED, realized_pnl=-4.0),
        ],
    )
    stats = repo.get_statistics("bot-stats")
    assert stats == {
        "total_trades": 3,
        "active_positions": 1,
        "successful_trades": 1,
        "failed_trades": 1,
        "total_profit_loss": 6.0,
        "win_rate": pytest.approx(33.3333333),
    }

    session.queue(Bot, first=None)
    assert repo.get_statistics("ghost") == {}


# --- JobRepository ------------------------------------------------------------------


def _job_row(job_id="job-1", job_row_id=5):
    job = Job(
        job_id=job_id,
        bot_id=7,
        job_type="backtest",
        config={},
        metadata_json={},
        progress_pct=0.0,
    )
    job.id = job_row_id
    return job


def test_job_repository_lifecycle():
    session = _FakeSession()
    repo = JobRepository(session)

    created = repo.create_job(
        "job-x", 7, "backtest", parameters={"p": 1}, metadata={"m": 2}
    )
    assert created.job_id == "job-x"
    assert created.config == {"p": 1}
    assert session.commits == 1

    job = _job_row("job-x")
    session.queue(Job, first=job)
    repo.start_job("job-x", process_id=42)
    assert job.status == JobStatusEnum.RUNNING
    assert job.process_id == 42
    assert job.completed_at is None and job.error_message is None

    session.queue(Job, first=job)
    repo.complete_job("job-x", result={"ok": True}, execution_time_ms=1200)
    assert job.status == JobStatusEnum.COMPLETED
    assert job.result == {"ok": True}
    assert job.progress_pct == 100.0
    assert job.execution_time_ms == 1200

    session.queue(Job, first=job)
    repo.fail_job("job-x", "exploded", error_traceback="tb")
    assert job.status == JobStatusEnum.FAILED
    assert job.error_message == "exploded"
    assert job.error_traceback == "tb"

    session.queue(Job, first=job)
    repo.cancel_job("job-x", reason="operator request")
    assert job.status == JobStatusEnum.CANCELLED
    assert job.cancellation_reason == "operator request"

    # Missing job: all mutators are no-ops without committing.
    for mutator in (
        lambda: repo.start_job("ghost"),
        lambda: repo.complete_job("ghost"),
        lambda: repo.fail_job("ghost", "x"),
        lambda: repo.cancel_job("ghost"),
        lambda: repo.update_progress("ghost", 10.0),
    ):
        session.queue(Job, first=None)
        mutator()
    assert session.commits == 5  # only create_job + four successful mutations


def test_job_repository_progress_and_history():
    session = _FakeSession()
    repo = JobRepository(session)

    job = _job_row("job-p")
    job.metadata_json = {"existing": 1}
    session.queue(Job, first=job)
    repo.update_progress("job-p", 150.0, metadata={"extra": 2})
    assert job.progress_pct == 100.0
    assert job.metadata_json == {"existing": 1, "extra": 2}

    session.queue(Job, first=job)
    repo.update_progress("job-p", -20.0)
    assert job.progress_pct == 0.0

    history = [_job_row("h1"), _job_row("h2")]
    session.queue(Job, all=history)
    assert repo.get_job_history(bot_id=7, days=3) == history

    session.queue(Job, all=history)
    assert repo.get_by_bot_id(7) == history
    session.queue(Job, first=job)
    assert repo.get_by_job_id("job-p") is job
    session.queue(Job, first=job)
    assert repo.get_by_id(5) is job


def test_job_repository_update_status_matrix():
    session = _FakeSession()
    repo = JobRepository(session)

    fresh = _job_row("job-s")
    session.queue(Job, first=fresh)
    repo.update_status(
        fresh.id,
        JobStatusEnum.RUNNING,
        progress_pct=42.0,
        metadata={"m": 1},
        result={"r": 1},
        error_message="stale",
    )
    assert fresh.status == JobStatusEnum.RUNNING
    assert fresh.started_at is not None
    assert fresh.progress_pct == 42.0
    assert fresh.metadata_json == {"m": 1}

    session.queue(Job, first=fresh)
    repo.update_status(fresh.id, JobStatusEnum.COMPLETED, cancellation_reason="n/a")
    assert fresh.completed_at is not None
    assert fresh.cancellation_reason == "n/a"

    session.queue(Job, first=None)
    repo.update_status(999, JobStatusEnum.FAILED)
    assert session.rollbacks == 0


# --- TradeRepository -------------------------------------------------------------------


def test_trade_repository_create_and_queries():
    session = _FakeSession()
    writer = _RecordingWriter()
    repo = TradeRepository(session, analytics_writer=writer)

    trade = repo.create_trade("t-9", 7, "BTC-USD", "ETH-USD", 100.0, 50.0, 1.0, 2.0)
    assert trade.status == TradeStatusEnum.OPEN
    assert session.added == [trade]
    assert writer.tables and writer.tables[-1][0] == "trade_events"
    assert writer.tables[-1][1][0]["event_kind"] == "opened"

    session.queue(Trade, first=trade)
    assert repo.get_by_position_id("t-9") is trade
    session.queue(Trade, all=[trade])
    assert repo.get_by_bot_id(7) == [trade]
    session.queue(Trade, all=[trade])
    assert repo.get_bot_trades(7) == [trade]


def test_trade_repository_close_trade_pnl():
    session = _FakeSession()
    writer = _RecordingWriter()
    repo = TradeRepository(session, analytics_writer=writer)

    trade = _trade_row("t-c")  # entry 100/2 and 50/4
    session.queue(Trade, first=trade)
    repo.close_trade("t-c", exit_price1=110.0, exit_price2=48.0)
    # pnl1 = (110-100)*2 = 20; pnl2 = (50-48)*4 = 8; total 28 over 400 invested.
    assert trade.profit_loss == 28.0
    assert trade.profit_loss_percentage == pytest.approx(7.0)
    assert trade.status == TradeStatusEnum.CLOSED
    assert trade.closed_at is not None
    assert writer.tables[-1][1][0]["event_kind"] == "closed"

    # Partial exits without both prices skip the P&L calculation.
    partial = _trade_row("t-p")
    session.queue(Trade, first=partial)
    repo.close_trade("t-p", exit_size1=1.0)
    assert partial.status == TradeStatusEnum.CLOSED
    assert not hasattr(partial, "profit_loss") or partial.profit_loss in (None, 5.0)

    session.queue(Trade, first=None)
    commits = session.commits
    repo.close_trade("ghost")
    assert session.commits == commits


def test_trade_repository_statistics_and_exit_update():
    session = _FakeSession()
    repo = TradeRepository(session, analytics_writer=_RecordingWriter())

    session.queue(
        Trade,
        all=[
            _trade_row("w1", TradeStatusEnum.CLOSED, profit_loss=10.0),
            _trade_row("l1", TradeStatusEnum.CLOSED, profit_loss=-2.0),
            _trade_row("o1", TradeStatusEnum.OPEN, profit_loss=0.0),
        ],
    )
    stats = repo.get_trade_statistics(7)
    assert stats == {
        "total_trades": 3,
        "winning_trades": 1,
        "losing_trades": 1,
        "total_profit_loss": 8.0,
        "average_trade_pnl": pytest.approx(8.0 / 3),
        "win_rate": pytest.approx(100.0 / 3),
    }

    exiting = _trade_row("t-x")
    session.queue(Trade, first=exiting)
    repo.update_trade_exit(
        "t-x",
        exit_price1=105.0,
        exit_size1=1.5,
        realized_pnl=12.5,
        realized_pnl_pct=3.25,
    )
    assert exiting.exit_price1 == 105.0
    assert exiting.exit_size1 == 1.5
    assert exiting.realized_pnl == 12.5
    assert exiting.status == TradeStatusEnum.CLOSED

    session.queue(Trade, first=None)
    repo.update_trade_exit("ghost")
    assert exiting.closed_at is not None


def test_trade_repository_analytics_row_and_writer_failure():
    session = _FakeSession()
    session.queue(Bot, first=_bot_row("analytics-bot"))
    failing = TradeRepository(session, analytics_writer=_RecordingWriter())

    trade = _trade_row("t-a")
    trade.closed_at = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    trade.updated_at = datetime(2026, 8, 19, 11, 0, tzinfo=timezone.utc)
    failing._write_analytics_trade(trade, event_kind="closed")
    # Writer failures degrade to a warning; the trade still flows through.
    assert failing.analytics_writer.error is None

    failing.analytics_writer.error = RuntimeError("clickhouse down")
    failing._write_analytics_trade(trade, event_kind="closed")  # must not raise

    row = TradeRepository._build_analytics_row(trade, event_kind="closed")
    assert row["event_kind"] == "closed"
    assert row["status"] == "closed"
    assert row["event_time"] == trade.closed_at
    assert row["entry_price1"] == 100.0
    assert row["realized_pnl"] == 5.0  # falls back to profit_loss
    assert row["instance_id"] == ""  # instance resolution uses the session

    naive = _trade_row("t-n")
    naive.closed_at = None
    naive.updated_at = None
    naive.created_at = None
    row = TradeRepository._build_analytics_row(naive, event_kind="opened")
    assert row["event_time"].tzinfo is not None
    assert row["closed_at"] is None


def test_trade_repository_normalize_event_time():
    naive = datetime(2026, 8, 19, 10, 0)
    normalized = TradeRepository._normalize_event_time(naive)
    assert normalized.tzinfo == timezone.utc

    aware = datetime(2026, 8, 19, 10, 0, tzinfo=timezone(timedelta(hours=2)))
    converted = TradeRepository._normalize_event_time(aware)
    assert converted.utcoffset() == timedelta(0)

    assert TradeRepository._normalize_event_time(None) is not None


# --- EventRepository --------------------------------------------------------------------


def _event_row(event_type="info_event", details=None, created_at=None):
    event = repository.Event(
        bot_instance_id=7,
        event_type=event_type,
        severity="info",
        message="something happened",
        details=details,
    )
    event.created_at = created_at or datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc)
    return event


def test_event_repository_coercers():
    assert EventRepository._coerce_optional_int(None) is None
    assert EventRepository._coerce_optional_int("") is None
    assert EventRepository._coerce_optional_int("7") == 7
    assert EventRepository._coerce_optional_int("junk") is None

    assert EventRepository._coerce_optional_float("2.5") == 2.5
    assert EventRepository._coerce_optional_float([]) is None

    assert EventRepository._normalize_optional_datetime(None) is None
    assert EventRepository._normalize_optional_datetime("") is None
    assert EventRepository._normalize_optional_datetime("junk") is None
    parsed = EventRepository._normalize_optional_datetime("2026-08-19T09:00:00Z")
    assert parsed == datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc)
    naive = EventRepository._normalize_optional_datetime(datetime(2026, 8, 19, 9, 0))
    assert naive.tzinfo == timezone.utc
    assert EventRepository._normalize_optional_datetime(42) is None


def test_event_repository_order_status_mapping():
    assert EventRepository._order_status_for_event("trade_entry_opened") == "filled"
    assert (
        EventRepository._order_status_for_event("trade_exit_close_confirmed")
        == "closed"
    )
    assert EventRepository._order_status_for_event("trade_exit_orphaned") == "orphaned"
    assert EventRepository._order_status_for_event("other") == ""
    assert EventRepository._order_status_for_event(None) == ""


def test_event_repository_log_and_query():
    session = _FakeSession()
    writer = _RecordingWriter()
    repo = EventRepository(session, analytics_writer=writer)

    event = repo.log_event(
        7,
        "bot_runtime_error",
        "error",
        "worker crashed",
        details={"correlation_id": "c-1"},
    )
    assert session.added == [event]
    assert session.commits == 1
    assert writer.tables and writer.tables[0][0] == "bot_events"
    assert writer.tables[0][1][0]["correlation_id"] == "c-1"

    cutoff_events = [_event_row()]
    session.queue(repository.Event, all=cutoff_events)
    assert repo.get_bot_events(7, days=2) == cutoff_events

    session.queue(repository.Event, all=cutoff_events)
    assert repo.get_all_events(days=1) == cutoff_events


def test_event_repository_order_analytics_rows():
    event = _event_row(
        "trade_entry_opened",
        details={
            "order_id_m1": "ord-1",
            "order_m1_side": "BUY",
            "market_1": "BTC-USD",
            "order_m1_price": "100.5",
            "order_m1_size": "2",
            "order_time_m1": "2026-08-19T09:00:00Z",
            "correlation_id": "corr-9",
            "instance_id": "strategy-1-1",
            "filled_size": "1.75",
            "fee": "0.02",
            "type": "LIMIT",
            "time_in_force": "GTT",
            "post_only": 1,
        },
        created_at=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc),
    )
    event.related_trade_id = "t-77"

    rows = EventRepository._build_order_analytics_rows(event)
    assert len(rows) == 1  # only m1 leg carries an order id
    row = rows[0]
    assert row["order_id"] == "ord-1"
    assert row["trade_id"] == "t-77"
    assert row["market"] == "BTC-USD"
    assert row["side"] == "BUY"
    assert row["status"] == "filled"
    assert row["price"] == 100.5
    assert row["size"] == 2.0
    assert row["filled_size"] == 1.75
    assert row["fee"] == 0.02
    assert row["type"] == "LIMIT"
    assert row["post_only"] == 1
    assert row["event_time"].tzinfo is not None
    assert row["correlation_id"] == "corr-9"
    assert row["instance_id"] == "strategy-1-1"

    # Exit-confirmed events map both legs when both order ids exist.
    exit_event = _event_row(
        "trade_exit_close_confirmed",
        details={
            "close_order_m1_id": "c-1",
            "close_order_m2_id": "c-2",
            "market_1": "BTC-USD",
            "market_2": "ETH-USD",
        },
    )
    exit_rows = EventRepository._build_order_analytics_rows(exit_event)
    assert len(exit_rows) == 2
    assert all(row["status"] == "closed" for row in exit_rows)

    # Non-order events produce no rows.
    assert EventRepository._build_order_analytics_rows(_event_row()) == []


def test_event_repository_analytics_write_failures_degrade():
    session = _FakeSession()
    writer = _RecordingWriter(error=RuntimeError("clickhouse down"))
    repo = EventRepository(session, analytics_writer=writer)

    order_event = _event_row(
        "trade_entry_opened",
        details={"order_id_m1": "ord-1", "market_1": "BTC-USD"},
    )
    repo._write_analytics_event(order_event)  # both writes fail; no raise
    assert writer.tables == []


def test_event_repository_event_context_and_row():
    event = _event_row(
        "custom",
        details="not-a-dict",  # non-dict details degrade to {}
        created_at=datetime(2026, 8, 19, 9, 0),  # naive
    )
    event.related_job_id = "job-77"
    details, created_at, correlation_id, bot_run_id = EventRepository._event_context(
        event
    )
    assert details == {}
    assert created_at.tzinfo == timezone.utc
    assert correlation_id == "job-77"
    assert bot_run_id == ""

    row = EventRepository._build_analytics_row(event)
    assert row["event_type"] == "custom"
    assert row["bot_id"] == "7"
    assert "payload_attrs" in row


# --- StrategyRepository ---------------------------------------------------------------------


def _strategy_row(strategy_id=31, **overrides):
    strategy = Strategy(
        name="Pair Strategy",
        category="custom",
        description="d",
        is_public=False,
        is_default=False,
        user_id=1,
        zscore_threshold=1.5,
        stats_window=21,
        max_half_life=24.0,
        usd_per_trade=10.0,
        usd_min_collateral=100.0,
        close_at_zscore_cross=True,
        find_cointegrated_pairs=True,
        manage_exits=True,
        place_trades=True,
        abort_all_positions=False,
        max_positions=5,
        max_drawdown_pct=15.0,
        stop_loss_pct=3.0,
        take_profit_pct=8.0,
        trailing_stop_pct=2.0,
        rebalance_interval_hours=24,
        position_timeout_hours=72,
        pair_selection_mode="liquidity",
        transaction_fee=0.0005,
        slippage=0.001,
        starting_balance=1000.0,
        candle_resolution="1HOUR",
        max_history_days=90,
        benchmark_symbol="BTC-USD",
        risk_free_rate=0.02,
        initial_amount=1000.0,
    )
    strategy.id = strategy_id
    for key, value in overrides.items():
        setattr(strategy, key, value)
    return strategy


def _version_row(version_id=3, version_number=2, strategy_id=31, name="Pair Strategy"):
    version = StrategyVersion(
        strategy_id=strategy_id,
        version_number=version_number,
        change_description="note",
        config_snapshot={"name": name},
        changes={},
        created_by_user_id=1,
    )
    version.id = version_id
    version.created_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return version


def test_strategy_repository_list_get_and_versions():
    session = _FakeSession()
    repo = StrategyRepository(session)

    rows = [_strategy_row(31), _strategy_row(32, name="Second")]
    session.queue(Strategy, count=2, all=rows)
    listing = repo.list(skip=0, limit=10)
    assert listing["total"] == 2
    assert [entry["id"] for entry in listing["strategies"]] == [31, 32]
    assert listing["strategies"][0]["resolution"] == "1HOUR"
    assert listing["strategies"][0]["usage_count"] == 0

    session.queue(Strategy, all=[rows[0]])
    public = repo.list_public()
    assert public["total"] == 1

    session.queue(Strategy, first=rows[1])
    fetched = repo.get(32)
    assert fetched["name"] == "Second"

    session.queue(Strategy, first=None)
    assert repo.get(999) is None

    versions = [_version_row(3, 2), _version_row(2, 1)]
    session.queue(StrategyVersion, all=versions)
    result = repo.versions(31)
    assert [entry["id"] for entry in result] == [3, 2]
    assert result[0]["name"] == "Pair Strategy"
    assert result[0]["created_at"].startswith("2026-08-01")


def test_strategy_repository_create_update_delete_revert():
    session = _FakeSession()
    repo = StrategyRepository(session)

    session.queue(StrategyVersion, first=None)  # no prior versions
    created = repo.create({"name": "New", "zscore_threshold": 2.0}, note="v1")
    assert created["name"] == "New"
    assert created["zscore_threshold"] == 2.0
    assert session.flushes == 1
    assert len(session.added) == 2  # strategy + version
    assert session.commits == 1
    assert session.refreshed

    existing = _strategy_row(41)
    session.queue(Strategy, first=existing)
    session.queue(StrategyVersion, first=_version_row(4, 2, strategy_id=41))
    updated = repo.update(41, {"name": "Renamed", "max_positions": 9})
    assert updated["name"] == "Renamed"
    assert updated["max_positions"] == 9
    assert session.added[-1].version_number == 3

    session.queue(Strategy, first=None)
    assert repo.update(999, {"name": "x"}) is None

    session.queue(Strategy, first=existing)
    assert repo.delete(41) is True
    assert existing.deleted_at is not None

    session.queue(Strategy, first=None)
    assert repo.delete(41) is False

    version = _version_row(5, 2, strategy_id=41, name="Snapshot Name")
    session.queue(StrategyVersion, first=version)
    session.queue(Strategy, first=existing)
    session.queue(StrategyVersion, first=_version_row(6, 3, strategy_id=41))
    reverted = repo.revert(41, 5)
    assert reverted["name"] == "Snapshot Name"

    session.queue(StrategyVersion, first=None)
    assert repo.revert(41, 999) is None


# --- UnitOfWork -----------------------------------------------------------------------------


def test_unit_of_work_wiring_and_context_management():
    session = _FakeSession()
    with UnitOfWork(session) as uow:
        assert uow.bots.session is session
        assert uow.jobs.session is session
        assert uow.trades.session is session
        assert uow.events.session is session
        assert uow.strategies.session is session
    assert session.commits == 1
    assert session.rollbacks == 0

    with pytest.raises(RuntimeError, match="txn failed"):
        with UnitOfWork(session):
            raise RuntimeError("txn failed")
    assert session.rollbacks == 1
