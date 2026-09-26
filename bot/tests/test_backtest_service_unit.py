"""Unit seams for BacktestService (service_backtest.py).

Focused on the spans the e2e file (tests/test_backtest_service.py) cannot reach
with a live fake dYdX client: pure helpers, lifecycle normalization, cache vs
persist branches, runtime-control pause/resume loop, heartbeat paths, worker
backend resolution edges, and the seeded pair simulator.
"""

from __future__ import annotations

import asyncio
import math
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pytest

import src.infrastructure.use_cases.service_backtest as sb
from src.infrastructure.use_cases.service_backtest import BacktestService


class _FakeRepo:
    """Minimal BacktestRepository double: dict store + call recording."""

    def __init__(self, runs: Optional[List[Dict[str, Any]]] = None):
        self.session = None
        self.runs: Dict[str, Dict[str, Any]] = {
            str(r.get("run_id")): dict(r) for r in (runs or [])
        }
        self.saved: List[Dict[str, Any]] = []
        self.progress_updates: List[Dict[str, Any]] = []
        self.touched: List[str] = []
        self.touch_result = True
        self.list_runs_payload: List[Dict[str, Any]] = list(self.runs.values())
        self.count_payload: Optional[int] = None
        self.fail_get_run = False
        self.fail_overview = False

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        if self.fail_get_run:
            raise RuntimeError("get_run exploded")
        run = self.runs.get(run_id)
        return dict(run) if run is not None else None

    def get_run_overview(self, run_id: str) -> Optional[Dict[str, Any]]:
        if self.fail_overview:
            raise RuntimeError("get_run_overview exploded")
        run = self.runs.get(run_id)
        return dict(run) if run is not None else None

    def save_run(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        persisted = dict(run_data)
        self.runs[str(persisted.get("run_id"))] = persisted
        self.saved.append(dict(persisted))
        return dict(persisted)

    def update_run_progress(self, run_data: Dict[str, Any]) -> bool:
        self.progress_updates.append(dict(run_data))
        self.runs[str(run_data.get("run_id"))] = dict(run_data)
        return True

    def touch_run(self, run_id: str, updated_at: Optional[str] = None) -> bool:
        self.touched.append(run_id)
        return self.touch_result

    def list_runs(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        status_filter: Optional[str] = None,
        days_filter: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.list_runs_payload]

    def count_runs(
        self,
        statuses: Optional[List[str]] = None,
        days_filter: Optional[int] = None,
    ) -> int:
        return (
            self.count_payload
            if self.count_payload is not None
            else len(self.list_runs_payload)
        )


def _make_service(repo: _FakeRepo) -> BacktestService:
    service = BacktestService.__new__(BacktestService)
    service.repository = repo
    service.session = getattr(repo, "session", None)
    return service


def _run(run_id: str = "run-x", **overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "run_id": run_id,
        "name": "test-run",
        "status": "running",
        "progress_pct": 10.0,
        "current_pair": "BTC/ETH",
        "current_task": "processing pair",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "request": {"pairs": ["BTC", "ETH"]},
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _reset_service_state():
    saved_runs = dict(BacktestService._runs)
    saved_tasks = dict(BacktestService._tasks)
    saved_monotonic = BacktestService._backend_reprobe_last_monotonic
    saved_available = BacktestService._backend_reprobe_last_available
    BacktestService._runs.clear()
    BacktestService._tasks.clear()
    BacktestService._backend_reprobe_last_monotonic = 0.0
    BacktestService._backend_reprobe_last_available = False
    try:
        yield
    finally:
        BacktestService._runs.clear()
        BacktestService._runs.update(saved_runs)
        BacktestService._tasks.clear()
        BacktestService._tasks.update(saved_tasks)
        BacktestService._backend_reprobe_last_monotonic = saved_monotonic
        BacktestService._backend_reprobe_last_available = saved_available


@pytest.fixture(autouse=True)
def _quiet_job_manager(monkeypatch):
    """Record job-manager marks instead of touching real job state."""
    calls: Dict[str, List[Any]] = {
        "progress": [],
        "completed": [],
        "failed": [],
        "cancelled": [],
    }

    def _record(name):
        def _inner(*args, **kwargs):
            calls[name].append((args, kwargs))

        return _inner

    monkeypatch.setattr(
        sb.async_job_manager, "mark_progress", _record("progress"), raising=False
    )
    monkeypatch.setattr(
        sb.async_job_manager, "mark_completed", _record("completed"), raising=False
    )
    monkeypatch.setattr(
        sb.async_job_manager, "mark_failed", _record("failed"), raising=False
    )
    monkeypatch.setattr(
        sb.async_job_manager, "mark_cancelled", _record("cancelled"), raising=False
    )
    return calls


# ---------------------------------------------------------------------------
# Pure status / lifecycle helpers
# ---------------------------------------------------------------------------


def test_canonical_status_alias_table():
    assert BacktestService._canonical_status("") == "pending"
    assert BacktestService._canonical_status(None) == "pending"
    assert BacktestService._canonical_status("QUEUED") == "pending"
    assert BacktestService._canonical_status("Scheduled") == "pending"
    assert BacktestService._canonical_status("in_progress") == "running"
    assert BacktestService._canonical_status("STARTED") == "running"
    assert BacktestService._canonical_status("retry") == "retrying"
    assert BacktestService._canonical_status("succeeded") == "completed"
    assert BacktestService._canonical_status("done") == "completed"
    assert BacktestService._canonical_status("error") == "failed"
    assert BacktestService._canonical_status("timed_out") == "timeout"
    assert BacktestService._canonical_status("stalled") == "stale"
    assert BacktestService._canonical_status("canceled") == "cancelled"
    assert BacktestService._canonical_status("weird-status") == "weird-status"


def test_normalize_lifecycle_state_pending_promotions():
    cancelled = BacktestService._normalize_lifecycle_state(
        {"status": "pending", "cancel_requested": True}
    )
    assert cancelled["status"] == "cancelled"

    failed = BacktestService._normalize_lifecycle_state(
        {"status": "pending", "error": "boom"}
    )
    assert failed["status"] == "failed"

    completed = BacktestService._normalize_lifecycle_state(
        {"status": "pending", "progress_pct": 100.0}
    )
    assert completed["status"] == "completed"

    via_pair = BacktestService._normalize_lifecycle_state(
        {"status": "pending", "current_pair": "Complete"}
    )
    assert via_pair["status"] == "completed"

    promoted = BacktestService._normalize_lifecycle_state(
        {"status": "pending", "started_at": "2026-01-01T00:00:00Z"}
    )
    assert promoted["status"] == "running"

    via_metrics = BacktestService._normalize_lifecycle_state(
        {"status": "pending", "total_trades": 3}
    )
    assert via_metrics["status"] == "running"

    untouched = BacktestService._normalize_lifecycle_state(
        {"status": "pending", "current_pair": "queued"}
    )
    assert untouched["status"] == "pending"

    terminal = BacktestService._normalize_lifecycle_state({"status": "completed"})
    assert terminal["status"] == "completed"


def test_to_ops_row_defaults_for_missing_fields():
    row = BacktestService._to_ops_row({})
    assert row["run_id"] == ""
    assert row["name"] == ""
    assert row["status"] == ""
    assert row["progress_pct"] == 0.0
    assert row["error"] is None
    full = BacktestService._to_ops_row({"run_id": "r1", "progress_pct": "12.5"})
    assert full["progress_pct"] == 12.5


def test_extract_request_payload_shapes():
    assert BacktestService._extract_request_payload({"a": 1}) == {"a": 1}

    class _ModelLike:
        def model_dump(self):
            return {"pydantic": True}

    assert BacktestService._extract_request_payload(_ModelLike()) == {"pydantic": True}
    assert BacktestService._extract_request_payload("nope") == {}


def test_coerce_bool_matrix():
    assert BacktestService._coerce_bool(True) is True
    assert BacktestService._coerce_bool(False) is False
    assert BacktestService._coerce_bool(None, default=True) is True
    assert BacktestService._coerce_bool("YES") is True
    assert BacktestService._coerce_bool(" on ") is True
    assert BacktestService._coerce_bool("0") is False
    assert BacktestService._coerce_bool("off") is False


def test_error_code_from_message_prefix_extraction():
    assert (
        BacktestService._error_code_from_message(
            "SELECTED_PAIRS_MISSING: need pairs", "X"
        )
        == "SELECTED_PAIRS_MISSING"
    )
    assert BacktestService._error_code_from_message("plain failure", "DEF") == "DEF"
    assert BacktestService._error_code_from_message("", "DEF") == "DEF"
    assert BacktestService._error_code_from_message("has space: nope", "DEF") == "DEF"


def test_normalize_analytics_rows_written_variants():
    assert BacktestService._normalize_analytics_rows_written(None) == 0
    assert BacktestService._normalize_analytics_rows_written("7") == 7
    assert BacktestService._normalize_analytics_rows_written(-3) == 0
    assert BacktestService._normalize_analytics_rows_written("junk") == 0
    assert (
        BacktestService._normalize_analytics_rows_written({"a": 2, "b": 3, "c": "x"})
        == 5
    )
    assert BacktestService._normalize_analytics_rows_written({"a": -5}) == 0


# ---------------------------------------------------------------------------
# Cache / persist seams
# ---------------------------------------------------------------------------


def test_load_run_data_prefers_persisted_and_hydrates():
    repo = _FakeRepo(
        [
            _run(
                "r1",
                request={
                    "pairs": ["BTC", "ETH"],
                    "_runtime_control": {"status": "started"},
                },
            )
        ]
    )
    service = _make_service(repo)
    loaded = service._load_run_data("r1")
    assert loaded is not None
    assert loaded["control_status"] == "started"
    assert "r1" in BacktestService._runs
    # Second load hydrates from the repository again (session is None but the
    # persisted row exists, so the repository wins over the cache).
    assert service._load_run_data("r1")["control_status"] == "started"


def test_load_run_data_cache_fallback_without_request_key():
    service = _make_service(_FakeRepo())
    BacktestService._runs["r1"] = _run("r1")
    BacktestService._runs["r1"].pop("request")
    loaded = service._load_run_data("r1")
    assert loaded is not None
    assert loaded["run_id"] == "r1"
    assert service._load_run_data("missing") is None


def test_load_run_data_uses_cache_with_request_when_session_none():
    service = _make_service(_FakeRepo())
    BacktestService._runs["r1"] = _run("r1")
    loaded = service._load_run_data("r1")
    assert loaded is not None
    assert loaded["request"] == {"pairs": ["BTC", "ETH"]}


def test_load_run_overview_persisted_and_cache_paths():
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    assert service._load_run_overview("r1")["run_id"] == "r1"
    assert service._load_run_overview("missing") is None

    repo.fail_overview = True
    cached_overview = _run("r2")
    cached_overview.pop("request")  # without "request" the cache cannot satisfy
    BacktestService._runs["r2"] = cached_overview
    # ...so the repository is consulted and its failure propagates.
    with pytest.raises(RuntimeError):
        service._load_run_overview("r2")


def test_persist_run_data_merges_pending_external_control():
    repo = _FakeRepo(
        [
            _run(
                "r1",
                request={
                    "pairs": ["BTC", "ETH"],
                    "_runtime_control": {"cancel_requested": True, "status": "running"},
                },
            )
        ]
    )
    service = _make_service(repo)
    incoming = _run(
        "r1", request={"pairs": ["BTC", "ETH"]}, started_at="2026-01-01T00:00:00Z"
    )
    persisted = service._persist_run_data(incoming)
    control = BacktestService._get_runtime_control(persisted)
    assert control.get("cancel_requested") is True
    assert persisted["control_status"] == "running"
    assert persisted["started_at"] == "2026-01-01T00:00:00Z"
    assert BacktestService._runs["r1"]["run_id"] == "r1"


def test_persist_run_data_preserves_control_keys_dropped_by_repository():
    repo = _FakeRepo()

    def _stripping_save(run_data):
        return {k: v for k, v in run_data.items() if k != "deadline_at"}

    repo.save_run = _stripping_save  # type: ignore[method-assign]
    service = _make_service(repo)
    persisted = service._persist_run_data(
        _run("r1", deadline_at="2026-01-02T00:00:00Z", timeout_seconds=60.0)
    )
    assert persisted["deadline_at"] == "2026-01-02T00:00:00Z"
    assert persisted["timeout_seconds"] == 60.0


def test_persist_run_data_survives_existing_lookup_failure():
    repo = _FakeRepo([_run("r1")])
    repo.fail_get_run = True
    service = _make_service(repo)
    persisted = service._persist_run_data(_run("r1", status="completed"))
    assert persisted["status"] == "completed"


def test_persist_progress_data_raises_when_repository_rejects():
    repo = _FakeRepo()

    def _reject(run_data):
        return False

    repo.update_run_progress = _reject  # type: ignore[method-assign]
    service = _make_service(repo)
    with pytest.raises(RuntimeError, match="unavailable for progress update"):
        service._persist_progress_data(_run("r1"))


def test_persist_progress_data_caches_into_runs():
    repo = _FakeRepo()
    service = _make_service(repo)
    BacktestService._runs["r1"] = _run("r1", progress_pct=0.0)
    result = service._persist_progress_data(_run("r1", progress_pct=42.0))
    assert result["progress_pct"] == 42.0
    assert BacktestService._runs["r1"]["progress_pct"] == 42.0
    assert repo.progress_updates[-1]["progress_pct"] == 42.0


def test_update_run_data_missing_run_and_autoupdated_timestamp():
    service = _make_service(_FakeRepo())
    assert service._update_run_data("missing", status="failed") is None

    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    updated = service._update_run_data("r1", status="paused")
    assert updated["status"] == "paused"
    assert updated["updated_at"]  # auto-stamped

    explicit = service._update_run_data(
        "r1", status="running", updated_at="2026-05-05T00:00:00Z"
    )
    assert explicit["updated_at"] == "2026-05-05T00:00:00Z"


def test_merge_runtime_control_branch_matrix():
    fresh = _run("r1", request={"pairs": ["BTC", "ETH"]})

    # No existing control -> returned untouched.
    assert BacktestService._merge_runtime_control(fresh, {"request": {}}) is fresh

    existing_cancel = {
        "request": {"_runtime_control": {"cancel_requested": True, "action": "start"}}
    }
    merged = BacktestService._merge_runtime_control(fresh, existing_cancel)
    assert BacktestService._get_runtime_control(merged).get("cancel_requested") is True

    # Current explicit cancel action wins over pending external control.
    cancelling = _run(
        "r1",
        request={
            "pairs": ["BTC", "ETH"],
            "_runtime_control": {"action": "cancel", "status": "cancelling"},
        },
    )
    kept = BacktestService._merge_runtime_control(cancelling, existing_cancel)
    assert BacktestService._get_runtime_control(kept).get("action") == "cancel"


def test_load_fresh_runtime_control_repo_failure_falls_back_to_cache():
    repo = _FakeRepo()
    repo.fail_overview = True
    service = _make_service(repo)
    BacktestService._runs["r1"] = _run(
        "r1", request={"_runtime_control": {"pause_requested": True}}
    )
    control = service._load_fresh_runtime_control("r1")
    assert control.get("pause_requested") is True

    repo.fail_overview = False
    assert service._load_fresh_runtime_control("missing") == {}


class _RecordingSession:
    """Session double that only records close() — enough for lifecycle pins."""

    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def test_load_fresh_runtime_control_bound_session_uses_short_lived_read(monkeypatch):
    """Worker path: control reads must not run on the long-held session.

    A SELECT on the held repository session pins a pooled connection until the
    next (throttled) write commit — and continuously while paused, because the
    pause poll loop only reads. The read must open → read → close instead.
    """
    from src.infrastructure.use_cases import service_backtest

    repo = _FakeRepo()
    repo.session = object()  # bound long-lived worker session
    service = _make_service(repo)

    bound_calls: List[str] = []

    def _bound_overview(run_id: str) -> Optional[Dict[str, Any]]:
        bound_calls.append(run_id)
        return None

    repo.get_run_overview = _bound_overview  # type: ignore[method-assign]

    session = _RecordingSession()
    stub_sessions: List[_RecordingSession] = []

    class _StubRepo:
        def __init__(self, sess: _RecordingSession) -> None:
            stub_sessions.append(sess)

        def get_run_overview(self, run_id: str) -> Optional[Dict[str, Any]]:
            return {
                "run_id": run_id,
                "request": {
                    "_runtime_control": {"action": "pause", "pause_requested": True}
                },
            }

    monkeypatch.setattr(service_backtest, "BacktestRepository", _StubRepo)
    monkeypatch.setattr(service_backtest.db, "get_session", lambda: session)

    control = service._load_fresh_runtime_control("r1")

    assert control.get("pause_requested") is True
    assert bound_calls == []  # the bound (held) session was never used
    assert stub_sessions == [session]  # fresh repository over the short session
    assert session.closed == 1  # released immediately, not held


def test_load_fresh_runtime_control_short_read_failure_falls_back_to_cache(
    monkeypatch,
):
    """A failing short-lived control read degrades to the cached control dict."""
    from src.infrastructure.use_cases import service_backtest

    repo = _FakeRepo()
    repo.session = object()
    service = _make_service(repo)
    BacktestService._runs["r1"] = _run(
        "r1", request={"_runtime_control": {"cancel_requested": True}}
    )

    class _ExplodingRepo:
        def __init__(self, sess: Any) -> None:
            pass

        def get_run_overview(self, run_id: str) -> Optional[Dict[str, Any]]:
            raise RuntimeError("short session read failed")

    monkeypatch.setattr(service_backtest, "BacktestRepository", _ExplodingRepo)
    monkeypatch.setattr(service_backtest.db, "get_session", _RecordingSession)

    assert service._load_fresh_runtime_control("r1").get("cancel_requested") is True


# ---------------------------------------------------------------------------
# Observability + heartbeat helpers
# ---------------------------------------------------------------------------


def test_with_status_observability_marks_running_run_stale():
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    observed = BacktestService._with_status_observability(
        _run("r1", updated_at=old, request={})
    )
    assert observed["status"] == "stale"
    assert observed["current_task"] == "stale"
    assert observed["error"]
    assert observed["cancellable"] is False
    assert observed["pausable"] is False


def test_with_status_observability_active_run_flags():
    observed = BacktestService._with_status_observability(
        _run(
            "r1",
            request={
                "_runtime_control": {
                    "pause_requested": True,
                    "status": "pause_requested",
                }
            },
        )
    )
    assert observed["status"] == "running"
    assert observed["pausable"] is False
    assert observed["resumable"] is True
    assert observed["cancellable"] is True
    assert observed["worker_backend"] == "asyncio"


def test_result_summary_and_location():
    assert BacktestService._result_summary({"status": "running"}) is None
    summary = BacktestService._result_summary(
        {"status": "completed", "total_pnl": "12.5", "total_trades": 4}
    )
    assert summary == {
        "status": "completed",
        "total_pnl": 12.5,
        "total_trades": 4,
        "win_rate": 0.0,
        "sharpe_ratio": 0.0,
    }
    assert BacktestService._result_location({}) == ""
    assert BacktestService._result_location({"run_id": "r1"}).endswith("/r1")


def test_parse_dt_and_heartbeat_age():
    assert BacktestService._parse_dt(None) is None
    assert BacktestService._parse_dt("") is None
    assert BacktestService._parse_dt("garbage") is None
    naive = BacktestService._parse_dt("2026-01-01T00:00:00")
    assert naive is not None and naive.tzinfo is not None
    zulu = BacktestService._parse_dt("2026-01-01T00:00:00Z")
    assert zulu is not None and zulu.tzinfo is not None
    assert BacktestService._heartbeat_age_seconds({}) is None
    age = BacktestService._heartbeat_age_seconds(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    )
    assert age is not None and age >= 0.0


def test_stale_heartbeat_seconds_env_matrix(monkeypatch):
    assert BacktestService._stale_backtest_heartbeat_seconds() == 120.0
    monkeypatch.setenv("BACKTEST_STALE_HEARTBEAT_SECONDS", "300")
    assert BacktestService._stale_backtest_heartbeat_seconds() == 300.0
    monkeypatch.setenv("BACKTEST_STALE_HEARTBEAT_SECONDS", "1")
    assert BacktestService._stale_backtest_heartbeat_seconds() == 5.0
    monkeypatch.setenv("BACKTEST_STALE_HEARTBEAT_SECONDS", "bogus")
    assert BacktestService._stale_backtest_heartbeat_seconds() == 120.0


def test_heartbeat_keepalive_seconds_env_matrix(monkeypatch):
    # Default: min(30s, stale_threshold/3) with a 0.1 floor.
    assert BacktestService._heartbeat_keepalive_seconds() == 30.0
    monkeypatch.setenv("BACKTEST_STALE_HEARTBEAT_SECONDS", "30")
    assert BacktestService._heartbeat_keepalive_seconds() == pytest.approx(10.0)
    monkeypatch.setenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS", "0.05")
    assert BacktestService._heartbeat_keepalive_seconds() == pytest.approx(0.1)
    monkeypatch.delenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS")
    monkeypatch.setenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS", "junk")
    monkeypatch.delenv("BACKTEST_STALE_HEARTBEAT_SECONDS")
    assert BacktestService._heartbeat_keepalive_seconds() == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_run_backtest_heartbeat_keepalive_returns_on_terminal_status(
    monkeypatch,
):
    monkeypatch.setenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS", "0.05")
    repo = _FakeRepo([_run("r1", status="completed")])
    service = _make_service(repo)
    await asyncio.wait_for(
        service._run_backtest_heartbeat_keepalive("r1", time.monotonic() + 5.0),
        timeout=2.0,
    )
    # Terminal status exits before any heartbeat refresh.
    assert repo.touched == []


@pytest.mark.asyncio
async def test_run_backtest_heartbeat_keepalive_missing_run_exits(monkeypatch):
    monkeypatch.setenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS", "0.05")
    service = _make_service(_FakeRepo())
    await asyncio.wait_for(
        service._run_backtest_heartbeat_keepalive("missing", time.monotonic() + 5.0),
        timeout=2.0,
    )


@pytest.mark.asyncio
async def test_run_backtest_heartbeat_keepalive_refreshes_active_run(monkeypatch):
    monkeypatch.setenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS", "0.05")
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    task = asyncio.create_task(
        service._run_backtest_heartbeat_keepalive("r1", time.monotonic() + 0.4)
    )
    # Wait for at least one refresh cycle, then let the deadline expire.
    deadline = time.monotonic() + 2.0
    while not repo.saved and time.monotonic() < deadline:
        await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert repo.saved  # _update_run_data persisted a heartbeat refresh


def test_touch_run_heartbeat_repository_session_none():
    repo = _FakeRepo([_run("r1")])
    BacktestService._runs["r1"] = _run("r1")
    service = _make_service(repo)
    assert service._touch_run_heartbeat("r1") is True
    assert repo.touched == ["r1"]
    assert BacktestService._runs["r1"]["updated_at"]


def test_touch_run_heartbeat_uses_fresh_session_when_attached(monkeypatch):
    repo = _FakeRepo([_run("r1")])
    repo.session = object()  # attached session -> dedicated session path
    service = _make_service(repo)

    class _FakeDb:
        @staticmethod
        def get_session():
            session = type("_SessionHandle", (), {"closed": False})()

            def _close():
                session.closed = True

            session.close = _close  # type: ignore[method-assign]
            return session

    monkeypatch.setattr(sb, "db", _FakeDb)
    monkeypatch.setattr(sb, "BacktestRepository", lambda session: repo)
    BacktestService._runs["r1"] = _run("r1")
    assert service._touch_run_heartbeat("r1") is True
    assert repo.touched == ["r1"]


def test_heartbeat_keepalive_thread_exits_and_swallows_errors(monkeypatch):
    monkeypatch.setenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS", "0.05")
    stop = threading.Event()

    # Terminal run: thread returns on the first status check.
    repo = _FakeRepo([_run("r1", status="completed")])
    service = _make_service(repo)
    thread = threading.Thread(
        target=service._run_backtest_heartbeat_keepalive_thread,
        args=("r1", time.monotonic() + 5.0, stop),
        daemon=True,
    )
    thread.start()
    thread.join(timeout=3.0)
    assert not thread.is_alive()

    # Failing repository: loop tolerates exceptions until the deadline.
    repo_fail = _FakeRepo([_run("r1")])
    repo_fail.fail_get_run = True
    repo_fail.touch_result = False
    service_fail = _make_service(repo_fail)
    stop_fail = threading.Event()
    thread_fail = threading.Thread(
        target=service_fail._run_backtest_heartbeat_keepalive_thread,
        args=("r1", time.monotonic() + 0.3, stop_fail),
        daemon=True,
    )
    thread_fail.start()
    thread_fail.join(timeout=3.0)
    assert not thread_fail.is_alive()


def test_resolve_stale_run_data_persists_stalled_running_run():
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    repo = _FakeRepo([_run("r1", updated_at=old, request={})])
    service = _make_service(repo)
    resolved = service._resolve_stale_run_data(repo.runs["r1"])
    assert resolved["status"] == "stale"
    assert repo.saved, "stale observation must be persisted"
    persisted = repo.saved[-1]
    assert persisted["status"] == "stale"
    assert persisted["finished_at"]


def test_resolve_stale_run_data_persists_promoted_pending_state():
    repo = _FakeRepo([_run("r1", status="pending", cancel_requested=True, request={})])
    service = _make_service(repo)
    resolved = service._resolve_stale_run_data(repo.runs["r1"])
    assert resolved["status"] == "cancelled"
    assert repo.saved[-1]["status"] == "cancelled"


def test_resolve_stale_run_data_returns_observed_when_unchanged():
    repo = _FakeRepo([_run("r1", status="completed", request={})])
    service = _make_service(repo)
    resolved = service._resolve_stale_run_data(repo.runs["r1"])
    assert resolved["status"] == "completed"
    assert repo.saved == []


# ---------------------------------------------------------------------------
# Worker backend resolution + auto recovery configuration
# ---------------------------------------------------------------------------


def test_configured_worker_backend_matrix(monkeypatch):
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "CELERY")
    assert BacktestService._configured_worker_backend() == "celery"
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "nats")
    assert BacktestService._configured_worker_backend() == "nats"
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "bogus")
    assert BacktestService._configured_worker_backend() == "asyncio"
    monkeypatch.delenv("BACKTEST_WORKER_BACKEND")
    assert BacktestService._configured_worker_backend() == "asyncio"


