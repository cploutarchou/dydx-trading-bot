import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from internal.domain import Base
from internal.domain.models import ArtifactReference, BacktestRun
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.storage.analytics import AnalyticsWriter
from src.infrastructure.storage.artifacts import ArtifactStore
from src.infrastructure.storage.clickhouse_writer import ClickHouseAnalyticsWriter


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


class _FakeClickHouseClient:
    def __init__(self):
        self.commands: list[str] = []
        self.inserts: list[dict[str, object]] = []

    def command(self, sql: str) -> None:
        self.commands.append(sql)

    def insert(self, *, table: str, data: list, column_names: list) -> None:
        del table
        for row_values in data:
            self.inserts.append(dict(zip(column_names, row_values)))


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
    assert calls["commit"] == 3
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
    assert persisted["artifact_refs"]["full_result"] == (
        "artifact://backtests/run-sidecars/full_result.json"
    )
    assert (
        artifact_store.read_json("backtests/run-sidecars/full_result.json")["status"]
        == "completed"
    )
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

    db_run = (
        session.query(BacktestRun).filter(BacktestRun.run_id == "run-sidecars").first()
    )
    assert db_run is not None
    assert db_run.trades_json == []
    assert db_run.position_snapshots_json == []
    assert db_run.daily_pnl_json == []
    assert db_run.artifact_refs is not None
    assert db_run.artifact_refs["request"] == (
        "artifact://backtests/run-sidecars/request.json"
    )
    assert db_run.artifact_refs["full_result"] == (
        "artifact://backtests/run-sidecars/full_result.json"
    )
    assert db_run.analytics_rows_written == 3

    artifact_rows = (
        session.query(ArtifactReference)
        .filter(ArtifactReference.owner_id == "run-sidecars")
        .order_by(ArtifactReference.object_key.asc())
        .all()
    )
    assert len(artifact_rows) == 5
    assert [row.bucket for row in artifact_rows] == ["backtests"] * 5
    assert artifact_rows[0].owner_type == "backtest_run"
    assert artifact_rows[0].checksum
    assert artifact_rows[0].size_bytes > 0

    reloaded = repository.get_run("run-sidecars")
    assert reloaded is not None
    assert reloaded["trades"] == [{"trade_id": "trade-1", "pnl": 12.5}]
    assert reloaded["position_snapshots"] == [{"snapshot_id": "position-1"}]
    assert reloaded["daily_pnl"] == [{"date": "2026-04-01", "pnl": 12.5}]

    session.close()


def test_repeated_completed_save_does_not_duplicate_analytics_projection(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'idempotent-sidecars.sqlite'}", future=True
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    analytics_writer = _RecordingAnalyticsWriter()
    repository = BacktestRepository(
        session,
        artifact_store=_RecordingArtifactStore(),
        analytics_writer=analytics_writer,
    )
    payload = {
        "run_id": "run-idempotent-sidecars",
        "name": "idempotent",
        "status": "completed",
        "request": {"pairs": ["BTC-USD/ETH-USD"]},
        "trades": [{"trade_id": "trade-1", "pnl": 2.5}],
        "position_snapshots": [{"snapshot_id": "snapshot-1"}],
        "daily_pnl": [{"date": "2026-07-01", "pnl": 2.5}],
    }

    first = repository.save_run(payload)
    call_count = len(analytics_writer.calls)
    second = repository.save_run(payload)

    assert first["analytics_rows_written"] == 3
    assert second["analytics_rows_written"] == 3
    assert len(analytics_writer.calls) == call_count
    full_result_ref = next(
        (
            row
            for row in session.query(ArtifactReference)
            .filter(ArtifactReference.owner_id == payload["run_id"])
            .all()
            if (row.metadata_json or {}).get("artifact_kind") == "full_result_json"
        ),
        None,
    )
    assert full_result_ref is not None
    assert full_result_ref.metadata_json["analytics_projection_complete"] is True
    assert full_result_ref.metadata_json["analytics_projection_checksum"]
    session.close()


