from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from internal.domain import Base
from internal.domain.models import BacktestRun, BacktestRunRequestPayload
from src.infrastructure.persistence.repository_backtest import BacktestRepository


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_get_run_falls_back_to_request_relation_when_row_payload_missing():
    session = _session()
    now = datetime.now(timezone.utc)
    run_id = "run-fallback-1"

    session.add(
        BacktestRun(
            run_id=run_id,
            name="fallback-test",
            status="failed",
            progress_pct=0.0,
            request_json={},
            trades_json=[],
            position_snapshots_json=[],
            daily_pnl_json=[],
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        BacktestRunRequestPayload(
            run_id=run_id,
            request_json={"start_date": "2026-04-01", "end_date": "2026-04-30"},
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()

    repo = BacktestRepository(session)
    row = repo.get_run(run_id)

    assert row is not None
    assert row["request"]["start_date"] == "2026-04-01"
    assert row["request"]["end_date"] == "2026-04-30"


def test_save_run_persists_snapshot_and_strips_runtime_control():
    session = _session()
    repo = BacktestRepository(session)

    run_id = "run-snapshot-1"
    repo.save_run(
        {
            "run_id": run_id,
            "name": "snapshot-test",
            "status": "pending",
            "request": {
                "start_date": "2026-04-01",
                "end_date": "2026-04-30",
                "_runtime_control": {"status": "running"},
            },
        }
    )

    snapshot = (
        session.query(BacktestRunRequestPayload)
        .filter(BacktestRunRequestPayload.run_id == run_id)
        .first()
    )
    assert snapshot is not None
    assert snapshot.request_json.get("start_date") == "2026-04-01"
    assert "_runtime_control" not in dict(snapshot.request_json or {})

    # Later writes with missing request should not erase the immutable snapshot.
    repo.save_run(
        {
            "run_id": run_id,
            "name": "snapshot-test-2",
            "status": "failed",
            "request": {},
        }
    )

    snapshot_after = (
        session.query(BacktestRunRequestPayload)
        .filter(BacktestRunRequestPayload.run_id == run_id)
        .first()
    )
    assert snapshot_after is not None
    assert snapshot_after.request_json.get("start_date") == "2026-04-01"


def test_get_run_overview_omits_large_payloads_but_keeps_request():
    session = _session()
    now = datetime.now(timezone.utc)
    run_id = "run-overview-1"

    session.add(
        BacktestRun(
            run_id=run_id,
            name="overview-test",
            status="running",
            progress_pct=12.5,
            request_json={"start_date": "2026-04-01", "pairs": ["BTC-USD", "ETH-USD"]},
            trades_json=[{"trade_id": "t-1"}],
            position_snapshots_json=[{"timestamp": "2026-04-01T00:00:00Z"}],
            daily_pnl_json=[{"date": "2026-04-01", "pnl": 10.0}],
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()

    repo = BacktestRepository(session)
    row = repo.get_run_overview(run_id)

    assert row is not None
    assert row["request"]["start_date"] == "2026-04-01"
    assert "trades" not in row
    assert "position_snapshots" not in row
    assert "daily_pnl" not in row