def test_worker_backend_reprobe_cooldown_env(monkeypatch):
    assert BacktestService._worker_backend_reprobe_cooldown_seconds() == 15.0
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS", "5")
    assert BacktestService._worker_backend_reprobe_cooldown_seconds() == 5.0
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS", "-1")
    assert BacktestService._worker_backend_reprobe_cooldown_seconds() == 0.0
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS", "junk")
    assert BacktestService._worker_backend_reprobe_cooldown_seconds() == 15.0


@pytest.mark.asyncio
async def test_resolve_worker_backend_explicit_and_reprobe_off(monkeypatch):
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "celery")
    assert await BacktestService._resolve_worker_backend() == "celery"
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "nats")
    assert await BacktestService._resolve_worker_backend() == "nats"

    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "false")
    assert await BacktestService._resolve_worker_backend() == "asyncio"


@pytest.mark.asyncio
async def test_resolve_worker_backend_cooldown_returns_last_result(monkeypatch):
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "true")
    BacktestService._backend_reprobe_last_monotonic = time.monotonic()
    BacktestService._backend_reprobe_last_available = True
    probed = []

    def _probe(timeout_seconds=1.5):
        probed.append(timeout_seconds)
        return False

    monkeypatch.setattr(BacktestService, "_probe_celery_worker_available", _probe)
    assert await BacktestService._resolve_worker_backend() == "celery"
    assert probed == []  # inside the cooldown window: no probe, cached result


