import json
from datetime import datetime, timezone

from internal.domain import Base
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.storage.analytics import AnalyticsWriter
from src.infrastructure.storage.artifacts import ArtifactStore


class _RecordingArtifactStore(ArtifactStore):
    def __init__(self):
        self._payloads: dict[str, bytes] = {}

    def reference_for(self, key: str) -> str:
        return f"artifact://{key}"

    def put_bytes(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> str:
        del content_type
        self._payloads[key] = bytes(data)
        return self.reference_for(key)

    def read_bytes(self, key: str) -> bytes:
        return self._payloads[key]

    def exists(self, key: str) -> bool:
        return key in self._payloads

    def read_json(self, key: str):
        return json.loads(self.read_bytes(key).decode("utf-8"))


class _RecordingAnalyticsWriter(AnalyticsWriter):
    def __init__(self):
        self.calls: list[tuple[str, list[dict[str, object]]]] = []

    def write_rows(self, table_name: str, rows):
        materialized = [dict(row) for row in rows]
        self.calls.append((table_name, materialized))
        return len(materialized)


class _MariaDbRecordChanged(Exception):
    args = (1020, "Record has changed since last read in table 'backtest_runtime_runs'")

    def __str__(self) -> str:
        return self.args[1]


def test_save_run_rolls_back_and_retries_mariadb_record_changed(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'runs.sqlite'}", future=True)
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_local()
    real_commit = session.commit
    real_rollback = session.rollback
    calls = {"commit": 0}
    rollbacks = {"count": 0}

    def flaky_commit():
        calls["commit"] += 1
        if calls["commit"] == 1:
            raise OperationalError(
                "UPDATE backtest_runtime_runs", {}, _MariaDbRecordChanged()
            )
        return real_commit()

    def tracked_rollback():
        rollbacks["count"] += 1
        return real_rollback()

    monkeypatch.setattr(session, "commit", flaky_commit)
    monkeypatch.setattr(session, "rollback", tracked_rollback)
    repository = BacktestRepository(session)

    persisted = repository.save_run(
        {
            "run_id": "run-retry-1020",
            "name": "retry",
            "status": "running",
            "progress_pct": 12.5,
            "current_pair": "BTC-USD/ETH-USD",
            "current_task": "processing pair",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "request": {"pairs": ["BTC-USD", "ETH-USD"]},
        }
    )

    assert persisted["run_id"] == "run-retry-1020"
    assert persisted["status"] == "running"
    assert calls["commit"] == 2
    assert rollbacks["count"] == 1
    assert repository.get_run("run-retry-1020")["current_task"] == "processing pair"

    session.close()


def test_list_run_overviews_uses_one_query_and_omits_heavy_results(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'monitor.sqlite'}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    repository = BacktestRepository(session)

    for index in range(3):
        repository.save_run(
            {
                "run_id": f"run-monitor-{index}",
                "name": f"monitor-{index}",
                "status": "running",
                "request": {"strategy_id": index, "pairs": ["BTC-USD/ETH-USD"]},
                "trades": [{"trade_id": f"trade-{index}"}],
                "position_snapshots": [{"position_id": f"position-{index}"}],
                "daily_pnl": [{"date": "2026-01-01", "pnl": index}],
            }
        )

    statements = []

    def record_statement(*args):
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        overviews = repository.list_run_overviews(limit=None, offset=0)
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    assert len(overviews) == 3
    assert len(statements) == 1
    assert overviews[0]["request"]["pairs"] == ["BTC-USD/ETH-USD"]
    assert "trades" not in overviews[0]
    assert "position_snapshots" not in overviews[0]
    assert "daily_pnl" not in overviews[0]

    session.close()


def test_update_run_progress_preserves_heavy_result_payloads(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'progress.sqlite'}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    repository = BacktestRepository(session)
    repository.save_run(
        {
            "run_id": "run-progress",
            "name": "progress",
            "status": "running",
            "request": {"pairs": ["BTC-USD/ETH-USD"]},
            "trades": [{"trade_id": "trade-1"}],
            "position_snapshots": [{"position_id": "position-1"}],
            "daily_pnl": [{"date": "2026-01-01", "pnl": 1.25}],
        }
    )

    updated = repository.update_run_progress(
        {
            "run_id": "run-progress",
            "status": "running",
            "progress_pct": 42.5,
            "current_pair": "BTC-USD/ETH-USD",
            "current_task": "processing pair",
            "total_pnl": 1.25,
            "total_trades": 1,
        }
    )
    persisted = repository.get_run("run-progress")

    assert updated is True
    assert persisted is not None
    assert persisted["progress_pct"] == 42.5
    assert persisted["current_task"] == "processing pair"
    assert persisted["trades"] == [{"trade_id": "trade-1"}]
    assert persisted["position_snapshots"] == [{"position_id": "position-1"}]
    assert persisted["daily_pnl"] == [{"date": "2026-01-01", "pnl": 1.25}]

    session.close()


def test_update_run_progress_can_mark_failed_without_rewriting_results(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'failed-progress.sqlite'}", future=True
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    repository = BacktestRepository(session)
    repository.save_run(
        {
            "run_id": "run-failed-progress",
            "name": "failed-progress",
            "status": "running",
            "request": {"pairs": ["BTC-USD/ETH-USD"]},
            "trades": [{"trade_id": "trade-heavy"}],
            "position_snapshots": [{"position_id": "position-heavy"}],
            "daily_pnl": [{"date": "2026-01-01", "pnl": 2.5}],
        }
    )

    updated = repository.update_run_progress(
        {
            "run_id": "run-failed-progress",
            "status": "failed",
            "current_task": "failed",
            "error": "Lost connection to MySQL server during query",
            "error_message": "Lost connection to MySQL server during query",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "request": {
                "pairs": ["BTC-USD/ETH-USD"],
                "_runtime_control": {"status": "failed", "action": "fail"},
            },
        }
    )
    persisted = repository.get_run("run-failed-progress")

    assert updated is True
    assert persisted is not None
    assert persisted["status"] == "failed"
    assert persisted["current_task"] == "failed"
    assert persisted["error"] == "Lost connection to MySQL server during query"
    assert persisted["error_message"] == "Lost connection to MySQL server during query"
    assert persisted["completed_at"] is not None
    assert persisted["trades"] == [{"trade_id": "trade-heavy"}]
    assert persisted["position_snapshots"] == [{"position_id": "position-heavy"}]
    assert persisted["daily_pnl"] == [{"date": "2026-01-01", "pnl": 2.5}]

    session.close()


def test_save_run_writes_backtest_sidecars_and_analytics(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sidecars.sqlite'}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    artifact_store = _RecordingArtifactStore()
    analytics_writer = _RecordingAnalyticsWriter()
    repository = BacktestRepository(
        session,
        artifact_store=artifact_store,
        analytics_writer=analytics_writer,
    )

    persisted = repository.save_run(
        {
            "run_id": "run-sidecars",
            "name": "sidecars",
            "status": "completed",
            "request": {"pairs": ["BTC-USD/ETH-USD"], "start_date": "2026-04-01"},
            "trades": [{"trade_id": "trade-1", "pnl": 12.5}],
            "position_snapshots": [{"snapshot_id": "position-1"}],
            "daily_pnl": [{"date": "2026-04-01", "pnl": 12.5}],
        }
    )

    assert persisted["artifact_refs"]["run_root"] == "artifact://backtests/run-sidecars"
    assert artifact_store.read_json("backtests/run-sidecars/request.json")["pairs"] == [
        "BTC-USD/ETH-USD"
    ]
    assert artifact_store.read_json("backtests/run-sidecars/trades.json") == [
        {"trade_id": "trade-1", "pnl": 12.5}
    ]
    assert artifact_store.read_json(
        "backtests/run-sidecars/position_snapshots.json"
    ) == [{"snapshot_id": "position-1"}]
    assert artifact_store.read_json("backtests/run-sidecars/daily_pnl.json") == [
        {"date": "2026-04-01", "pnl": 12.5}
    ]

    assert [call[0] for call in analytics_writer.calls] == [
        "backtest_trades",
        "backtest_position_snapshots",
        "backtest_daily_pnl",
    ]
    assert analytics_writer.calls[0][1][0]["run_id"] == "run-sidecars"
    assert analytics_writer.calls[0][1][0]["trade_id"] == "trade-1"

    session.close()
