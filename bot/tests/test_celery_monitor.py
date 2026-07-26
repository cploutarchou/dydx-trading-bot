import asyncio

import src.infrastructure.use_cases.service_backtest as service_backtest_module
from src.infrastructure.workers.backtest_tasks import (
    _is_transient_backtest_error,
    _mark_worker_failure,
    _merge_task_context_overrides,
)
from src.infrastructure.workers.celery_monitor import (
    _task_from_backtest,
    build_progress_meta,
    celery_state_from_backtest,
    list_celery_tasks,
    list_celery_workers,
    normalized_task_status,
    redact_payload,
    retry_celery_task,
)


def test_flower_script_uses_discovered_celery_app_path():
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "celery-flower.sh"
    content = script.read_text(encoding="utf-8")

    assert "src.infrastructure.workers.celery_app:celery_app" in content
    assert "FLOWER_BASIC_AUTH is required" in content
    assert '--basic_auth="${FLOWER_BASIC_AUTH}"' in content


def test_makefile_local_worker_and_flower_use_workers_celery_app():
    from pathlib import Path

    makefile = Path(__file__).resolve().parents[1] / "Makefile"
    content = makefile.read_text(encoding="utf-8")

    assert "local-worker: ensure-venv" in content
    assert "src.infrastructure.workers.celery_app:celery_app worker -l info" in content
    assert "-Q $${CELERY_QUEUES:-backtests,default,high_priority,scheduled}" in content
    assert (
            "src.infrastructure.workers.celery_app:celery_app flower --address=0.0.0.0 --port=5555"
            in content
    )
    assert "redis://localhost:6379/1" in content
    assert "redis://localhost:6379/2" in content
    assert (
            "CELERY_QUEUES=$${CELERY_QUEUES:-backtests,default,high_priority,scheduled}"
            in content
    )


def test_workers_celery_app_loads_repo_env_before_resolving_broker_settings():
    from pathlib import Path

    celery_app_module = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "infrastructure"
            / "workers"
            / "celery_app.py"
    )
    content = celery_app_module.read_text(encoding="utf-8")

    assert "from src.shared import env_loader" in content
    assert "env_loader.load_repo_env(__file__)" in content


def test_celery_app_routes_backtests_to_dedicated_queue():
    from src.infrastructure.workers.celery_app import celery_app

    routes = celery_app.conf.task_routes

    assert routes["backtests.run"]["queue"] == "backtests"
    assert routes["bot.sync_market_candles"]["queue"] == "scheduled"
    assert celery_app.conf.task_default_queue == "default"
    assert {"backtests", "default", "high_priority", "scheduled"}.issubset(
        {queue.name for queue in celery_app.conf.task_queues}
    )


def test_celery_beat_schedule_is_market_sync_opt_in(monkeypatch):
    from src.infrastructure.workers import celery_app as celery_app_module

    monkeypatch.setenv("MARKET_SYNC_ENABLED", "false")
    assert celery_app_module._beat_schedule() == {}

    monkeypatch.setenv("MARKET_SYNC_ENABLED", "true")
    schedule = celery_app_module._beat_schedule()
    assert schedule["sync-market-candles"]["task"] == "bot.sync_market_candles"
    assert schedule["sync-market-candles"]["options"]["queue"] == "scheduled"


def test_redact_payload_hides_sensitive_task_fields():
    payload = {
        "strategy_id": 7,
        "api_key": "secret-key",
        "nested": {"broker_url": "redis://:password@localhost:6379/0", "safe": "ok"},
        "pairs": ["BTC-USD", "ETH-USD"],
    }

    redacted = redact_payload(payload)

    assert redacted["strategy_id"] == 7
    assert redacted["api_key"] == "redacted"
    assert redacted["nested"]["broker_url"] == "redacted"
    assert redacted["nested"]["safe"] == "ok"
    assert redacted["pairs"] == ["BTC-USD", "ETH-USD"]


def test_build_progress_meta_includes_debug_context():
    meta = build_progress_meta(
        run_id="run-1",
        progress_percent=42.123,
        current_pair="BTC-USD/ETH-USD",
        current_step="processing pair",
        total_pairs=10,
        completed_pairs=4,
        current_phase="simulation",
        eta_seconds=120,
        strategy_id=3,
        bot_id="bot-1",
        environment="testnet",
        selected_pairs=["BTC-USD", "ETH-USD"],
    )

    assert meta["task_id"] == "run-1"
    assert meta["task_name"] == "backtests.run"
    assert meta["status"] == "PROGRESS"
    assert meta["progress_percent"] == 42.12
    assert meta["current_pair"] == "BTC-USD/ETH-USD"
    assert meta["total_pairs"] == 10
    assert meta["completed_pairs"] == 4
    assert meta["strategy_id"] == 3
    assert meta["bot_id"] == "bot-1"
    assert meta["environment"] == "testnet"
    assert meta["selected_pairs"] == ["BTC-USD", "ETH-USD"]
    assert meta["last_heartbeat_at"]