def test_auto_recovery_mode_alias_matrix(monkeypatch):
    monkeypatch.delenv("BACKTEST_AUTO_RECOVERY_MODE", raising=False)
    monkeypatch.delenv("BACKTEST_AUTO_RECOVER", raising=False)
    assert BacktestService._auto_recovery_mode() == "mark_failed"

    monkeypatch.setenv("BACKTEST_AUTO_RECOVER", "true")
    assert BacktestService._auto_recovery_mode() == "restart"
    monkeypatch.delenv("BACKTEST_AUTO_RECOVER")

    for raw, expected in [
        ("0", "off"),
        ("dry-run", "off"),
        ("observe", "off"),
        ("reconcile", "mark_failed"),
        ("mark-failed", "mark_failed"),
        ("1", "restart"),
        ("rerun", "restart"),
        ("resume", "restart"),
        ("unknown-mode", "mark_failed"),
    ]:
        monkeypatch.setenv("BACKTEST_AUTO_RECOVERY_MODE", raw)
        assert BacktestService._auto_recovery_mode() == expected, raw


def test_auto_recovery_min_age_and_candidate_matrix(monkeypatch):
    monkeypatch.delenv("BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS", raising=False)
    monkeypatch.delenv("BACKTEST_STALE_HEARTBEAT_SECONDS", raising=False)
    assert BacktestService._auto_recovery_min_age_seconds() == 120.0
    monkeypatch.setenv("BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS", "10")
    assert BacktestService._auto_recovery_min_age_seconds() == 10.0
    monkeypatch.setenv("BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS", "-5")
    assert BacktestService._auto_recovery_min_age_seconds() == 0.0
    monkeypatch.setenv("BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS", "junk")
    assert BacktestService._auto_recovery_min_age_seconds() == 120.0

    monkeypatch.setenv("BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS", "0")
    assert BacktestService._is_auto_recovery_candidate({}) is True

    monkeypatch.setenv("BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS", "3600")
    fresh = {"updated_at": datetime.now(timezone.utc).isoformat()}
    assert BacktestService._is_auto_recovery_candidate(fresh) is False
    assert BacktestService._is_auto_recovery_candidate({"updated_at": None}) is True


