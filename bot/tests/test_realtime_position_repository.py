from __future__ import annotations

from src.infrastructure.persistence.repository_realtime import PositionRepository
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
        return self._session.position


class _FakeSession:
    def __init__(self):
        self.position = None
        self.bot = type("BotRecord", (), {"instance_id": "strategy-1-101"})()
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)
        self.position = value

    def commit(self) -> None:
        self.commits += 1

    def query(self, model):
        return _FakeQuery(self, model)


def test_position_repository_mirrors_open_update_and_close_snapshots():
    session = _FakeSession()
    analytics_writer = _RecordingAnalyticsWriter()
    repository = PositionRepository(session, analytics_writer=analytics_writer)

    position = repository.create_position(
        bot_instance_id=77,
        position_id="live-pos-1",
        pair1="BTC-USD",
        pair2="ETH-USD",
        side1="BUY",
        side2="SELL",
        entry_price1=100.0,
        entry_price2=50.0,
        entry_size1=2.0,
        entry_size2=3.0,
        z_score_entry=2.1,
        hedge_ratio=0.6,
        correlation=0.9,
        half_life=12.0,
    )
    repository.update_position_prices(
        "live-pos-1",
        current_price1=110.0,
        current_price2=45.0,
        z_score_current=0.8,
        funding_rate=0.001,
    )
    repository.close_position("live-pos-1")

    assert session.commits == 3
    assert session.added == [position]
    assert len(analytics_writer.calls) == 3

    opened_table, opened_rows = analytics_writer.calls[0]
    assert opened_table == "position_snapshots"
    assert opened_rows[0]["position_id"] == "live-pos-1"
    assert opened_rows[0]["bot_id"] == "77"
    assert opened_rows[0]["instance_id"] == "strategy-1-101"
    assert opened_rows[0]["event_kind"] == "opened"
    assert opened_rows[0]["status"] == "open"
    assert opened_rows[0]["z_score_entry"] == 2.1
    assert opened_rows[0]["hedge_ratio"] == 0.6
    assert opened_rows[0]["closed_at"] is None

    updated_table, updated_rows = analytics_writer.calls[1]
    assert updated_table == "position_snapshots"
    assert updated_rows[0]["event_kind"] == "mark_to_market"
    assert updated_rows[0]["instance_id"] == "strategy-1-101"
    assert updated_rows[0]["current_price1"] == 110.0
    assert updated_rows[0]["current_price2"] == 45.0
    assert updated_rows[0]["current_size1"] == 2.0
    assert updated_rows[0]["current_size2"] == 3.0
    assert updated_rows[0]["unrealized_pnl"] == 35.0
    assert updated_rows[0]["unrealized_pnl_pct"] == 10.0
    assert updated_rows[0]["z_score_current"] == 0.8
    assert updated_rows[0]["funding_rate"] == 0.001

    closed_table, closed_rows = analytics_writer.calls[2]
    assert closed_table == "position_snapshots"
    assert closed_rows[0]["event_kind"] == "closed"
    assert closed_rows[0]["instance_id"] == "strategy-1-101"
    assert closed_rows[0]["status"] == "closed"
    assert closed_rows[0]["closed_at"] is not None
