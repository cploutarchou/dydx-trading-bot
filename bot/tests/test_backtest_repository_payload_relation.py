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


def _stored_request(session, run_id):
    # Read the column directly: get_run() falls back to the request snapshot,
    # which would hide a wiped row.
    session.expire_all()
    record = session.query(BacktestRun).filter(BacktestRun.run_id == run_id).one()
    return dict(record.request_json or {})


def test_save_run_from_summary_projection_keeps_stored_request():
    session = _session()
    repo = BacktestRepository(session)
    run_id = "run-summary-resave-1"
    request = {"start_date": "2026-04-01", "selected_pairs": ["BTC-USD/ETH-USD"]}
    repo.save_run(
        {"run_id": run_id, "name": "resave", "status": "pending", "request": request}
    )

    # list_runs() returns a summary with no "request" key at all, and
    # _normalize_run_data() then defaults it to {}.
    summary = next(row for row in repo.list_runs() if row["run_id"] == run_id)
    assert "request" not in summary

    repo.save_run({**summary, "status": "failed"})

    assert _stored_request(session, run_id) == request
    assert repo.get_run(run_id)["status"] == "failed"


def test_save_run_still_replaces_request_when_one_is_given():
    session = _session()
    repo = BacktestRepository(session)
    run_id = "run-request-update-1"
    repo.save_run({"run_id": run_id, "status": "pending", "request": {"a": 1}})

    repo.save_run({"run_id": run_id, "status": "running", "request": {"a": 2}})

    assert _stored_request(session, run_id) == {"a": 2}


def test_reconciling_an_interrupted_run_keeps_its_request():
    from src.infrastructure.use_cases.service_backtest import BacktestService

    # Regression: on every API start, interruption recovery marked orphaned
    # pending/running runs as failed by re-saving their list_runs() summary,
    # which blanked the request and made the run impossible to restart.
    session = _session()
    repo = BacktestRepository(session)
    run_id = "run-interrupted-1"
    request = {"start_date": "2026-04-01", "selected_pairs": ["BTC-USD/ETH-USD"]}
    repo.save_run(
        {"run_id": run_id, "name": "queued", "status": "pending", "request": request}
    )

    service = BacktestService(repo)
    outcome = service.reconcile_interrupted_runs(dry_run=False)

    assert [row["run_id"] for row in outcome["reconciled"]] == [run_id]
    assert repo.get_run(run_id)["status"] == "failed"
    assert _stored_request(session, run_id) == request


def test_save_run_with_only_a_control_block_keeps_stored_request():
    session = _session()
    repo = BacktestRepository(session)
    run_id = "run-control-only-resave-1"
    request = {
        "start_date": "2026-04-01",
        "selected_pairs": ["BTC-USD/ETH-USD"],
        "_runtime_control": {"status": "running", "action": "start"},
    }
    repo.save_run({"run_id": run_id, "status": "running", "request": request})

    summary = next(row for row in repo.list_runs() if row["run_id"] == run_id)
    newer_control = {"status": "stale", "action": "start"}
    repo.save_run(
        {**summary, "status": "stale", "request": {"_runtime_control": newer_control}}
    )

    stored = _stored_request(session, run_id)
    assert stored["selected_pairs"] == ["BTC-USD/ETH-USD"]
    assert stored["start_date"] == "2026-04-01"
    assert stored["_runtime_control"] == newer_control


def test_marking_a_run_stale_from_the_health_probe_keeps_its_request():
    from datetime import datetime, timedelta, timezone

    from src.infrastructure.use_cases.service_backtest import BacktestService

    # Regression: /health and /ready resolve every run from the list_runs()
    # projection. When a worker died mid-run, the stale verdict was saved with
    # a request holding only the control block, which erased the run's pairs
    # and dates; every restart then failed with SELECTED_PAIRS_MISSING.
    session = _session()
    repo = BacktestRepository(session)
    run_id = "run-worker-lost-1"
    request = {
        "start_date": "2026-02-01",
        "end_date": "2026-09-20",
        "selected_pairs": ["AVAX-USD/EOS-USD"],
        "_runtime_control": {
            "status": "running",
            "action": "start",
            "worker_backend": "celery",
            "worker_task_id": run_id,
        },
    }
    repo.save_run(
        {
            "run_id": run_id,
            "name": "worker lost",
            "status": "running",
            "request": request,
        }
    )
    # save_run() stamps updated_at itself, so age the heartbeat on the row.
    record = session.query(BacktestRun).filter(BacktestRun.run_id == run_id).one()
    record.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    session.commit()

    BacktestService(repo).get_runtime_health()

    assert repo.get_run(run_id)["status"] == "stale"
    stored = _stored_request(session, run_id)
    assert stored["selected_pairs"] == ["AVAX-USD/EOS-USD"]
    assert stored["start_date"] == "2026-02-01"
    assert stored["end_date"] == "2026-09-20"