# ---------------------------------------------------------------------------
# Pair / request payload helpers
# ---------------------------------------------------------------------------


def test_pair_markets_from_request_error_branches():
    with pytest.raises(ValueError, match="SELECTED_PAIRS_INVALID"):
        BacktestService._pair_markets_from_request(
            {"selected_pairs": ["BTC/ETH", "ETH"]}
        )
    with pytest.raises(ValueError, match="SELECTED_PAIRS_INVALID"):
        BacktestService._pair_markets_from_request({"selected_pairs": ["BTC/ETH/USD"]})
    with pytest.raises(ValueError, match="SELECTED_PAIRS_INVALID"):
        BacktestService._pair_markets_from_request({"selected_pairs": ["BTC/BTC"]})
    with pytest.raises(ValueError, match="SELECTED_PAIRS_MISSING"):
        BacktestService._pair_markets_from_request({"pairs": ["BTC"]})
    with pytest.raises(ValueError, match="SELECTED_PAIRS_MISSING"):
        BacktestService._pair_markets_from_request({})

    pairs, labels, explicit = BacktestService._pair_markets_from_request(
        {"selected_pairs": ["btc/eth", "BTC/ETH", "ETH/SOL"]}
    )
    assert pairs == [("BTC", "ETH"), ("ETH", "SOL")]
    assert labels == ["BTC/ETH", "ETH/SOL"]
    assert explicit is True

    derived, derived_labels, implicit = BacktestService._pair_markets_from_request(
        {"pairs": ["BTC", "ETH", "SOL"]}
    )
    assert derived == [("BTC", "ETH"), ("BTC", "SOL"), ("ETH", "SOL")]
    assert derived_labels == ["BTC/ETH", "BTC/SOL", "ETH/SOL"]
    assert implicit is False


def test_selected_pair_labels_and_markets_from_request():
    explicit = BacktestService._selected_pair_labels_from_request(
        {"selected_pairs": ["BTC/ETH"]}
    )
    assert explicit == ["BTC/ETH"]

    derived = BacktestService._selected_pair_labels_from_request(
        {"pairs": ["BTC", "ETH", "SOL"]}
    )
    assert derived == ["BTC/ETH", "BTC/SOL", "ETH/SOL"]

    single = BacktestService._selected_pair_labels_from_request({"pairs": ["BTC"]})
    assert single == []
    assert BacktestService._selected_pair_labels_from_request({}) == []


