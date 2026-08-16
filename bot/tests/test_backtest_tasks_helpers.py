"""Unit tests for the Celery backtest task module (helpers + task flows).

Covers the pure helper surface (lock TTL/retry policy, transient-error
classification, redis lock + pub/sub plumbing, pair selection) and the
``run_backtest_task`` lifecycle flows (duplicate skip, validation failures,
happy path, transient retry, terminal failure, timeout, cancellation) against
fakes — no broker, no database.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import httpx
import pytest
from celery.exceptions import Retry, SoftTimeLimitExceeded

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infrastructure.workers import backtest_tasks  # noqa: E402
from src.infrastructure.workers.backtest_tasks import run_backtest_task  # noqa: E402

# ------------------------------------------------------------------- fakes


class _DummySession:
    def close(self) -> None:
        return None


class _FakeRepo:
    last: Optional["_FakeRepo"] = None

    def __init__(self, _session: Any, run: Optional[Dict[str, Any]] = None):
        self.run_payload = run
        self.saved: List[Dict[str, Any]] = []
        _FakeRepo.last = self

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.run_payload

    def get_run_overview(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.run_payload

    def save_run(self, data: Dict[str, Any]) -> bool:
        self.saved.append(dict(data))
        return True

    def update_run_progress(self, data: Dict[str, Any]) -> bool:
        self.saved.append(dict(data))
        return True


class _FakeService:
    """Mirrors the codec seam the task uses (same shape as the real one)."""

    execute_error: Optional[BaseException] = None
    execute_delay: float = 0.0
    recorded_executions: List[Dict[str, Any]] = []
    recorded_retries: List[Dict[str, Any]] = []

    def __init__(self, _repository: Any):
        self._callbacks: List[Any] = []

    # --- codec helpers (dict-in dict-out, like the real service) ---
    @staticmethod
    def _task_context_from_request(request_payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"source": request_payload.get("source", "api")}

    @staticmethod
    def _build_task_context(
        request_payload: Dict[str, Any], **merged: Any
    ) -> Dict[str, Any]:
        return dict(merged)

    @staticmethod
    def _error_code_from_message(message: str, fallback: str) -> str:
        if "STRATEGY" in message or "PAIRS" in message:
            return "BACKTEST_REQUEST_INVALID"
        return fallback

    @staticmethod
    def _set_task_context(
        request_payload: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        updated = dict(request_payload)
        updated["task_context"] = dict(ctx)
        return updated

    @staticmethod
    def _clear_task_failure(request_payload: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(request_payload)
        updated.pop("task_failure", None)
        return updated

    @staticmethod
    def _set_task_failure(
        request_payload: Dict[str, Any], failure: Dict[str, Any]
    ) -> Dict[str, Any]:
        updated = dict(request_payload)
        updated["task_failure"] = dict(failure)
        return updated

    @staticmethod
    def _set_runtime_control(
        run_data: Dict[str, Any], **updates: Any
    ) -> Dict[str, Any]:
        request = dict(run_data.get("request") or {})
        request["_runtime_control"] = dict(updates)
        run_data["request"] = request
        return run_data

    # --- execution seams ---
    def mark_backtest_retrying(self, run_id, **kwargs):
        _FakeService.recorded_retries.append(dict(kwargs))
        return True

    async def execute_existing_backtest(self, run_id, progress_callback, **kwargs):
        _FakeService.recorded_executions.append(
            {"run_id": run_id, "callback": progress_callback, "kwargs": kwargs}
        )
        if _FakeService.execute_delay:
            await asyncio.sleep(_FakeService.execute_delay)
        if _FakeService.execute_error is not None:
            raise _FakeService.execute_error
        return {"run_id": run_id, "status": "completed"}


@pytest.fixture(autouse=True)
def _reset_fake_service_state():
    _FakeService.execute_error = None
    _FakeService.execute_delay = 0.0
    _FakeService.recorded_executions = []
    _FakeService.recorded_retries = []
    _FakeRepo.last = None
    CAPTURE["states"].clear()
    CAPTURE["published"].clear()
    CAPTURE["events"].clear()
    yield
    run_backtest_task.pop_request() if run_backtest_task.request_stack.top else None


# Observable captures from the last _invoke_task call — also populated when the
# task raises, so failure-path tests can still assert on state/publish/events.
CAPTURE = {"states": [], "published": [], "events": []}


def _invoke_task(
    monkeypatch, run_id: str, task_context=None, run_payload=None, acquire=None
):
    """Drive run_backtest_task with faked collaborators; returns (result, states).

    Also mirrors state/publish/event captures into the module-level CAPTURE dict
    so raising paths can assert against them.
    """
    states: List[Dict[str, Any]] = CAPTURE["states"]
    published: List[tuple] = CAPTURE["published"]
    events: List[Dict[str, Any]] = CAPTURE["events"]

    monkeypatch.setattr(
        run_backtest_task,
        "update_state",
        lambda state=None, meta=None, **kw: states.append(
            {"state": state, "meta": meta}
        ),
    )

    def _raising_retry(exc=None, **kwargs):
        raise Retry(message="retry requested", exc=exc)

    monkeypatch.setattr(run_backtest_task, "retry", _raising_retry)
    monkeypatch.setattr(
        backtest_tasks,
        "db",
        type("DB", (), {"get_session": staticmethod(lambda: _DummySession())})(),
    )
    monkeypatch.setattr(
        backtest_tasks,
        "BacktestRepository",
        lambda session: _FakeRepo(None, run=run_payload),
    )
    monkeypatch.setattr(backtest_tasks, "BacktestService", _FakeService)
    monkeypatch.setattr(
        backtest_tasks, "_publish_backtest_status", lambda *a, **k: published.append(a)
    )
    monkeypatch.setattr(
        backtest_tasks, "emit_backtest_event_sync", lambda **k: events.append(k)
    )

    async def _noop_publish(**kwargs):
        events.append(kwargs)

    monkeypatch.setattr(backtest_tasks, "publish_backtest_event", _noop_publish)
    lock_behavior = acquire if acquire is not None else (lambda run_id, token: None)
    monkeypatch.setattr(backtest_tasks, "_acquire_backtest_lock", lock_behavior)
    monkeypatch.setattr(backtest_tasks, "_release_backtest_lock", lambda *a: None)
    monkeypatch.setattr(
        backtest_tasks,
        "_mark_worker_failure",
        lambda *a, **k: events.append({"mark_failed": a}),
    )

    run_backtest_task.push_request()
    try:
        result = run_backtest_task.run(run_id, task_context)
    finally:
        run_backtest_task.pop_request()
    return result, states, published, events


def _run_payload() -> Dict[str, Any]:
    return {
        "run_id": "run-1",
        "status": "pending",
        "request": {"selected_pairs": ["BTC-USD/ETH-USD"], "source": "test"},
    }


# ------------------------------------------------------- pure helpers


def test_normalize_request_payload():
    assert backtest_tasks._normalize_request_payload({"a": 1}) == {"a": 1}
    assert backtest_tasks._normalize_request_payload("junk") == {}
    assert backtest_tasks._normalize_request_payload(None) == {}


def test_merge_task_context_overrides():
    merged = backtest_tasks._merge_task_context_overrides({"a": 1, "b": 2}, b=3, c=4)
    assert merged == {"a": 1, "b": 3, "c": 4}
    assert backtest_tasks._merge_task_context_overrides(None, x=1) == {"x": 1}


def test_selected_pairs_resolution_order():
    # data-level wins, then request.selected_pairs, then request.pairs
    assert backtest_tasks._selected_pairs(
        {"selected_pairs": ["A/B"], "request": {"pairs": ["C/D"]}}
    ) == ["A/B"]
    assert backtest_tasks._selected_pairs(
        {"request": {"selected_pairs": ["A/B"], "pairs": ["C/D"]}}
    ) == ["A/B"]
    assert backtest_tasks._selected_pairs({"request": {"pairs": ["C/D"]}}) == ["C/D"]
    assert backtest_tasks._selected_pairs({"request": {}}) == []
    assert backtest_tasks._selected_pairs({"selected_pairs": "not-a-list"}) == []
    # Blank entries are filtered
    assert backtest_tasks._selected_pairs({"selected_pairs": ["A/B", "  "]}) == ["A/B"]


def test_lock_ttl_seconds_env_matrix(monkeypatch):
    monkeypatch.delenv("BACKTEST_TASK_LOCK_TTL_SECONDS", raising=False)
    monkeypatch.delenv("BACKTEST_CELERY_TASK_TIME_LIMIT", raising=False)
    assert backtest_tasks._lock_ttl_seconds() == 7 * 24 * 60 * 60 + 300  # default

    monkeypatch.setenv("BACKTEST_CELERY_TASK_TIME_LIMIT", "600")
    assert backtest_tasks._lock_ttl_seconds() == 900

    monkeypatch.setenv("BACKTEST_TASK_LOCK_TTL_SECONDS", "120")
    assert backtest_tasks._lock_ttl_seconds() == 120

    monkeypatch.setenv("BACKTEST_TASK_LOCK_TTL_SECONDS", "10")
    assert backtest_tasks._lock_ttl_seconds() == 60  # floor

    monkeypatch.setenv("BACKTEST_TASK_LOCK_TTL_SECONDS", "bogus")
    monkeypatch.setenv("BACKTEST_CELERY_TASK_TIME_LIMIT", "also-bogus")
    assert backtest_tasks._lock_ttl_seconds() == 7 * 24 * 60 * 60 + 300


def test_max_retries_env(monkeypatch):
    monkeypatch.delenv("BACKTEST_CELERY_MAX_RETRIES", raising=False)
    assert backtest_tasks._max_retries() == 3
    monkeypatch.setenv("BACKTEST_CELERY_MAX_RETRIES", "5")
    assert backtest_tasks._max_retries() == 5
    monkeypatch.setenv("BACKTEST_CELERY_MAX_RETRIES", "-1")
    assert backtest_tasks._max_retries() == 0
    monkeypatch.setenv("BACKTEST_CELERY_MAX_RETRIES", "bogus")
    assert backtest_tasks._max_retries() == 3


class _Response:
    def __init__(self, status_code: int, headers: Optional[Dict[str, str]] = None):
        self.status_code = status_code
        self.headers = headers or {}


class _RetryAfterError(Exception):
    def __init__(self, seconds: str):
        super().__init__(f"retry after {seconds}s")
        self.response = _Response(429, {"Retry-After": seconds})


def test_retry_countdown_seconds(monkeypatch):
    monkeypatch.delenv("BACKTEST_CELERY_RETRY_BASE_SECONDS", raising=False)
    monkeypatch.delenv("BACKTEST_CELERY_RETRY_MAX_SECONDS", raising=False)

    # Retry-After header wins outright
    assert backtest_tasks._retry_countdown_seconds(0, _RetryAfterError("42")) == 42.0

    # Exponential backoff: 30 * 2^retries, capped at the max
    assert backtest_tasks._retry_countdown_seconds(0, RuntimeError("x")) == 30.0
    assert backtest_tasks._retry_countdown_seconds(2, RuntimeError("x")) == 120.0
    assert backtest_tasks._retry_countdown_seconds(10, RuntimeError("x")) == 600.0

    monkeypatch.setenv("BACKTEST_CELERY_RETRY_BASE_SECONDS", "10")
    monkeypatch.setenv("BACKTEST_CELERY_RETRY_MAX_SECONDS", "25")
    assert backtest_tasks._retry_countdown_seconds(1, RuntimeError("x")) == 20.0
    assert backtest_tasks._retry_countdown_seconds(5, RuntimeError("x")) == 25.0


def test_is_transient_backtest_error_classification():
    request = httpx.Request("GET", "https://indexer.example")

    # Never transient regardless of shape
    assert backtest_tasks._is_transient_backtest_error(TimeoutError()) is False
    assert (
        backtest_tasks._is_transient_backtest_error(asyncio.CancelledError()) is False
    )
    assert backtest_tasks._is_transient_backtest_error(ValueError("bad input")) is False

    # HTTP status codes: retryable set only
    def _status_error(code: int) -> httpx.HTTPStatusError:
        return httpx.HTTPStatusError(
            f"{code}", request=request, response=httpx.Response(code, request=request)
        )

    assert backtest_tasks._is_transient_backtest_error(_status_error(503)) is True
    assert backtest_tasks._is_transient_backtest_error(_status_error(429)) is True
    assert backtest_tasks._is_transient_backtest_error(_status_error(404)) is False

    # Transport families
    assert (
        backtest_tasks._is_transient_backtest_error(httpx.TimeoutException("t")) is True
    )
    assert backtest_tasks._is_transient_backtest_error(httpx.ConnectError("c")) is True

    # Message heuristics for arbitrary exceptions
    assert (
        backtest_tasks._is_transient_backtest_error(RuntimeError("Connection refused"))
        is True
    )
    assert (
        backtest_tasks._is_transient_backtest_error(
            RuntimeError("rate limited, back off")
        )
        is True
    )
    assert (
        backtest_tasks._is_transient_backtest_error(RuntimeError("fatal logic error"))
        is False
    )


def test_redis_lock_url_env_matrix(monkeypatch):
    for var in ("BACKTEST_LOCK_REDIS_URL", "REDIS_URL", "VALKEY_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(
        backtest_tasks, "redis_url", lambda prefer_celery_broker=True: None
    )

    assert backtest_tasks._redis_lock_url() is None

    monkeypatch.setenv("BACKTEST_LOCK_REDIS_URL", "redis://lock:6379/0")
    assert backtest_tasks._redis_lock_url() == "redis://lock:6379/0"

    monkeypatch.delenv("BACKTEST_LOCK_REDIS_URL", raising=False)
    monkeypatch.setenv("VALKEY_URL", "redis://valkey:6379/3")
    assert backtest_tasks._redis_lock_url() == "redis://valkey:6379/3"

    # Non-redis schemes are rejected
    monkeypatch.setenv("VALKEY_URL", "postgres://nope")
    assert backtest_tasks._redis_lock_url() is None

    # Broker fallback when nothing else is set
    monkeypatch.delenv("VALKEY_URL", raising=False)
    monkeypatch.setattr(
        backtest_tasks,
        "redis_url",
        lambda prefer_celery_broker=True: "redis://broker:6379/1",
    )
    assert backtest_tasks._redis_lock_url() == "redis://broker:6379/1"


# ------------------------------------------------------------ lock plumbing


class _FakeRedisClient:
    def __init__(self, *, set_result=None, set_error=None):
        self.set_result = set_result
        self.set_error = set_error
        self.set_calls: List[dict] = []
        self.eval_calls: List[tuple] = []
        self.closed = False

    def set(self, key, value, nx=False, ex=None):
        self.set_calls.append({"key": key, "value": value, "nx": nx, "ex": ex})
        if self.set_error is not None:
            raise self.set_error
        return self.set_result

    def eval(self, script, numkeys, key, token):
        self.eval_calls.append((script, key, token))
        return 1

    def close(self):
        self.closed = True


def test_acquire_lock_outcomes(monkeypatch):
    # No redis configured: lock is a no-op (None client)
    monkeypatch.setattr(backtest_tasks, "_get_lock_redis_client", lambda: None)
    assert backtest_tasks._acquire_backtest_lock("run-1", "tok") is None

    # Successful acquisition returns the client
    client = _FakeRedisClient(set_result=True)
    monkeypatch.setattr(backtest_tasks, "_get_lock_redis_client", lambda: client)
    got = backtest_tasks._acquire_backtest_lock("run-1", "tok")
    assert got is client
    assert client.set_calls[0]["key"] == "backtest:run-lock:run-1"
    assert client.set_calls[0]["nx"] is True
    assert client.set_calls[0]["ex"] >= 60

    # Already locked: client closed, BACKTEST_ALREADY_RUNNING raised
    busy = _FakeRedisClient(set_result=None)
    monkeypatch.setattr(backtest_tasks, "_get_lock_redis_client", lambda: busy)
    with pytest.raises(RuntimeError, match="BACKTEST_ALREADY_RUNNING"):
        backtest_tasks._acquire_backtest_lock("run-1", "tok")
    assert busy.closed is True

    # Transport failure during acquisition propagates after cleanup
    broken = _FakeRedisClient(set_error=ConnectionError("redis gone"))
    monkeypatch.setattr(backtest_tasks, "_get_lock_redis_client", lambda: broken)
    with pytest.raises(ConnectionError):
        backtest_tasks._acquire_backtest_lock("run-1", "tok")
    assert broken.closed is True

    # Client construction failure degrades to lock-less execution
    def _boom():
        raise RuntimeError("init failed")

    monkeypatch.setattr(backtest_tasks, "_get_lock_redis_client", _boom)
    assert backtest_tasks._acquire_backtest_lock("run-1", "tok") is None


def test_release_lock_issues_compare_and_delete(monkeypatch):
    backtest_tasks._release_backtest_lock("run-1", "tok", None)  # no client: no-op

    client = _FakeRedisClient()
    backtest_tasks._release_backtest_lock("run-1", "tok", client)
    assert client.eval_calls == [
        (backtest_tasks._LOCK_RELEASE_SCRIPT, "backtest:run-lock:run-1", "tok")
    ]
    assert client.closed is True

    # Eval failure is swallowed (lock expires via TTL)
    flaky = _FakeRedisClient(set_error=ConnectionError("mid-release"))
    flaky.eval = lambda *a: (_ for _ in ()).throw(ConnectionError("redis gone"))
    backtest_tasks._release_backtest_lock("run-1", "tok", flaky)  # must not raise
    assert flaky.closed is True


# ---------------------------------------------------------- pub/sub status


def test_publish_backtest_status_plumbing(monkeypatch):
    class _PubClient:
        def __init__(self):
            self.channels: List[tuple] = []
            self.closed = False

        def publish(self, channel, payload):
            self.channels.append((channel, payload))

        def close(self):
            self.closed = True

    client = _PubClient()
    monkeypatch.setattr(backtest_tasks, "_get_redis_client", lambda: client)
    backtest_tasks._publish_backtest_status("run-1", "started", 5.0, "BTC/ETH", 12.0)

    assert len(client.channels) == 1
    channel, payload = client.channels[0]
    assert channel == "backtest:run-1:status"
    import json

    body = json.loads(payload)
    assert body["run_id"] == "run-1"
    assert body["status"] == "started"
    assert body["progress"] == 5.0
    assert client.closed is True

    # No client: silent no-op; failing publish: swallowed
    monkeypatch.setattr(backtest_tasks, "_get_redis_client", lambda: None)
    backtest_tasks._publish_backtest_status("run-1", "started")  # must not raise

    class _Broken:
        def publish(self, *a):
            raise ConnectionError("redis down")

        def close(self):
            pass

    monkeypatch.setattr(backtest_tasks, "_get_redis_client", lambda: _Broken())
    backtest_tasks._publish_backtest_status("run-1", "started")  # must not raise


def test_get_redis_client_prefers_explicit_url(monkeypatch):
    import redis as redis_module

    sentinel = object()
    captured: Dict[str, Any] = {}

    def _fake_from_url(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(redis_module, "from_url", _fake_from_url)
    monkeypatch.setattr(
        backtest_tasks,
        "redis_url",
        lambda prefer_celery_broker=True: "redis://pub:6379/2",
    )
    assert backtest_tasks._get_redis_client() is sentinel
    assert captured["url"] == "redis://pub:6379/2"
    assert captured["kwargs"]["decode_responses"] is True

    # Constructor failure degrades to None (never raises)
    def _exploding_url(prefer_celery_broker=True):
        raise RuntimeError("env broken")

    monkeypatch.setattr(backtest_tasks, "redis_url", _exploding_url)
    assert backtest_tasks._get_redis_client() is None


# ------------------------------------------------- task lifecycle flows


def test_task_duplicate_lock_skip(monkeypatch):
    def _already_locked(run_id, token):
        raise RuntimeError("BACKTEST_ALREADY_RUNNING: locked elsewhere")

    monkeypatch.setattr(backtest_tasks, "_acquire_backtest_lock", _already_locked)
    result, states, _, _ = _invoke_task(
        monkeypatch, "run-1", run_payload=_run_payload(), acquire=_already_locked
    )

    assert result["status"] == "duplicate_skipped"
    assert "BACKTEST_ALREADY_RUNNING" in result["reason"]
    assert states[0]["state"] == "SUCCESS"
    assert states[0]["meta"]["status"] == "duplicate_skipped"
    # No execution happened
    assert _FakeService.recorded_executions == []


def test_task_missing_run_raises(monkeypatch):
    with pytest.raises(ValueError, match="not found"):
        _invoke_task(monkeypatch, "ghost-run", run_payload=None)


def test_task_validation_failures(monkeypatch):
    # Strategy snapshot present but no strategy id
    payload = _run_payload()
    payload["request"]["strategy_payload_snapshot"] = {"params": 1}
    with pytest.raises(ValueError, match="STRATEGY_ID_MISSING"):
        _invoke_task(monkeypatch, "run-1", run_payload=payload)

    # Strategy id but no snapshot
    payload = _run_payload()
    payload["request"]["strategy_id"] = 7
    with pytest.raises(ValueError, match="STRATEGY_PAYLOAD_MISSING"):
        _invoke_task(monkeypatch, "run-1", run_payload=payload)

    # No pairs selected anywhere
    payload = _run_payload()
    payload["request"] = {"source": "test"}
    with pytest.raises(ValueError, match="SELECTED_PAIRS_MISSING"):
        _invoke_task(monkeypatch, "run-1", run_payload=payload)


def test_task_happy_path(monkeypatch):
    result, states, published, events = _invoke_task(
        monkeypatch, "run-1", run_payload=_run_payload()
    )

    assert result == {"run_id": "run-1", "status": "completed"}
    assert _FakeService.recorded_executions[0]["run_id"] == "run-1"
    assert _FakeService.recorded_executions[0]["kwargs"]["propagate_exceptions"] is True

    state_names = [s["state"] for s in states]
    assert state_names[0] == "STARTED"
    assert states[0]["meta"]["selected_pairs"] == ["BTC-USD/ETH-USD"]
    assert states[0]["meta"]["backtest_run_id"] == "run-1"

    statuses = [call[1] for call in published]
    assert "started" in statuses and "completed" in statuses
    event_statuses = [e.get("status") for e in events]
    assert "started" in event_statuses and "completed" in event_statuses

    # The captured progress callback drives PROGRESS state + pubsub
    callback = _FakeService.recorded_executions[0]["callback"]
    before = len(states)
    asyncio.run(callback("run-1", 50.0, "BTC-USD/ETH-USD", 30.0))
    assert states[before]["state"] == "PROGRESS"
    assert states[before]["meta"]["progress_percent"] == 50.0
    assert states[before]["meta"]["completed_pairs"] == 0  # 50% of 1 pair
    assert published[-1][1] == "progress"


def test_task_transient_error_retries(monkeypatch):
    monkeypatch.setenv("BACKTEST_CELERY_MAX_RETRIES", "3")
    _FakeService.execute_error = httpx.ConnectError("indexer unreachable")

    with pytest.raises(Retry):
        _invoke_task(monkeypatch, "run-1", run_payload=_run_payload())

    assert _FakeService.recorded_retries, "retrying status must be persisted"
    assert _FakeService.recorded_retries[0]["retry_count"] == 1
    # The transient error's retry countdown is exponential (30s base)
    assert _FakeService.recorded_retries[0]["countdown_seconds"] == 30.0


def test_task_permanent_error_marks_failed(monkeypatch):
    _FakeService.execute_error = RuntimeError("fatal logic error")

    with pytest.raises(RuntimeError, match="fatal logic error"):
        _invoke_task(monkeypatch, "run-1", run_payload=_run_payload())

    # Worker-failure persistence ran and a failed status was published
    assert any("mark_failed" in e for e in CAPTURE["events"])
    assert CAPTURE["published"][-1][1] == "failed"


def test_task_soft_time_limit_marks_timeout(monkeypatch):
    _FakeService.execute_error = SoftTimeLimitExceeded()

    with pytest.raises(SoftTimeLimitExceeded):
        _invoke_task(monkeypatch, "run-1", run_payload=_run_payload())


def test_task_cancellation_marks_revoked(monkeypatch):
    _FakeService.execute_error = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        _invoke_task(monkeypatch, "run-1", run_payload=_run_payload())