def test_save_run_updates_existing_artifact_reference_rows(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'artifact-upsert.sqlite'}", future=True
    )
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

    first_persisted = repository.save_run(
        {
            "run_id": "run-upsert",
            "name": "upsert",
            "status": "running",
            "request": {"pairs": ["BTC-USD/ETH-USD"]},
            "trades": [{"trade_id": "trade-1", "pnl": 1.0}],
        }
    )
    second_persisted = repository.save_run(
        {
            "run_id": "run-upsert",
            "name": "upsert",
            "status": "completed",
            "request": {"pairs": ["BTC-USD/ETH-USD"]},
            "trades": [{"trade_id": "trade-1", "pnl": 10.0}],
        }
    )

    assert "full_result" not in first_persisted["artifact_refs"]
    assert second_persisted["artifact_refs"]["full_result"] == (
        "artifact://backtests/run-upsert/full_result.json"
    )

    artifact_rows = (
        session.query(ArtifactReference)
        .filter(ArtifactReference.owner_id == "run-upsert")
        .order_by(ArtifactReference.object_key.asc())
        .all()
    )
    assert len(artifact_rows) == 5
    trades_row = next(
        row for row in artifact_rows if row.object_key == "run-upsert/trades.json"
    )
    full_result_row = next(
        row for row in artifact_rows if row.object_key == "run-upsert/full_result.json"
    )
    assert trades_row.bucket == "backtests"
    assert trades_row.metadata_json["artifact_kind"] == "trades"
    assert full_result_row.metadata_json["artifact_kind"] == "full_result_json"
    assert trades_row.size_bytes == len(
        json.dumps(
            [{"trade_id": "trade-1", "pnl": 10.0}],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )

    session.close()


def test_save_run_writes_equity_curve_and_strategy_metrics_when_present(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'analytics.sqlite'}", future=True)
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
            "run_id": "run-analytics",
            "name": "analytics",
            "status": "completed",
            "request": {
                "pairs": ["BTC-USD/ETH-USD"],
                "strategy_id": 42,
            },
            "trades": [{"trade_id": "trade-1", "pnl": 12.5}],
            "position_snapshots": [{"snapshot_id": "position-1"}],
            "daily_pnl": [{"date": "2026-04-01", "pnl": 12.5}],
            "equity_curve": [
                {"point_time": "2026-04-01T00:00:00+00:00", "equity": 1000.0},
                {"point_time": "2026-04-02T00:00:00+00:00", "equity": 1012.5},
            ],
            "metrics": {
                "sharpe_ratio": 1.25,
                "max_drawdown_pct": -4.5,
            },
            "updated_at": "2026-04-03T00:00:00+00:00",
        }
    )

    assert [call[0] for call in analytics_writer.calls] == [
        "backtest_trades",
        "backtest_position_snapshots",
        "backtest_daily_pnl",
        "backtest_equity_curve",
        "strategy_metrics",
    ]
    assert analytics_writer.calls[3][1] == [
        {
            "run_id": "run-analytics",
            "point_time": "2026-04-01T00:00:00+00:00",
            "equity": 1000.0,
        },
        {
            "run_id": "run-analytics",
            "point_time": "2026-04-02T00:00:00+00:00",
            "equity": 1012.5,
        },
    ]
    persisted_created_at = persisted["created_at"]
    assert analytics_writer.calls[4][1] == [
        {
            "run_id": "run-analytics",
            "metric_name": "max_drawdown_pct",
            "metric_value": -4.5,
            "strategy_id": 42,
            "scope": "backtest",
            "metric_time": persisted_created_at,
        },
        {
            "run_id": "run-analytics",
            "metric_name": "sharpe_ratio",
            "metric_value": 1.25,
            "strategy_id": 42,
            "scope": "backtest",
            "metric_time": persisted_created_at,
        },
    ]

    db_run = (
        session.query(BacktestRun).filter(BacktestRun.run_id == "run-analytics").first()
    )
    assert db_run is not None
    assert db_run.analytics_rows_written == 7

    session.close()


def test_nonterminal_run_does_not_project_mutable_analytics_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'progress.sqlite'}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    analytics_writer = _RecordingAnalyticsWriter()
    repository = BacktestRepository(
        SessionLocal(),
        artifact_store=_RecordingArtifactStore(),
        analytics_writer=analytics_writer,
    )

    repository.save_run(
        {
            "run_id": "run-progress",
            "name": "progress",
            "status": "running",
            "trades": [{"trade_id": "mutable-trade", "pnl": 1.0}],
            "position_snapshots": [{"snapshot_id": "mutable-position"}],
            "daily_pnl": [{"date": "2026-07-12", "pnl": 1.0}],
        }
    )

    assert analytics_writer.calls == []


def test_save_run_forces_clickhouse_flush_for_terminal_completed_run(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'analytics-flush.sqlite'}", future=True
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    artifact_store = _RecordingArtifactStore()
    analytics_client = _FakeClickHouseClient()
    analytics_writer = ClickHouseAnalyticsWriter(
        enabled=True,
        database="analytics",
        extra_config={
            "client": analytics_client,
            "batch_size": 50,
            "flush_interval_seconds": 60,
        },
    )
    repository = BacktestRepository(
        session,
        artifact_store=artifact_store,
        analytics_writer=analytics_writer,
    )

    persisted = repository.save_run(
        {
            "run_id": "run-terminal-flush",
            "name": "terminal-flush",
            "status": "completed",
            "request": {"pairs": ["BTC-USD/ETH-USD"]},
            "trades": [{"trade_id": "trade-1", "pnl": 12.5}],
            "position_snapshots": [{"snapshot_id": "position-1"}],
            "daily_pnl": [{"date": "2026-04-01", "pnl": 12.5}],
        }
    )

    assert persisted["analytics_rows_written"] == 3
    assert analytics_writer.get_buffer("backtest_trades") == []
    assert analytics_writer.get_buffer("backtest_position_snapshots") == []
    assert analytics_writer.get_buffer("backtest_daily_pnl") == []
    assert len(analytics_client.inserts) == 3

    session.close()