def test_reconstruct_restart_request_payload_paths():
    existing = BacktestService._reconstruct_restart_request_payload(
        {"request": {"pairs": ["BTC", "ETH"], "_runtime_control": {"status": "x"}}}
    )
    assert existing == {"pairs": ["BTC", "ETH"]}  # control stripped, no synthesis

    reconstructed = BacktestService._reconstruct_restart_request_payload(
        {
            "name": "orphan",
            "selected_pairs": ["BTC/ETH", "ETH/SOL"],
            "start_date": "2026-01-01",
            "end_date": "2026-02-01",
            "strategy_payload_snapshot": {"name": "strat"},
        }
    )
    assert reconstructed["name"] == "orphan"
    assert reconstructed["pair_selection_mode"] == "input"
    assert reconstructed["pairs"] == ["BTC", "ETH", "SOL"]  # >=2 markets -> markets
    assert reconstructed["trading_parameters"]["resolution"] == "1HOUR"
    assert reconstructed["strategy_payload_snapshot"] == {"name": "strat"}
    assert "strategy_id" not in reconstructed  # None values stripped

    fallback = BacktestService._reconstruct_restart_request_payload(
        {
            "current_pair": "btc/eth",
            "initial_balance": None,
            "start_date": "2026-01-01",
            "end_date": "2026-02-01",
        }
    )
    assert fallback["selected_pairs"] == ["BTC/ETH"]
    assert fallback["initial_balance"] == 10000.0
    assert fallback["source"] == "api"


def test_reconstruct_restart_request_payload_needs_the_date_window():
    for run_data in (
        {"selected_pairs": ["BTC/ETH"], "end_date": "2026-02-01"},
        {"selected_pairs": ["BTC/ETH"], "start_date": "2026-01-01"},
        {"selected_pairs": ["BTC/ETH"], "start_date": " ", "end_date": ""},
    ):
        assert BacktestService._reconstruct_restart_request_payload(run_data) == {}


def test_request_payload_hash_ignores_control_and_task_keys():
    base = {"pairs": ["BTC", "ETH"], "start_date": "2026-01-01"}
    decorated = dict(
        base,
        _runtime_control={"status": "running"},
        _task_context={"worker": "w1"},
        _task_failure={"error_code": "X"},
    )
    assert BacktestService._request_payload_hash(
        base
    ) == BacktestService._request_payload_hash(decorated)
    different = dict(base, start_date="2026-02-01")
    assert BacktestService._request_payload_hash(
        base
    ) != BacktestService._request_payload_hash(different)


def test_build_task_context_overrides_and_metadata_precedence(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    context = BacktestService._build_task_context(
        {
            "pairs": ["BTC", "ETH"],
            "metadata": {"team": "core"},
            "_task_context": {
                "metadata": {"existing": True},
                "queue": "queued-original",
                "strategy_name": "old-name",
            },
            "strategy_payload_snapshot": {"name": "alpha", "version_number": 3},
            "requested_by_user_id": 7,
        },
        queue="high_priority",
        retry_count=2,
    )
    assert context["queue"] == "high_priority"  # override wins
    assert context["strategy_name"] == "alpha"  # snapshot beats existing
    assert context["source_strategy_version"] == 3
    assert context["pairs"] == ["BTC", "ETH"]
    assert context["selected_pairs"] == ["BTC/ETH"]
    assert context["environment"] == "local"
    # Computed metadata wins over request metadata, which wins over existing.
    assert context["metadata"]["team"] == "core"
    assert context["metadata"]["existing"] is True
    assert context["metadata"]["payload_hash"]
    assert context["retry_count"] == 2
    assert context["metadata"]["requested_by_user_id"] == 7


def test_task_context_failure_accessors():
    payload = {
        "_task_context": {"worker": "w1"},
        "_task_failure": {"error_code": "E1"},
    }
    assert BacktestService._task_context_from_request(payload) == {"worker": "w1"}
    assert BacktestService._task_failure_from_request(payload) == {"error_code": "E1"}
    assert BacktestService._task_context_from_request({"_task_context": "junk"}) == {}
    assert BacktestService._task_failure_from_request({}) == {}


def test_attach_history_fetch_summary():
    run_data = _run("r1", request={})
    attached = BacktestService._attach_history_fetch_summary(
        run_data, {"BTC": {"candles": 10}}
    )
    context = attached["request"]["_task_context"]
    assert "history_fetch_telemetry" in context["metadata"]


# ---------------------------------------------------------------------------
# Metrics math (deterministic formulas)
# ---------------------------------------------------------------------------


def test_build_metrics_returns_baseline_for_defaults():
    metrics = BacktestService._build_metrics({})
    assert metrics == {
        "total_pnl": 48.2,
        "win_rate": 0.59,
        "sharpe_ratio": 1.33,
        "max_drawdown_pct": 10.9,
        "total_trades": 24,
    }


def test_build_metrics_sensitivities():
    metrics = BacktestService._build_metrics(
        {
            "trading_parameters": {
                "zscore_threshold": 1.0,
                "stats_window": 25,
                "usd_per_trade": 20.0,
                "close_at_zscore_cross": False,
                "transaction_fee": 0.001,
                "slippage": 0.0005,
                "risk_free_rate": 0.03,
                "max_positions": 7,
            }
        }
    )
    # Baseline + every sensitivity applied; expectations mirror the code's
    # final rounding so the formulas stay verifiable to the last digit.
    assert metrics["total_pnl"] == pytest.approx(
        round(
            48.2
            + 4.0 * 0.5
            - 0.05 * 16
            + 0.08 * 10.0
            - 1.2
            - (0.001 * 4000.0 + 0.0005 * 4400.0)
            - 0.01 * 40.0
            - 2 * 0.25,
            1,
        ),
        abs=0.05,
    )
    assert metrics["win_rate"] == round(
        0.59 - 0.03 * 0.5 - 0.0025 * 4 - 0.001 * 10.0 - 0.02, 2
    )
    assert metrics["sharpe_ratio"] == round(
        1.33
        - 0.18 * 0.25
        - 0.002 * 16
        - 0.002 * 10.0
        - 0.05
        - (0.001 * 60 + 0.0005 * 60)
        - 0.01 * 0.6
        - 2 * 0.01,
        2,
    )
    assert metrics["max_drawdown_pct"] == round(
        10.9
        + 1.2 * 0.5
        + 0.12 * 4
        + 0.035 * 10.0
        + 0.6
        + (0.001 * 400.0 + 0.0005 * 1600.0)
        + 2 * 0.08,
        1,
    )
    # 24 + 5 (zscore) - 1 (window) + 1 (usd) - 3 (no cross-close) + 2 (slippage)
    assert metrics["total_trades"] == 24 + 5 - 1 + 1 - 3 + 2


def test_build_metrics_clamps_extreme_inputs():
    metrics = BacktestService._build_metrics(
        {"strategy_params": {"zscore_threshold": 50.0, "stats_window": 500}}
    )
    assert 0.25 <= metrics["win_rate"] <= 0.95
    assert -2.0 <= metrics["sharpe_ratio"] <= 5.0
    assert metrics["total_trades"] >= 1


def test_compute_sharpe_edges():
    assert BacktestService._compute_sharpe([], 1000.0) == 0.0
    assert BacktestService._compute_sharpe([5.0], 1000.0) == 0.0
    assert BacktestService._compute_sharpe([10.0, 10.0, 10.0], 1000.0) == 0.0
    sharpe = BacktestService._compute_sharpe([10.0, -5.0, 8.0], 1000.0)
    returns = np.array([10.0, -5.0, 8.0]) / 1000.0
    assert sharpe == pytest.approx(
        float(np.mean(returns) / np.std(returns) * math.sqrt(252))
    )


def test_compute_max_drawdown_pct():
    assert BacktestService._compute_max_drawdown_pct([], 1000.0) == 0.0
    assert BacktestService._compute_max_drawdown_pct([10.0, 10.0], 1000.0) == 0.0
    # 1000 -> +200 = 1200 peak, then -300 -> 900: dd = 300/1200 = 25%.
    assert BacktestService._compute_max_drawdown_pct(
        [200.0, -300.0], 1000.0
    ) == pytest.approx(25.0)


def test_build_daily_pnl_rows_sorted_with_trade_counts():
    rows = BacktestService._build_daily_pnl_rows(
        {"2026-01-02": -1.5, "2026-01-01": 3.25},
        [
            {"exit_timestamp": "2026-01-01T05:00:00Z"},
            {"exit_timestamp": "2026-01-01T09:00:00Z"},
            {"exit_timestamp": "2026-01-03T00:00:00Z"},
        ],
        "1HOUR",
    )
    assert [r["date"] for r in rows] == ["2026-01-01", "2026-01-02"]
    assert rows[0]["pnl"] == 3.25
    assert rows[0]["trades"] == 2
    assert rows[0]["candle_id"] == "2026-01-01|PORTFOLIO|1HOUR"
    assert rows[1]["trades"] == 0


def test_parse_date_variants():
    end = BacktestService._parse_date("2026-01-01", end_of_day=True)
    assert (end.hour, end.minute, end.second) == (23, 59, 59)
    start = BacktestService._parse_date("2026-01-01", end_of_day=False)
    assert (start.hour, start.minute) == (0, 0)
    stamped = BacktestService._parse_date("2026-01-01T12:00:00Z", end_of_day=True)
    assert stamped.hour == 12
    assert stamped.tzinfo is not None
    naive = BacktestService._parse_date("2026-01-01T12:00:00")
    assert naive.tzinfo is not None


def test_parse_timeout_seconds_matrix():
    assert BacktestService._parse_timeout_seconds({}) == 24 * 60 * 60
    assert (
        BacktestService._parse_timeout_seconds({"timeout_seconds": "junk"})
        == 24 * 60 * 60
    )
    assert BacktestService._parse_timeout_seconds({"timeout_seconds": 0.001}) == 1.0
    assert (
        BacktestService._parse_timeout_seconds({"timeout_seconds": 10**9})
        == 7 * 24 * 60 * 60
    )
    assert (
        BacktestService._parse_timeout_seconds(
            {"trading_parameters": {"timeout_seconds": 90}}
        )
        == 90
    )


# ---------------------------------------------------------------------------
# Await / runtime-control loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_await_with_deadline_branches():
    expired_awaitable = asyncio.sleep(0)
    with pytest.raises(TimeoutError, match="connecting"):
        await BacktestService._await_with_deadline(
            expired_awaitable, time.monotonic() - 1.0, "connecting"
        )
    expired_awaitable.close()

    async def _slow():
        await asyncio.sleep(5.0)

    with pytest.raises(TimeoutError, match="loading history"):
        await BacktestService._await_with_deadline(
            _slow(), time.monotonic() + 0.05, "loading history"
        )

    assert (
        await BacktestService._await_with_deadline(
            asyncio.sleep(0), time.monotonic() + 5.0, "ok"
        )
        is None
    )


@pytest.mark.asyncio
async def test_honor_runtime_control_cancel_and_passthrough():
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)

    run_data = _run("r1")
    with pytest.raises(asyncio.CancelledError):
        await service._honor_runtime_control(
            "r1", dict(run_data, cancel_requested=True), time.monotonic() + 5.0
        )

    repo.runs["r1"]["request"] = {
        "pairs": ["BTC", "ETH"],
        "_runtime_control": {"cancel_requested": True},
    }
    with pytest.raises(asyncio.CancelledError):
        await service._honor_runtime_control("r1", run_data, time.monotonic() + 5.0)

    # No pending control: returned untouched without persistence.
    repo.runs["r1"]["request"] = {"pairs": ["BTC", "ETH"]}
    result = await service._honor_runtime_control(
        "r1", run_data, time.monotonic() + 5.0
    )
    assert result is run_data
    assert repo.saved == []


