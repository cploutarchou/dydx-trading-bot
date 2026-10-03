from __future__ import annotations

from src.infrastructure.persistence.repository import TradeRepository
from src.infrastructure.storage.analytics import AnalyticsWriter


class _RecordingAnalyticsWriter(AnalyticsWriter):
    def __init__(self):
        self.calls: list[tuple[str, list[dict[str, object]]]] = []

    def write_rows(self, table_name: str, rows):
        materialized = [dict(row) for row in rows]
        self.calls.append((table_name, materialized))
        return len(materialized)


class _FakeQuery:
    def __init__(self, session: "_FakeSession", model):
        self._session = session
        self._model = model

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        if getattr(self._model, "__name__", "") == "Bot":
            return self._session.bot
        return self._session.trade


class _FakeSession:
    def __init__(self):
        self.trade = None
        self.bot = type("BotRecord", (), {"instance_id": "strategy-1-101"})()
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)
        self.trade = value

    def commit(self) -> None:
        self.commits += 1

    def query(self, model):
        return _FakeQuery(self, model)


def test_trade_repository_mirrors_opened_and_closed_trades_to_trade_events():
    session = _FakeSession()
    analytics_writer = _RecordingAnalyticsWriter()
    repository = TradeRepository(session, analytics_writer=analytics_writer)

    trade = repository.create_trade(
        trade_id="live-abc123",
        bot_id=77,
        pair1="BTC-USD",
        pair2="ETH-USD",
        entry_price1=100000.0,
        entry_price2=3000.0,
        entry_size1=0.1,
        entry_size2=2.0,
        side1="BUY",
        side2="SELL",
    )
    repository.update_trade_exit(
        "live-abc123",
        exit_price1=101000.0,
        exit_price2=2900.0,
        exit_size1=0.1,
        exit_size2=2.0,
        realized_pnl=300.5,
        realized_pnl_pct=1.75,
    )

    assert session.commits == 2
    assert session.added == [trade]
    assert len(analytics_writer.calls) == 2

    opened_table, opened_rows = analytics_writer.calls[0]
    assert opened_table == "trade_events"
    assert len(opened_rows) == 1
    opened_row = opened_rows[0]
    assert opened_row["trade_id"] == "live-abc123"
    assert opened_row["bot_id"] == "77"
    assert opened_row["instance_id"] == "strategy-1-101"
    assert opened_row["pair1"] == "BTC-USD"
    assert opened_row["pair2"] == "ETH-USD"
    assert opened_row["event_kind"] == "opened"
    assert opened_row["status"] == "open"
    assert opened_row["closed_at"] is None

    closed_table, closed_rows = analytics_writer.calls[1]
    assert closed_table == "trade_events"
    assert len(closed_rows) == 1
    closed_row = closed_rows[0]
    assert closed_row["trade_id"] == "live-abc123"
    assert closed_row["instance_id"] == "strategy-1-101"
    assert closed_row["event_kind"] == "closed"
    assert closed_row["status"] == "closed"
    assert closed_row["exit_price1"] == 101000.0
    assert closed_row["exit_price2"] == 2900.0
    assert closed_row["realized_pnl"] == 300.5
    assert closed_row["realized_pnl_pct"] == 1.75
    assert closed_row["closed_at"] is not None


def _opened_trade_repository():
    session = _FakeSession()
    repository = TradeRepository(session, analytics_writer=_RecordingAnalyticsWriter())
    repository.create_trade(
        trade_id="live-pnl-1",
        bot_id=77,
        pair1="BTC-USD",
        pair2="ETH-USD",
        entry_price1=100.0,
        entry_price2=50.0,
        entry_size1=2.0,
        entry_size2=4.0,
        side1="BUY",
        side2="SELL",
    )
    return session, repository


def test_update_trade_exit_feeds_the_columns_the_statistics_read():
    session, repository = _opened_trade_repository()

    repository.update_trade_exit(
        "live-pnl-1",
        exit_price1=110.0,
        exit_price2=45.0,
        exit_size1=2.0,
        exit_size2=4.0,
        realized_pnl=39.8,
        realized_pnl_pct=9.95,
    )

    trade = session.trade
    assert trade.realized_pnl == 39.8
    assert trade.profit_loss == 39.8
    assert trade.realized_pnl_pct == 9.95
    assert trade.profit_loss_percentage == 9.95


def test_update_trade_exit_without_pnl_does_not_record_a_false_zero():
    session, repository = _opened_trade_repository()
    session.trade.realized_pnl = None
    session.trade.profit_loss = None

    repository.update_trade_exit(
        "live-pnl-1",
        exit_price1=110.0,
        exit_price2=45.0,
        exit_size1=2.0,
        exit_size2=4.0,
    )

    assert session.trade.realized_pnl is None
    assert session.trade.profit_loss is None
