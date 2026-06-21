from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from internal.domain import Base
from src.infrastructure.persistence.repository_backtest import BacktestRepository


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
            raise OperationalError("UPDATE backtest_runtime_runs", {}, _MariaDbRecordChanged())
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
    engine = create_engine(f"sqlite:///{tmp_path / 'failed-progress.sqlite'}", future=True)
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