@pytest.mark.asyncio
async def test_honor_runtime_control_pause_resumes(monkeypatch):
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    control_states = [{"pause_requested": True, "status": "pause_requested"}]
    repo.runs["r1"]["request"] = {"pairs": ["BTC", "ETH"]}

    def _overview(run_id):
        current = dict(control_states[0])
        if len(control_states) > 1:
            control_states.pop(0)
        return dict(
            _run("r1", request={"pairs": ["BTC", "ETH"], "_runtime_control": current})
        )

    repo.get_run_overview = _overview  # type: ignore[method-assign]
    checkpoints: List[int] = []

    async def _flip_to_resume():
        await asyncio.sleep(0.05)
        control_states.append(
            {"resume_requested": True, "pause_requested": False, "status": "running"}
        )

    flipper = asyncio.create_task(_flip_to_resume())
    resumed = await asyncio.wait_for(
        service._honor_runtime_control(
            "r1",
            _run("r1"),
            time.monotonic() + 30.0,
            checkpoint_writer=lambda: checkpoints.append(1),
        ),
        timeout=10.0,
    )
    await flipper
    assert resumed["status"] == "running"
    assert resumed["current_task"] == "processing pair"
    assert checkpoints == [1]
    assert repo.saved[0]["status"] == "paused"
    assert resumed["request"]["_runtime_control"]["action"] == "resume"


@pytest.mark.asyncio
async def test_honor_runtime_control_timeout_and_cancel_while_paused():
    repo = _FakeRepo(
        [_run("r1", request={"_runtime_control": {"pause_requested": True}})]
    )
    service = _make_service(repo)

    with pytest.raises(TimeoutError, match="while paused"):
        await service._honor_runtime_control(
            "r1",
            _run("r1"),
            time.monotonic() - 1.0,  # deadline already exhausted
            checkpoint_writer=lambda: None,
        )

    # Cancel arrives while paused: the refreshed overview carries the cancel
    # flag and the loop raises CancelledError on its next control check.
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    control_states: List[Dict[str, Any]] = [
        {"pause_requested": True, "status": "pause_requested"}
    ]

    def _overview(run_id):
        current = dict(control_states[0])
        if len(control_states) > 1:
            control_states.pop(0)
        return dict(
            _run(
                "r1",
                request={"pairs": ["BTC", "ETH"], "_runtime_control": current},
            )
        )

    repo.get_run_overview = _overview  # type: ignore[method-assign]

    async def _flip_soon():
        await asyncio.sleep(0.05)
        control_states.append(
            {
                "pause_requested": True,
                "cancel_requested": True,
                "status": "cancelling",
            }
        )

    flipper = asyncio.create_task(_flip_soon())
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(
            service._honor_runtime_control("r1", _run("r1"), time.monotonic() + 30.0),
            timeout=10.0,
        )
    await flipper


@pytest.mark.asyncio
async def test_honor_runtime_control_stays_paused_and_persists(monkeypatch):
    repo = _FakeRepo(
        [
            _run(
                "r1",
                request={
                    "pairs": ["BTC", "ETH"],
                    "_runtime_control": {"pause_requested": True},
                },
            )
        ]
    )
    service = _make_service(repo)
    original_sleep = asyncio.sleep

    async def _short_sleep(seconds):
        await original_sleep(min(seconds, 0.02))

    monkeypatch.setattr(sb.asyncio, "sleep", _short_sleep)
    task = asyncio.create_task(
        service._honor_runtime_control("r1", _run("r1"), time.monotonic() + 0.3)
    )
    deadline = time.monotonic() + 5.0
    while len(repo.saved) < 3 and time.monotonic() < deadline:
        await original_sleep(0.02)
    assert not task.done(), "must stay paused while control holds pause_requested"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert all(saved["status"] == "paused" for saved in repo.saved[1:])


# ---------------------------------------------------------------------------
# Ops / recovery / mutation service methods
# ---------------------------------------------------------------------------


def test_find_orphaned_in_progress_runs_filters():
    repo = _FakeRepo()
    service = _make_service(repo)
    runs = [
        _run("active-asyncio", status="running"),
        _run("orphaned", status="running"),
        _run("pending-orphan", status="PENDING"),
        _run("done", status="completed"),
        {"status": "running"},  # no run_id: ignored
        _run("terminal-alias", status="error"),
    ]
    BacktestService._tasks["active-asyncio"] = object()  # type: ignore[assignment]
    orphaned = service._find_orphaned_in_progress_runs(runs)
    assert [r["run_id"] for r in orphaned] == ["orphaned", "pending-orphan"]
    assert service._find_orphaned_in_progress_runs([]) == []


