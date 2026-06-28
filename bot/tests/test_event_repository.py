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
