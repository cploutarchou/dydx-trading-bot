import json

from src.infrastructure.persistence.repository import EventRepository
from src.infrastructure.storage.analytics import AnalyticsWriter


class _RecordingAnalyticsWriter(AnalyticsWriter):
    def __init__(self):
        self.calls: list[tuple[str, list[dict[str, object]]]] = []

    def write_rows(self, table_name: str, rows):
        materialized = [dict(row) for row in rows]
        self.calls.append((table_name, materialized))
        return len(materialized)


class _FakeSession:
    def __init__(self):
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1


def test_event_repository_mirrors_logged_events_to_bot_events_clickhouse_rows():
    session = _FakeSession()
    analytics_writer = _RecordingAnalyticsWriter()
    repository = EventRepository(session, analytics_writer=analytics_writer)

    event = repository.log_event(
        bot_instance_id=77,
        event_type="bot_started",
        severity="info",
        message="Bot started successfully",
        details={
            "instance_id": "strategy-1-101",
            "status": "running",
            "correlation_id": "corr-123",
            "strategy_id": "42",
            "bot_run_id": "run-abc",
        },
        user_id="operator-7",
        related_job_id="job-99",
        related_trade_id="trade-88",
    )

    assert session.commits == 1
    assert session.added == [event]
    assert len(analytics_writer.calls) == 1

    table_name, rows = analytics_writer.calls[0]
    assert table_name == "bot_events"
    assert len(rows) == 1
    row = rows[0]
    payload_attrs = json.loads(str(row["payload_attrs"]))

    assert row["bot_id"] == "77"
    assert row["bot_run_id"] == "run-abc"
    assert row["event_type"] == "bot_started"
    assert row["status"] == "running"
    assert row["strategy_id"] == 42
    assert row["worker_id"] == "strategy-1-101"
    assert row["correlation_id"] == "corr-123"
    assert payload_attrs["message"] == "Bot started successfully"
    assert payload_attrs["related_trade_id"] == "trade-88"
    assert payload_attrs["details"]["instance_id"] == "strategy-1-101"


def test_event_repository_mirrors_trade_lifecycle_orders_to_order_events():
    session = _FakeSession()
    analytics_writer = _RecordingAnalyticsWriter()
    repository = EventRepository(session, analytics_writer=analytics_writer)

    event = repository.log_event(
        bot_instance_id=77,
        event_type="trade_entry_opened",
        severity="info",
        message="Opened live trade for BTC-USD / ETH-USD",
        details={
            "instance_id": "strategy-1-101",
            "correlation_id": "corr-order-1",
            "bot_run_id": "run-abc",
            "market_1": "BTC-USD",
            "market_2": "ETH-USD",
            "order_id_m1": "entry-1",
            "order_id_m2": "entry-2",
            "order_m1_side": "BUY",
            "order_m2_side": "SELL",
            "order_m1_price": 100000.0,
            "order_m2_price": 3000.0,
            "order_m1_size": 0.1,
            "order_m2_size": 2.0,
            "order_time_m1": "2026-01-01T00:00:01+00:00",
            "order_time_m2": "2026-01-01T00:00:02+00:00",
        },
        related_trade_id="live-abc123",
    )

    assert session.commits == 1
    assert session.added == [event]
    assert len(analytics_writer.calls) == 2

    bot_table, bot_rows = analytics_writer.calls[0]
    assert bot_table == "bot_events"
    assert len(bot_rows) == 1

    order_table, order_rows = analytics_writer.calls[1]
    assert order_table == "order_events"
    assert len(order_rows) == 2
    first_row = order_rows[0]
    second_row = order_rows[1]

    assert first_row["order_id"] == "entry-1"
    assert first_row["trade_id"] == "live-abc123"
    assert first_row["bot_id"] == "77"
    assert first_row["instance_id"] == "strategy-1-101"
    assert first_row["bot_run_id"] == "run-abc"
    assert first_row["market"] == "BTC-USD"
    assert first_row["side"] == "BUY"
    assert first_row["status"] == "filled"
    assert first_row["event_type"] == "trade_entry_opened"
    assert first_row["price"] == 100000.0
    assert first_row["size"] == 0.1
    assert str(first_row["exchange_time"]) == "2026-01-01 00:00:01+00:00"
    assert first_row["correlation_id"] == "corr-order-1"

    assert second_row["order_id"] == "entry-2"
    assert second_row["instance_id"] == "strategy-1-101"
    assert second_row["market"] == "ETH-USD"
    assert second_row["side"] == "SELL"
    assert second_row["status"] == "filled"