def test_list_interrupted_runs_for_ops_partitions():
    repo = _FakeRepo()
    repo.list_runs_payload = [
        _run("orphan", status="running"),
        _run(
            "interrupted",
            status="failed",
            error=BacktestService._INTERRUPTION_ERROR,
        ),
        _run("other-failure", status="failed", error="normal failure"),
    ]
    service = _make_service(repo)
    result = service.list_interrupted_runs_for_ops(limit=10)
    assert result["orphaned_count"] == 1
    assert result["interrupted_count"] == 1
    assert result["orphaned_in_progress"][0]["run_id"] == "orphan"
    assert result["interrupted_runs"][0]["run_id"] == "interrupted"


def test_reconcile_interrupted_runs_dry_run_vs_apply():
    repo = _FakeRepo([_run("orphan", status="running")])
    service = _make_service(repo)

    dry = service.reconcile_interrupted_runs(dry_run=True)
    assert dry["dry_run"] is True
    assert dry["candidate_count"] == 1
    assert dry["reconciled_count"] == 0
    assert repo.saved == []

    applied = service.reconcile_interrupted_runs(dry_run=False)
    assert applied["reconciled_count"] == 1
    assert repo.saved[-1]["status"] == "failed"
    assert repo.saved[-1]["error"] == BacktestService._INTERRUPTION_ERROR


def test_update_backtest_metadata_merge_replace_and_missing():
    repo = _FakeRepo(
        [
            _run(
                "r1",
                request={
                    "pairs": ["BTC", "ETH"],
                    "_task_context": {"metadata": {"keep": 1, "stale": 2}},
                },
            )
        ]
    )
    service = _make_service(repo)

    assert service.update_backtest_metadata("missing", {"a": 1}) is None

    merged = service.update_backtest_metadata("r1", {"new": 3})
    assert merged["metadata"] == {"keep": 1, "stale": 2, "new": 3}

    replaced = service.update_backtest_metadata("r1", {"only": 1}, merge=False)
    assert replaced["metadata"] == {"only": 1}
    persisted_request = repo.saved[-1]["request"]
    assert persisted_request["metadata"] == {"only": 1}
    assert persisted_request["_task_context"]["metadata"] == {"only": 1}


def test_mark_backtest_retrying_missing_run_returns_none():
    service = _make_service(_FakeRepo())
    assert (
        service.mark_backtest_retrying(
            "missing", error="boom", countdown_seconds=30.0, retry_count=1
        )
        is None
    )


def test_revoke_celery_backtest_none_and_failure(monkeypatch):
    service = _make_service(_FakeRepo())
    service._revoke_celery_backtest(None)  # no task id: no-op

    from src.infrastructure.workers import celery_app as celery_app_module

    def _boom(*args, **kwargs):
        raise RuntimeError("revoke exploded")

    monkeypatch.setattr(celery_app_module.celery_app.control, "revoke", _boom)
    service._revoke_celery_backtest("task-1")  # failure is swallowed + logged


def test_enqueue_celery_backtest_import_failure(monkeypatch):
    service = _make_service(_FakeRepo())
    monkeypatch.setitem(sys.modules, "src.infrastructure.workers.backtest_tasks", None)
    with pytest.raises(RuntimeError, match="Celery backtest worker is not available"):
        service._enqueue_celery_backtest("r1")


def test_mark_celery_enqueue_failed_persists_failure(_quiet_job_manager):
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    failed = service._mark_celery_enqueue_failed(
        _run("r1"), RuntimeError("broker down"), action="enqueue_failed"
    )
    assert failed["status"] == "failed"
    assert failed["current_task"] == "enqueue failed"
    assert failed["error"] == "broker down"
    assert failed["worker_backend"] == "celery"
    control = BacktestService._get_runtime_control(failed)
    assert control["action"] == "enqueue_failed"
    failure = BacktestService._task_failure_from_request(failed["request"])
    assert failure["error_code"] == "BACKTEST_ENQUEUE_FAILED"
    assert failure["error_message"] == "broker down"


@pytest.mark.asyncio
async def test_restart_interrupted_existing_run_edge_paths(monkeypatch):
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)

    def _backend(value: str):
        async def _resolve(cls):
            return value

        return _resolve

    missing = await service._restart_interrupted_existing_run({"run_id": "missing"})
    assert missing is None

    repo.runs["r1"]["request"] = None
    no_request = await service._restart_interrupted_existing_run({"run_id": "r1"})
    assert no_request is None
    BacktestService._runs.pop("r1", None)  # drop the stale cache-first entry

    monkeypatch.setattr(
        BacktestService, "_resolve_worker_backend", classmethod(_backend("nats"))
    )
    repo.runs["r1"] = _run("r1")
    nats_skipped = await service._restart_interrupted_existing_run({"run_id": "r1"})
    assert nats_skipped is None

    monkeypatch.setattr(
        BacktestService, "_resolve_worker_backend", classmethod(_backend("celery"))
    )

    def _explode(run_id, task_context=None):
        raise RuntimeError("enqueue failed")

    monkeypatch.setattr(service, "_enqueue_celery_backtest", _explode)
    repo.runs["r1"] = _run("r1")
    failed = await service._restart_interrupted_existing_run({"run_id": "r1"})
    assert failed is not None
    assert failed["status"] == "failed"
    control = BacktestService._get_runtime_control(failed)
    assert control["action"] == "auto_recover_enqueue_failed"


def test_prepare_existing_run_recovery_backend_split():
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    celery_row = service._prepare_existing_run_recovery(
        _run("r1"), worker_backend="celery", worker_task_id="task-9"
    )
    assert celery_row["status"] == "pending"
    assert celery_row["current_task"] == "auto recovery queued"
    assert celery_row["worker_task_id"] == "task-9"

    asyncio_row = service._prepare_existing_run_recovery(
        _run("r1"), worker_backend="asyncio", worker_task_id="r1"
    )
    assert asyncio_row["status"] == "running"
    assert asyncio_row["current_task"] == "auto recovery running"


@pytest.mark.asyncio
async def test_auto_recover_interrupted_runs_off_mode():
    repo = _FakeRepo()
    repo.list_runs_payload = [_run("orphan", status="running")]
    service = _make_service(repo)
    result = await service.auto_recover_interrupted_runs(mode="off")
    assert result["mode"] == "off"
    assert result["candidate_count"] == 1
    assert result["marked_failed_count"] == 0
    assert result["restarted_count"] == 0
    assert result["skipped_count"] == 1
    assert repo.saved == []


@pytest.mark.asyncio
async def test_auto_recover_invalid_mode_falls_back_to_mark_failed():
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    repo = _FakeRepo()
    repo.list_runs_payload = [_run("orphan", status="running", updated_at=old)]
    service = _make_service(repo)
    result = await service.auto_recover_interrupted_runs(mode="nonsense")
    assert result["mode"] == "mark_failed"
    assert result["marked_failed_count"] == 1
    assert repo.saved[-1]["status"] == "failed"


def test_handle_task_done_paths(caplog):
    service = _make_service(_FakeRepo())

    class _CancelledTask:
        def cancelled(self):
            return True

    service._handle_task_done("r1", _CancelledTask())  # returns silently

    class _FailedTask:
        def cancelled(self):
            return False

        def exception(self):
            return RuntimeError("task crashed")

    with caplog.at_level(
        "ERROR", logger="src.infrastructure.use_cases.service_backtest"
    ):
        service._handle_task_done("r2", _FailedTask())
    assert any("unhandled exception" in message for message in caplog.messages)

    class _OkTask:
        def cancelled(self):
            return False

        def exception(self):
            return None

    service._handle_task_done("r3", _OkTask())


def test_list_backtest_runs_maps_through_stale_resolution():
    repo = _FakeRepo()
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    repo.list_runs_payload = [
        _run("stale-run", status="running", updated_at=old, request={})
    ]
    repo.count_payload = 5
    service = _make_service(repo)
    listing = service.list_backtest_runs(limit=10, status_filter="running")
    assert listing.total == 5
    assert listing.runs[0]["status"] == "stale"


# ---------------------------------------------------------------------------
# Pair simulator (seeded, deterministic)
# ---------------------------------------------------------------------------