def test_task_context_overrides_replace_existing_worker_hostname():
    request_payload = {
        "name": "test",
        "pairs": ["BTC-USD", "ETH-USD"],
        "_task_context": {"worker_hostname": "queued-worker", "retry_count": 0},
    }

    context = service_backtest_module.BacktestService._build_task_context(
        request_payload,
        **_merge_task_context_overrides(
            {"worker_hostname": "queued-worker", "retry_count": 0},
            worker_hostname="active-worker",
            retry_count=2,
        ),
    )

    assert context["worker_hostname"] == "active-worker"
    assert context["retry_count"] == 2


def test_mark_worker_failure_reuses_existing_task_context_without_duplicate_kwargs(
        monkeypatch,
):
    from src.infrastructure.workers import backtest_tasks

    class _FakeSession:
        def close(self):
            return None

    saved: dict[str, object] = {}
    stored_run = {
        "run_id": "run-ctx-1",
        "request": {
            "name": "test",
            "pairs": ["BTC-USD", "ETH-USD"],
            "_task_context": {
                "strategy_id": 11,
                "worker_hostname": "queued-worker",
                "retry_count": 0,
            },
        },
    }

    class _FakeRepository:
        def __init__(self, session):
            self.session = session

        def get_run(self, run_id):
            assert run_id == "run-ctx-1"
            return {
                "run_id": stored_run["run_id"],
                "request": {**stored_run["request"]},
            }

        def get_run_overview(self, run_id):
            return self.get_run(run_id)

        def save_run(self, data):
            saved.update(data)
            return data

        def update_run_progress(self, data):
            saved.update(data)
            return data

    monkeypatch.setattr(backtest_tasks.db, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(backtest_tasks, "BacktestRepository", _FakeRepository)

    _mark_worker_failure(
        "run-ctx-1",
        "worker crashed",
        worker_hostname="active-worker",
        retry_count=2,
    )

    request_payload = saved["request"]
    assert isinstance(request_payload, dict)
    task_context = request_payload["_task_context"]
    assert task_context["worker_hostname"] == "active-worker"
    assert task_context["retry_count"] == 2
    assert saved["status"] == "failed"
    assert saved["error_message"] == "worker crashed"


def test_backtest_task_retry_classifier_only_retries_transient_errors():
    assert _is_transient_backtest_error(RuntimeError("temporarily unavailable"))
    assert _is_transient_backtest_error(RuntimeError("connection reset by peer"))
    assert not _is_transient_backtest_error(ValueError("SELECTED_PAIRS_MISSING"))
    assert not _is_transient_backtest_error(TimeoutError("Backtest timed out"))


def test_celery_state_from_backtest_maps_app_statuses():
    assert celery_state_from_backtest("completed") == "SUCCESS"
    assert celery_state_from_backtest("failed") == "FAILURE"
    assert celery_state_from_backtest("cancelled") == "REVOKED"
    assert celery_state_from_backtest("running") == "STARTED"
    assert celery_state_from_backtest("queued") == "PENDING"


def test_normalized_task_status_maps_celery_states():
    assert normalized_task_status("PENDING") == "pending"
    assert normalized_task_status("STARTED") == "running"
    assert normalized_task_status("SUCCESS") == "success"
    assert normalized_task_status("FAILURE") == "failed"
    assert normalized_task_status("RETRY") == "retrying"
    assert normalized_task_status("REVOKED") == "cancelled"


def test_task_from_backtest_uses_persisted_request_context_when_summary_fields_are_missing():
    task = _task_from_backtest(
        {
            "run_id": "run-ctx-1",
            "worker_task_id": "run-ctx-1",
            "status": "running",
            "progress_pct": 37.5,
            "current_task": "processing pair",
            "current_pair": "BTC-USD/ETH-USD",
            "request": {
                "strategy_id": 11,
                "pairs": ["BTC-USD", "ETH-USD", "SOL-USD"],
                "selected_pairs": ["BTC-USD/ETH-USD", "ETH-USD/SOL-USD"],
                "_task_context": {
                    "strategy_id": 11,
                    "selected_pairs": ["BTC-USD/ETH-USD", "ETH-USD/SOL-USD"],
                    "bot_id": "bot-7",
                    "environment": "development",
                    "source": "ui",
                    "strategy_name": "Desk Strategy",
                    "payload_hash": "abc123",
                    "metadata": {
                        "strategy_name": "Desk Strategy",
                        "pair_count": 2,
                        "payload_hash": "abc123",
                        "source": "ui",
                    },
                    "worker_hostname": "worker-a",
                    "retry_count": 1,
                },
            },
        }
    )

    assert task["strategy_id"] == 11
    assert task["selected_pairs"] == ["BTC-USD/ETH-USD", "ETH-USD/SOL-USD"]
    assert task["bot_id"] == "bot-7"
    assert task["environment"] == "development"
    assert task["worker_hostname"] == "worker-a"
    assert task["retry_count"] == 1
    assert task["queue"] == "backtests"
    assert task["normalized_status"] == "running"
    assert task["metadata"]["strategy_name"] == "Desk Strategy"
    assert task["metadata"]["payload_hash"] == "abc123"


def test_list_celery_workers_uses_short_lived_cache(monkeypatch):
    from src.infrastructure.workers import celery_monitor

    celery_monitor._clear_monitor_cache()
    monkeypatch.setenv("CELERY_MONITOR_CACHE_TTL_SECONDS", "60")

    class _Inspector:
        def stats(self):
            calls.append("stats")
            return {"worker-a": {"pool": {"writes": {"celery": 1}}}}

        def active(self):
            calls.append("active")
            return {"worker-a": []}

        def registered(self):
            calls.append("registered")
            return {"worker-a": ["backtests.run"]}

    calls = []
    monkeypatch.setattr(celery_monitor, "_inspect", lambda: _Inspector())

    first = list_celery_workers()
    second = list_celery_workers()

    assert first["total"] == 1
    assert second["total"] == 1
    assert sorted(calls) == ["active", "registered", "stats"]


def test_list_celery_tasks_skips_async_result_for_terminal_runs(monkeypatch):
    from src.infrastructure.workers import celery_monitor

    celery_monitor._clear_monitor_cache()
    monkeypatch.delenv("CELERY_TASK_RESULT_ENRICH_TERMINAL", raising=False)
    monkeypatch.setenv("CELERY_MONITOR_CACHE_TTL_SECONDS", "0")

    runs = [
        {
            "run_id": "run-completed",
            "worker_task_id": "run-completed",
            "status": "completed",
        },
        {"run_id": "run-failed", "worker_task_id": "run-failed", "status": "failed"},
        {"run_id": "run-running", "worker_task_id": "run-running", "status": "running"},
    ]
    monkeypatch.setattr(celery_monitor, "_load_backtest_runs", lambda: runs)

    class _Inspector:
        def active(self):
            return {}

        def reserved(self):
            return {}

        def scheduled(self):
            return {}

    monkeypatch.setattr(celery_monitor, "_inspect", lambda: _Inspector())

    probed_task_ids = []

    class _FakeResult:
        def __init__(self, task_id, app=None):
            _ = app
            probed_task_ids.append(task_id)
            self.state = "PENDING"
            self.info = {}
            self.traceback = None
            self.result = None

    monkeypatch.setattr(celery_monitor, "AsyncResult", _FakeResult)

    payload = list_celery_tasks(limit=100)

    assert payload["total"] == 3
    assert probed_task_ids == ["run-running"]


def test_retry_celery_task_awaits_restart_without_nested_event_loop(monkeypatch):
    from src.infrastructure.workers import celery_monitor

    class _FakeSession:
        def close(self):
            return None

    class _FakeRepository:
        def __init__(self, session):
            self.session = session

        def get_run(self, run_id):
            return {"run_id": run_id, "request": {}}

    class _FakeService:
        def __init__(self, repository):
            self.repository = repository

        async def restart_backtest(self, run_id):
            return {"new_run_id": f"restarted-{run_id}"}

    monkeypatch.setattr(
        celery_monitor,
        "get_celery_task",
        lambda task_id: {
            "task_id": task_id,
            "task_name": "backtests.run",
            "backtest_run_id": "run-123",
            "status": "FAILURE",
        },
    )
    monkeypatch.setattr(celery_monitor.db, "get_session", lambda: _FakeSession())
    monkeypatch.setattr(celery_monitor, "BacktestRepository", _FakeRepository)
    monkeypatch.setattr(service_backtest_module, "BacktestService", _FakeService)

    result = asyncio.run(retry_celery_task("run-123"))

    assert result["task_id"] == "run-123"
    assert result["retried"] is True
    assert result["new_backtest_run_id"] == "restarted-run-123"