def _sine_series(
    n: int, base: float = 100.0
) -> tuple[List[str], np.ndarray, np.ndarray]:
    rng = np.random.default_rng(42)
    hours = np.arange(n)
    prices_b = base + 0.01 * hours + rng.normal(0, 0.05, n)
    spread = 10.0 * np.sin(hours / 6.0)
    prices_a = 1.2 * prices_b + spread
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = [
        (start + timedelta(hours=int(h))).isoformat().replace("+00:00", "Z")
        for h in hours
    ]
    return timestamps, prices_a, prices_b


@pytest.mark.asyncio
async def test_simulate_pair_seeded_round_trip(monkeypatch):
    monkeypatch.setenv("BACKTEST_SIMULATION_YIELD_EVERY_STEPS", "5")
    timestamps, prices_a, prices_b = _sine_series(400)
    service = _make_service(_FakeRepo())
    heartbeats = []

    async def _heartbeat():
        heartbeats.append(1)

    trades, snapshots, daily_pnl = await service._simulate_pair(
        run_id="r1",
        market_a="BTC",
        market_b="ETH",
        timestamps=timestamps,
        prices_a=prices_a,
        prices_b=prices_b,
        params={"stats_window": 20, "zscore_threshold": 1.0, "usd_per_trade": 10.0},
        trade_index_offset=0,
        heartbeat_callback=_heartbeat,
    )
    assert len(trades) >= 2
    assert len(snapshots) == len(trades)
    assert heartbeats  # inline heartbeat refresh ran at yield points
    for trade in trades:
        assert trade["market_1"] == "BTC"
        assert trade["market_2"] == "ETH"
        assert trade["win"] == (trade["pnl_usd"] > 0)
        assert trade["duration_hours"] >= 0.0
        assert trade["trade_id"].startswith("t-r1-")
    assert daily_pnl
    assert sum(daily_pnl.values()) == pytest.approx(
        sum(t["pnl_usd"] for t in trades), abs=1e-3
    )


@pytest.mark.asyncio
async def test_simulate_pair_heartbeat_failure_is_tolerated(monkeypatch):
    monkeypatch.setenv("BACKTEST_SIMULATION_YIELD_EVERY_STEPS", "5")
    timestamps, prices_a, prices_b = _sine_series(120)
    service = _make_service(_FakeRepo())
    calls = {"n": 0}

    async def _flaky_heartbeat():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("heartbeat channel busy")

    trades, _, _ = await service._simulate_pair(
        run_id="r1",
        market_a="BTC",
        market_b="ETH",
        timestamps=timestamps,
        prices_a=prices_a,
        prices_b=prices_b,
        params={"stats_window": 10, "zscore_threshold": 1.0},
        trade_index_offset=0,
        heartbeat_callback=_flaky_heartbeat,
    )
    assert calls["n"] >= 2  # the failing call did not abort the simulation


@pytest.mark.asyncio
async def test_simulate_pair_guards():
    service = _make_service(_FakeRepo())
    timestamps = ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"]

    short = await service._simulate_pair(
        "r1",
        "BTC",
        "ETH",
        timestamps,
        np.array([1.0, 1.1]),
        np.array([1.0, 1.0]),
        {"stats_window": 20},
        0,
    )
    assert short == ([], [], {})

    flat = await service._simulate_pair(
        "r1",
        "BTC",
        "ETH",
        ["2026-01-01T00:00:00Z"] * 50,
        np.linspace(1, 2, 50),
        np.full(50, 7.0),
        {"stats_window": 5},
        0,
    )
    assert flat == ([], [], {})


# ---------------------------------------------------------------------------
# _execute_backtest validation / timeout / completion seams
# ---------------------------------------------------------------------------


def _execute_request(**overrides: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "pairs": ["BTC", "ETH"],
        "start_date": "2026-01-01",
        "end_date": "2026-01-10",
        "trading_parameters": {"stats_window": 10, "zscore_threshold": 1.0},
    }
    payload.update(overrides)
    return payload


class _FakeClient:
    def __init__(self):
        class _Indexer:
            class _Markets:
                def get_perpetual_markets(self):
                    raise RuntimeError("markets endpoint down")

            markets = _Markets()

        class _Node:
            async def close(self):
                raise RuntimeError("close exploded")  # swallowed in finally

        self.indexer = _Indexer()
        self.node = _Node()


@pytest.mark.asyncio
async def test_execute_existing_backtest_raises_for_missing_payload(monkeypatch):
    service = _make_service(_FakeRepo())

    with pytest.raises(ValueError, match="not found"):
        await service.execute_existing_backtest("missing")

    repo = _FakeRepo([_run("r1", request=None)])
    service = _make_service(repo)
    with pytest.raises(ValueError, match="no request payload"):
        await service.execute_existing_backtest("r1")


@pytest.mark.asyncio
async def test_execute_backtest_missing_run_returns_silently():
    service = _make_service(_FakeRepo())
    await service._execute_backtest("missing", _execute_request(), None)


@pytest.mark.asyncio
async def test_execute_backtest_strategy_and_pair_and_date_validation(monkeypatch):
    async def _explode_connect():
        raise AssertionError("connect must not be reached")

    monkeypatch.setattr(sb, "connect_dydx", _explode_connect)

    # strategy_id without a snapshot payload
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    with pytest.raises(ValueError, match="STRATEGY_PAYLOAD_MISSING"):
        await service._execute_backtest(
            "r1",
            _execute_request(strategy_id="strat-1"),
            None,
            propagate_exceptions=True,
        )
    # The failure path persists via update_run_progress, not a full save.
    failed = repo.progress_updates[-1]
    assert failed["status"] == "failed"
    failure = BacktestService._task_failure_from_request(failed["request"])
    assert failure["error_code"] == "STRATEGY_PAYLOAD_MISSING"

    # no pair selection derivable
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    with pytest.raises(ValueError, match="SELECTED_PAIRS_MISSING"):
        await service._execute_backtest(
            "r1", _execute_request(pairs=[]), None, propagate_exceptions=True
        )

    # end before start
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    with pytest.raises(ValueError, match="end_date must be after start_date"):
        await service._execute_backtest(
            "r1",
            _execute_request(start_date="2026-02-01", end_date="2026-01-01"),
            None,
            propagate_exceptions=True,
        )


@pytest.mark.asyncio
async def test_execute_backtest_volatility_mode_precache_and_completion(monkeypatch):
    monkeypatch.setenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS", "0.05")

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(sb, "connect_dydx", _fake_connect)
    monkeypatch.setattr(
        BacktestService,
        "_prioritize_pairs",
        classmethod(
            lambda cls, pair_markets, mode, market_map, history_by_market: pair_markets
        ),
    )

    fetched: List[str] = []

    async def _fake_fetch_history(**kwargs):
        market = kwargs.get("market")
        fetched.append(str(market))
        return {"2026-01-01T00:00:00Z": 100.0, "2026-01-01T01:00:00Z": 100.1}

    monkeypatch.setattr(sb._history, "_fetch_market_history", _fake_fetch_history)

    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    await service._execute_backtest(
        "r1",
        _execute_request(
            pair_selection_mode="volatility",
            max_pairs="not-a-number",  # malformed: ignored, no cap
        ),
        None,
        propagate_exceptions=True,
    )
    # Pre-cache loop fetched both markets once; per-pair lookups hit the cache.
    assert set(fetched) == {"BTC", "ETH"}
    completed = repo.saved[-1]
    assert completed["status"] == "completed"
    assert completed["progress_pct"] == 100.0
    assert completed["current_pair"] == "complete"
    # Empty (too-short) history -> zero trades but valid totals persisted.
    assert completed["total_trades"] == 0


@pytest.mark.asyncio
async def test_execute_backtest_timeout_propagates(monkeypatch):
    monkeypatch.setenv("BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS", "0.05")

    async def _slow_connect():
        await asyncio.sleep(5.0)
        return _FakeClient()

    monkeypatch.setattr(sb, "connect_dydx", _slow_connect)
    repo = _FakeRepo([_run("r1")])
    service = _make_service(repo)
    with pytest.raises(TimeoutError):
        await service._execute_backtest(
            "r1",
            _execute_request(timeout_seconds=1.0),
            None,
            propagate_exceptions=True,
        )
    timed_out = repo.progress_updates[-1]
    assert timed_out["status"] == "timeout"
    assert timed_out["current_task"] == "timeout"
    assert timed_out["error"]
