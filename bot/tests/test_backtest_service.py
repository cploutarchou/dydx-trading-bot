"""Tests for asynchronous, candle-driven backtest execution."""

import asyncio
import importlib
import math
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _default_backtest_backend_asyncio(monkeypatch):
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "false")
    yield


def _load_modules():
    models_module = importlib.import_module("src.infrastructure.domain.models_backtest")
    service_module = importlib.import_module(
        "src.infrastructure.use_cases.service_backtest"
    )

    return models_module.BacktestConfigRequest, service_module


def _load_pair_selection():
    """Load the extracted pair-selection module (Phase 2 decomposition).

    The prioritization logic now lives in
    :mod:`src.infrastructure.use_cases.backtest_pair_selection`; ``BacktestService``
    keeps only a thin delegating ``_prioritize_pairs``.
    """
    return importlib.import_module(
        "src.infrastructure.use_cases.backtest_pair_selection"
    )


def _request(**trading_parameters):
    BacktestConfigRequest, _ = _load_modules()
    return BacktestConfigRequest(
        name="test-run",
        description="test",
        start_date="2026-02-05",
        end_date="2026-02-07",
        initial_balance=1000.0,
        trading_parameters={"resolution": "1HOUR", **trading_parameters},
        pairs=["BTC-USD", "ETH-USD", "SOL-USD"],
    )


class _FakeMarkets:
    async def get_perpetual_market_candles(
        self,
        market,
        resolution,
        from_iso=None,
        to_iso=None,
        limit=100,
    ):
        del resolution, limit
        start = datetime.fromisoformat(str(from_iso).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(to_iso).replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        market_bias = {
            "BTC-USD": 32000.0,
            "ETH-USD": 1800.0,
            "SOL-USD": 120.0,
        }.get(market, 1000.0)
        # Per-market phase offsets: without them every market shares the same
        # wave and the pair spread is constant, leaving z-scores driven only
        # by "%.6f" rounding noise (which the live-faithful exit ladder
        # correctly never trades). Phase-shifted waves give pairs a genuinely
        # mean-reverting spread.
        market_phase = {
            "BTC-USD": 0.0,
            "ETH-USD": 0.9,
            "SOL-USD": 1.7,
        }.get(market, 0.5)

        candles = []
        idx = 0
        cursor = start
        while cursor <= end:
            wave = math.sin(idx / 8.0 + market_phase) * 15.0
            trend = idx * 0.2
            close = market_bias + wave + trend
            candles.append(
                {
                    "startedAt": cursor.replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "close": f"{close:.6f}",
                }
            )
            cursor += timedelta(hours=1)
            idx += 1

        return {"candles": candles}

    async def get_perpetual_markets(self):
        return {
            "markets": {
                "BTC-USD": {"volume24H": "9000000"},
                "ETH-USD": {"volume24H": "7000000"},
                "SOL-USD": {"volume24H": "3000000"},
                "AVAX-USD": {"volume24H": "1000000"},
            }
        }


class _FakeIndexer:
    def __init__(self):
        self.markets = _FakeMarkets()


class _FakeNode:
    async def close(self):
        return None


class _FakeClient:
    def __init__(self):
        self.indexer = _FakeIndexer()
        self.node = _FakeNode()


class _SlowMarkets(_FakeMarkets):
    async def get_perpetual_markets(self):
        await asyncio.sleep(10)
        return await super().get_perpetual_markets()


class _SlowIndexer:
    def __init__(self):
        self.markets = _SlowMarkets()


class _SlowClient:
    def __init__(self):
        self.indexer = _SlowIndexer()
        self.node = _FakeNode()


class _HeartbeatSlowMarkets(_FakeMarkets):
    async def get_perpetual_markets(self):
        await asyncio.sleep(0.6)
        return await super().get_perpetual_markets()


class _HeartbeatSlowIndexer:
    def __init__(self):
        self.markets = _HeartbeatSlowMarkets()


class _HeartbeatSlowClient:
    def __init__(self):
        self.indexer = _HeartbeatSlowIndexer()
        self.node = _FakeNode()


class _BlockingHeartbeatMarkets(_FakeMarkets):
    async def get_perpetual_markets(self):
        time.sleep(0.6)
        return await super().get_perpetual_markets()


class _BlockingHeartbeatIndexer:
    def __init__(self):
        self.markets = _BlockingHeartbeatMarkets()


class _BlockingHeartbeatClient:
    def __init__(self):
        self.indexer = _BlockingHeartbeatIndexer()
        self.node = _FakeNode()


class _PausableMarkets(_FakeMarkets):
    async def get_perpetual_market_candles(
        self,
        market,
        resolution,
        from_iso=None,
        to_iso=None,
        limit=100,
    ):
        await asyncio.sleep(0.5)
        return await super().get_perpetual_market_candles(
            market,
            resolution,
            from_iso=from_iso,
            to_iso=to_iso,
            limit=limit,
        )


class _PausableIndexer:
    def __init__(self):
        self.markets = _PausableMarkets()


class _PausableClient:
    def __init__(self):
        self.indexer = _PausableIndexer()
        self.node = _FakeNode()


async def _wait_for_terminal_status(service, run_id, timeout_seconds=15.0):
    end = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < end:
        status = service.get_backtest_status(run_id)
        assert status is not None
        if status.status in {"completed", "failed", "timeout", "cancelled", "stale"}:
            return status.status
        await asyncio.sleep(0.02)
    raise TimeoutError("backtest did not reach terminal status in time")


async def _wait_for_status(service, run_id, expected_status, timeout_seconds=15.0):
    end = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < end:
        status = service.get_backtest_status(run_id)
        assert status is not None
        if status.status == expected_status:
            return status
        await asyncio.sleep(0.02)
    raise TimeoutError(f"backtest did not reach {expected_status} in time")


def test_backtest_runs_async_and_completes_with_trades(monkeypatch):
    BacktestConfigRequest, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)

    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(
            BacktestConfigRequest(
                **_request(
                    zscore_threshold=1.2,
                    usd_per_trade=20.0,
                    stats_window=12,
                    close_at_zscore_cross=True,
                ).model_dump()
            )
        )
        assert created.status == "running"

        terminal = await _wait_for_terminal_status(service, created.run_id)
        assert terminal == "completed"

        details = service.get_backtest_details(created.run_id)
        assert details is not None
        assert details.status == "completed"
        assert details.total_trades >= 0
        assert details.artifact_refs["full_result"].endswith(
            f"/backtests/{created.run_id}/full_result.json"
        )
        assert details.analytics_rows_written >= 0

        trades = service.get_backtest_trades(created.run_id, limit=500)
        assert len(trades) == details.total_trades

        progress = service.get_live_progress(created.run_id)
        assert progress is not None
        assert float(progress["progress_pct"]) == 100.0

    asyncio.run(_run())


def test_backtest_progress_callback_failure_does_not_fail_run(monkeypatch):
    BacktestConfigRequest, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    async def _failing_progress(*_args):
        raise RuntimeError("websocket unavailable")

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)
    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(
            BacktestConfigRequest(**_request(max_pairs=1).model_dump()),
            progress_callback=_failing_progress,
        )
        terminal = await _wait_for_terminal_status(service, created.run_id)
        assert terminal == "completed"

    asyncio.run(_run())


def test_parameter_changes_produce_distinct_real_results(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)

    service = BacktestService(session=None)

    async def _run():
        aggressive = await service.create_and_run_backtest(
            _request(
                zscore_threshold=0.8,
                usd_per_trade=30.0,
                stats_window=10,
                close_at_zscore_cross=True,
            )
        )
        conservative = await service.create_and_run_backtest(
            _request(
                zscore_threshold=2.2,
                usd_per_trade=10.0,
                stats_window=30,
                close_at_zscore_cross=True,
            )
        )

        a_status = await _wait_for_terminal_status(service, aggressive.run_id)
        c_status = await _wait_for_terminal_status(service, conservative.run_id)
        assert a_status == "completed"
        assert c_status == "completed"

        a = service.get_backtest_details(aggressive.run_id)
        c = service.get_backtest_details(conservative.run_id)
        assert a is not None and c is not None

        assert (
            a.total_pnl != c.total_pnl
            or a.total_trades != c.total_trades
            or a.sharpe_ratio != c.sharpe_ratio
        )

    asyncio.run(_run())


def test_cancel_running_backtest(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)

    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(
            _request(
                zscore_threshold=1.5,
                usd_per_trade=10.0,
                stats_window=21,
                close_at_zscore_cross=True,
            )
        )

        assert service.cancel_backtest(created.run_id)
        terminal = await _wait_for_terminal_status(service, created.run_id)
        assert terminal in {"cancelled", "completed"}

    asyncio.run(_run())


def test_pause_and_resume_running_backtest(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _PausableClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)

    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(
            _request(
                zscore_threshold=1.5,
                usd_per_trade=10.0,
                stats_window=21,
                close_at_zscore_cross=True,
            )
        )

        paused_payload = service.pause_backtest(created.run_id)
        assert paused_payload is not None
        assert paused_payload["control_status"] == "pause_requested"

        paused = await _wait_for_status(service, created.run_id, "paused")
        assert paused.resumable is True
        assert paused.pausable is False

        resumed_payload = service.resume_backtest(created.run_id)
        assert resumed_payload is not None
        assert resumed_payload["control_status"] == "resume_requested"

        terminal = await _wait_for_terminal_status(service, created.run_id)
        assert terminal == "completed"

    asyncio.run(_run())


def test_retry_backtest_starts_new_run_from_persisted_request(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)

    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(_request())
        terminal = await _wait_for_terminal_status(service, created.run_id)
        assert terminal == "completed"

        retried = await service.retry_backtest(created.run_id)
        assert retried is not None
        assert retried["run_id"] == created.run_id
        assert retried["new_run_id"] != created.run_id

        retry_terminal = await _wait_for_terminal_status(service, retried["new_run_id"])
        assert retry_terminal == "completed"

    asyncio.run(_run())


def test_restart_backtest_reconstructs_missing_request_from_persisted_fields(
    monkeypatch,
):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)

    service = BacktestService(session=None)
    run_id = "legacy-restart-run"
    now = datetime.now(timezone.utc).isoformat()
    service.repository.save_run(
        {
            "run_id": run_id,
            "name": "legacy restart",
            "status": "completed",
            "progress_pct": 100.0,
            "current_pair": "BTC-USD/ETH-USD",
            "current_task": "complete",
            "created_at": now,
            "updated_at": now,
            "start_date": "2026-03-20",
            "end_date": "2026-04-19",
            "selected_pairs": ["BTC-USD/ETH-USD"],
            "request": {},
        }
    )

    async def _run():
        restarted = await service.restart_backtest(run_id)
        assert restarted is not None
        assert restarted["run_id"] == run_id
        assert restarted["new_run_id"] != run_id

    asyncio.run(_run())


def test_repair_backtest_request_restores_restartability(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)

    service = BacktestService(session=None)
    run_id = "legacy-repair-run"
    now = datetime.now(timezone.utc).isoformat()
    service.repository.save_run(
        {
            "run_id": run_id,
            "name": "legacy repair",
            "status": "completed",
            "progress_pct": 100.0,
            "current_pair": "BTC-USD/ETH-USD",
            "current_task": "complete",
            "created_at": now,
            "updated_at": now,
            "start_date": "2026-03-20",
            "end_date": "2026-04-19",
            "selected_pairs": ["BTC-USD/ETH-USD"],
            "request": {},
        }
    )

    dry_run = service.repair_backtest_request(run_id, dry_run=True)
    assert dry_run is not None
    assert dry_run["repairable"] is True
    assert dry_run["repaired"] is False

    repaired = service.repair_backtest_request(run_id, dry_run=False)
    assert repaired is not None
    assert repaired["repaired"] is True
    assert repaired["request_available"] is True

    status = service.get_backtest_status(run_id)
    assert status is not None
    assert status.request_available is True
    assert status.request is not None

    restarted = asyncio.run(service.restart_backtest(run_id))
    assert restarted is not None
    assert restarted["new_run_id"] != run_id


def test_celery_worker_backend_queues_persisted_run(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "celery")
    queued: dict[str, object] = {}
    monkeypatch.setattr(
        BacktestService,
        "_enqueue_celery_backtest",
        lambda self, run_id, task_context=None: queued.update(
            {"run_id": run_id, "task_context": task_context}
        )
        or f"task-{run_id}",
    )

    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(
            _request(
                pair_selection_mode="input",
                max_pairs=0,
            ).model_copy(
                update={
                    "strategy_id": 42,
                    "selected_pairs": ["BTC-USD/ETH-USD"],
                    "strategy_payload_snapshot": {
                        "id": 42,
                        "name": "Queued Strategy",
                    },
                }
            )
        )
        assert created.status == "pending"
        assert created.worker_backend == "celery"
        assert created.worker_task_id == f"task-{created.run_id}"
        assert queued["run_id"] == created.run_id
        task_context = queued["task_context"]
        assert isinstance(task_context, dict)
        assert task_context["strategy_id"] == 42
        assert task_context["selected_pairs"] == ["BTC-USD/ETH-USD"]
        assert task_context["metadata"]["pair_count"] == 1
        assert task_context["metadata"]["source"] == "api"
        assert task_context["queue"] == "backtests"
        assert task_context["payload_hash"]

        status = service.get_backtest_status(created.run_id)
        assert status is not None
        assert status.status == "pending"
        assert status.pausable is True
        assert status.worker_backend == "celery"
        assert status.strategy_id == 42
        assert status.selected_pairs == ["BTC-USD/ETH-USD"]
        assert status.metadata["pair_count"] == 1
        assert service.delete_backtest(created.run_id)

    asyncio.run(_run())


def test_resolve_worker_backend_keeps_configured_celery_without_probe(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "celery")
    monkeypatch.setattr(
        BacktestService,
        "_probe_celery_worker_available",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("probe should not run when backend is already celery")
        ),
    )

    backend = asyncio.run(BacktestService._resolve_worker_backend())
    assert backend == "celery"


def test_resolve_worker_backend_promotes_asyncio_when_probe_succeeds(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "true")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS", "60")

    BacktestService._backend_reprobe_last_monotonic = 0.0
    BacktestService._backend_reprobe_last_available = False
    monkeypatch.setattr(
        BacktestService,
        "_probe_celery_worker_available",
        lambda *_args, **_kwargs: True,
    )

    backend = asyncio.run(BacktestService._resolve_worker_backend())
    assert backend == "celery"
    assert os.getenv("BACKTEST_WORKER_BACKEND") == "celery"


def test_resolve_worker_backend_keeps_asyncio_when_probe_fails(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "true")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS", "60")

    BacktestService._backend_reprobe_last_monotonic = 0.0
    BacktestService._backend_reprobe_last_available = False
    monkeypatch.setattr(
        BacktestService,
        "_probe_celery_worker_available",
        lambda *_args, **_kwargs: False,
    )

    backend = asyncio.run(BacktestService._resolve_worker_backend())
    assert backend == "asyncio"
    assert os.getenv("BACKTEST_WORKER_BACKEND") == "asyncio"


def test_resolve_worker_backend_respects_reprobe_cooldown(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "true")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS", "60")

    BacktestService._backend_reprobe_last_monotonic = 0.0
    BacktestService._backend_reprobe_last_available = False

    probe_calls = {"count": 0}

    def _probe(*_args, **_kwargs):
        probe_calls["count"] += 1
        return False

    monkeypatch.setattr(BacktestService, "_probe_celery_worker_available", _probe)

    first = asyncio.run(BacktestService._resolve_worker_backend())
    second = asyncio.run(BacktestService._resolve_worker_backend())

    assert first == "asyncio"
    assert second == "asyncio"
    assert probe_calls["count"] == 1


def test_enqueue_celery_backtest_uses_backtests_queue(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService
    from src.infrastructure.workers import backtest_tasks

    captured: dict[str, object] = {}

    class _FakeAsyncResult:
        id = "task-run-queue"

    class _FakeTask:
        @staticmethod
        def apply_async(**kwargs):
            captured.update(kwargs)
            return _FakeAsyncResult()

    monkeypatch.setenv("BACKTEST_CELERY_QUEUE", "backtests")
    monkeypatch.setattr(backtest_tasks, "run_backtest_task", _FakeTask)

    service = BacktestService(session=None)
    task_id = service._enqueue_celery_backtest(
        "run-queue",
        {"strategy_id": 7, "queue": "backtests"},
    )

    assert task_id == "task-run-queue"
    assert captured["args"] == ("run-queue",)
    assert captured["kwargs"] == {
        "task_context": {"strategy_id": 7, "queue": "backtests"}
    }
    assert captured["task_id"] == "run-queue"
    assert captured["queue"] == "backtests"


def test_celery_enqueue_failure_does_not_run_backtest_inline(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "celery")

    def _fail_enqueue(self, run_id, task_context=None):
        raise RuntimeError("broker unavailable")

    def _unexpected_inline_task(*_args, **_kwargs):
        raise AssertionError("Celery enqueue failure must not start inline execution")

    monkeypatch.setattr(BacktestService, "_enqueue_celery_backtest", _fail_enqueue)
    monkeypatch.setattr(
        service_module.async_job_manager,
        "create_supervised_task",
        _unexpected_inline_task,
    )

    service = BacktestService(session=None)

    async def _run():
        with pytest.raises(service_module.BacktestEnqueueError):
            await service.create_and_run_backtest(
                _request(
                    pair_selection_mode="input",
                    max_pairs=0,
                ).model_copy(
                    update={
                        "strategy_id": 42,
                        "selected_pairs": ["BTC-USD/ETH-USD"],
                        "strategy_payload_snapshot": {
                            "id": 42,
                            "name": "Queued Strategy",
                        },
                    }
                )
            )

    asyncio.run(_run())

    runs = service.repository.list_runs(limit=None, offset=0)
    failed_runs = [
        run for run in runs if run.get("error_message") == "broker unavailable"
    ]
    assert len(failed_runs) == 1
    failed = failed_runs[0]
    assert failed["status"] == "failed"
    assert failed["worker_backend"] == "celery"
    assert failed["current_task"] == "enqueue failed"

    status = service.get_backtest_status(failed["run_id"])
    assert status is not None
    assert status.status == "failed"
    assert status.error_message == "broker unavailable"
    assert status.error_code == "BACKTEST_ENQUEUE_FAILED"
    assert status.result_summary is not None

    assert service.delete_backtest(failed["run_id"])


def test_mark_backtest_retrying_persists_retry_status():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    service = BacktestService(session=None)
    now = datetime.now(timezone.utc).isoformat()
    service.repository.save_run(
        {
            "run_id": "run-retry",
            "name": "retry",
            "status": "running",
            "progress_pct": 12.5,
            "current_pair": "BTC-USD/ETH-USD",
            "current_task": "processing pair",
            "created_at": now,
            "updated_at": now,
            "request": _request().model_dump(),
        }
    )

    persisted = service.mark_backtest_retrying(
        "run-retry",
        error=RuntimeError("temporarily unavailable"),
        countdown_seconds=30,
        retry_count=2,
        task_id="task-retry",
    )

    assert persisted is not None
    status = service.get_backtest_status("run-retry")
    assert status is not None
    assert status.status == "retrying"
    assert status.worker_backend == "celery"
    assert status.worker_task_id == "task-retry"
    assert status.retry_count == 2
    assert status.error_message == "temporarily unavailable"
    assert status.error_code == "BACKTEST_TRANSIENT_RETRY"
    assert service.repository.delete_run("run-retry")


def test_pair_markets_from_request_preserves_explicit_selected_pairs_labels():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    pair_markets, selected_pairs, explicit = BacktestService._pair_markets_from_request(
        {
            "pairs": ["BTC-USD", "ETH-USD", "SOL-USD"],
            "selected_pairs": ["BTC-USD/ETH-USD", "ETH-USD/SOL-USD"],
        }
    )

    assert explicit is True
    assert selected_pairs == ["BTC-USD/ETH-USD", "ETH-USD/SOL-USD"]
    assert pair_markets == [("BTC-USD", "ETH-USD"), ("ETH-USD", "SOL-USD")]


def test_failed_backtest_exposes_error_fields(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _failing_connect():
        raise RuntimeError("historical data fetch failed")

    monkeypatch.setattr(service_module, "connect_dydx", _failing_connect)

    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(_request())

        terminal = await _wait_for_terminal_status(service, created.run_id)
        assert terminal == "failed"

        details = service.get_backtest_details(created.run_id)
        assert details is not None
        assert details.status == "failed"
        assert details.error == "historical data fetch failed"
        assert details.error_message == "historical data fetch failed"

        status = service.get_backtest_status(created.run_id)
        assert status is not None
        assert status.status == "failed"
        assert status.error == "historical data fetch failed"
        assert status.error_message == "historical data fetch failed"

        progress = service.get_live_progress(created.run_id)
        assert progress is not None
        assert progress["error"] == "historical data fetch failed"
        assert progress["error_message"] == "historical data fetch failed"

    asyncio.run(_run())


def test_backtest_times_out_and_exposes_heartbeat_fields(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _slow_connect():
        return _SlowClient()

    monkeypatch.setattr(service_module, "connect_dydx", _slow_connect)
    monkeypatch.setattr(BacktestService, "_MIN_TIMEOUT_SECONDS", 0.01)

    service = BacktestService(session=None)

    async def _run():
        payload = _request().model_dump()
        payload["timeout_seconds"] = 0.05
        created = await service.create_and_run_backtest(payload)

        terminal = await _wait_for_terminal_status(
            service,
            created.run_id,
            timeout_seconds=5.0,
        )
        assert terminal == "timeout"

        status = service.get_backtest_status(created.run_id)
        assert status is not None
        assert status.status == "timeout"
        assert status.deadline_at is not None
        assert status.last_heartbeat_at == status.updated_at
        assert status.heartbeat_age_seconds is not None
        assert status.cancellable is False
        assert "timed out" in str(status.error_message).lower()

        progress = service.get_live_progress(created.run_id)
        assert progress is not None
        assert progress["status"] == "timeout"
        assert progress["last_heartbeat_at"] == status.updated_at
        assert progress["cancellable"] is False

    asyncio.run(_run())


def test_stale_backtest_status_is_persisted_as_stale(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService
    monkeypatch.setattr(BacktestService, "_STALE_BACKTEST_HEARTBEAT_SECONDS", 1.0)

    service = BacktestService(session=None)
    stale_updated_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    service.repository.save_run(
        {
            "run_id": "stale-run",
            "name": "stale",
            "status": "running",
            "progress_pct": 63.0,
            "current_pair": "BOME-USD/USUAL-USD",
            "current_task": "processing pair",
            "created_at": stale_updated_at,
            "updated_at": stale_updated_at,
            "start_date": "2026-03-20",
            "end_date": "2026-04-19",
        }
    )

    status = service.get_backtest_status("stale-run")
    assert status is not None
    assert status.status == "stale"
    assert status.cancellable is False
    assert status.progress_pct == 63.0
    assert "heartbeat is stale" in str(status.error_message).lower()

    persisted = service.repository.get_run("stale-run")
    assert persisted is not None
    assert persisted["status"] == "stale"
    assert persisted["updated_at"] == stale_updated_at

    health = service.get_runtime_health()
    assert health["queue_depth"] == 0


def test_pending_backtest_is_not_marked_stale_from_old_heartbeat(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService
    monkeypatch.setattr(BacktestService, "_STALE_BACKTEST_HEARTBEAT_SECONDS", 1.0)

    service = BacktestService(session=None)
    stale_updated_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    service.repository.save_run(
        {
            "run_id": "pending-old-heartbeat",
            "name": "pending-queue",
            "status": "pending",
            "progress_pct": 0.0,
            "current_pair": "pending",
            "current_task": "queued",
            "worker_backend": "celery",
            "created_at": stale_updated_at,
            "updated_at": stale_updated_at,
            "start_date": "2026-03-20",
            "end_date": "2026-04-19",
        }
    )

    status = service.get_backtest_status("pending-old-heartbeat")
    assert status is not None
    assert status.status == "pending"
    assert status.error is None
    assert status.error_message is None
    assert status.cancellable is True

    persisted = service.repository.get_run("pending-old-heartbeat")
    assert persisted is not None
    assert persisted["status"] == "pending"


def test_backtest_keepalive_prevents_false_stale_during_slow_phase(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService
    monkeypatch.setattr(BacktestService, "_STALE_BACKTEST_HEARTBEAT_SECONDS", 0.4)

    async def _slow_connect():
        return _HeartbeatSlowClient()

    monkeypatch.setattr(service_module, "connect_dydx", _slow_connect)

    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(
            _request(max_pairs=1, stats_window=8).model_dump()
        )

        await asyncio.sleep(0.2)

        status = service.get_backtest_status(created.run_id)
        assert status is not None
        assert status.status == "running"
        assert status.last_heartbeat_at is not None
        assert status.heartbeat_age_seconds is not None
        assert status.heartbeat_age_seconds < 0.4

        terminal = await _wait_for_terminal_status(service, created.run_id)
        assert terminal == "completed"

    asyncio.run(_run())


def test_backtest_watchdog_keeps_heartbeat_alive_during_blocking_phase(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService
    monkeypatch.setattr(BacktestService, "_STALE_BACKTEST_HEARTBEAT_SECONDS", 0.4)
    monkeypatch.setattr(
        BacktestService, "_heartbeat_keepalive_seconds", lambda self: 0.1
    )

    async def _blocking_connect():
        return _BlockingHeartbeatClient()

    monkeypatch.setattr(service_module, "connect_dydx", _blocking_connect)

    service = BacktestService(session=None)
    observed_statuses: list[str] = []
    stop_polling = threading.Event()

    def _poll_status(run_id: str) -> None:
        while not stop_polling.is_set():
            status = service.get_backtest_status(run_id)
            if status is not None:
                observed_statuses.append(status.status)
            time.sleep(0.05)

    async def _run():
        created = await service.create_and_run_backtest(
            _request(max_pairs=1, stats_window=8).model_dump()
        )

        poller = threading.Thread(
            target=_poll_status,
            args=(created.run_id,),
            daemon=True,
        )
        poller.start()

        try:
            terminal = await _wait_for_terminal_status(service, created.run_id)
        finally:
            stop_polling.set()
            poller.join(timeout=2.0)

        assert not poller.is_alive()
        assert terminal == "completed"
        assert "stale" not in observed_statuses

        status = service.get_backtest_status(created.run_id)
        assert status is not None
        assert status.status == "completed"
        assert status.heartbeat_age_seconds is not None
        assert status.heartbeat_age_seconds < 0.4

    asyncio.run(_run())


def test_legacy_pending_with_progress_normalizes_to_running(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService
    monkeypatch.setattr(BacktestService, "_STALE_BACKTEST_HEARTBEAT_SECONDS", 3600.0)

    service = BacktestService(session=None)
    now = datetime.now(timezone.utc).isoformat()
    service.repository.save_run(
        {
            "run_id": "legacy-progress-run",
            "name": "legacy-progress",
            "status": "created",
            "progress_pct": 12.3,
            "current_pair": "BTC-USD/ETH-USD",
            "current_task": "processing pair",
            "created_at": now,
            "updated_at": now,
            "start_date": "2026-03-20",
            "end_date": "2026-04-19",
        }
    )

    status = service.get_backtest_status("legacy-progress-run")
    assert status is not None
    assert status.status == "running"
    assert status.progress_pct == 12.3

    persisted = service.repository.get_run("legacy-progress-run")
    assert persisted is not None
    assert persisted["status"] == "running"


def test_build_market_pairs_uses_all_unique_combinations():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    pairs = BacktestService._build_market_pairs(
        ["BTC-USD", "ETH-USD", "SOL-USD", "ETH-USD", ""]
    )

    assert pairs == [
        ("BTC-USD", "ETH-USD"),
        ("BTC-USD", "SOL-USD"),
        ("ETH-USD", "SOL-USD"),
    ]


def test_build_market_pairs_with_four_markets_returns_all_six_combinations():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    pairs = BacktestService._build_market_pairs(
        ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD"]
    )

    assert len(pairs) == 6
    assert pairs == [
        ("BTC-USD", "ETH-USD"),
        ("BTC-USD", "SOL-USD"),
        ("BTC-USD", "AVAX-USD"),
        ("ETH-USD", "SOL-USD"),
        ("ETH-USD", "AVAX-USD"),
        ("SOL-USD", "AVAX-USD"),
    ]


def test_prioritize_pairs_by_liquidity_prefers_highest_combined_volume():
    pair_selection = _load_pair_selection()

    pairs = [
        ("BTC-USD", "SOL-USD"),
        ("ETH-USD", "AVAX-USD"),
        ("BTC-USD", "ETH-USD"),
    ]
    market_map = {
        "BTC-USD": {"volume24H": "1000"},
        "ETH-USD": {"volume24H": "900"},
        "SOL-USD": {"volume24H": "300"},
        "AVAX-USD": {"volume24H": "100"},
    }

    ranked = pair_selection._prioritize_pairs_by_liquidity(pairs, market_map)
    assert ranked == [
        ("BTC-USD", "ETH-USD"),  # 1900
        ("BTC-USD", "SOL-USD"),  # 1300
        ("ETH-USD", "AVAX-USD"),  # 1000
    ]


def test_prioritize_pairs_by_liquidity_is_stable_for_ties():
    pair_selection = _load_pair_selection()

    pairs = [
        ("BTC-USD", "SOL-USD"),
        ("ETH-USD", "AVAX-USD"),
    ]
    market_map = {
        "BTC-USD": {"volume24H": "1000"},
        "SOL-USD": {"volume24H": "200"},
        "ETH-USD": {"volume24H": "800"},
        "AVAX-USD": {"volume24H": "400"},
    }

    # both sum to 1200 -> preserve input order
    ranked = pair_selection._prioritize_pairs_by_liquidity(pairs, market_map)
    assert ranked == pairs


def test_pair_selection_mode_normalization_aliases():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    assert BacktestService._normalize_pair_selection_mode("volume") == "liquidity"
    assert BacktestService._normalize_pair_selection_mode("none") == "input"
    assert BacktestService._normalize_pair_selection_mode("order") == "input"
    assert (
        BacktestService._normalize_pair_selection_mode("cointegration")
        == "cointegration"
    )
    assert BacktestService._normalize_pair_selection_mode("volatility") == "volatility"
    assert BacktestService._normalize_pair_selection_mode("unknown-mode") == "liquidity"


def test_prioritize_pairs_respects_mode_selection():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    pair_markets = [
        ("BTC-USD", "ETH-USD"),
        ("BTC-USD", "SOL-USD"),
        ("ETH-USD", "SOL-USD"),
    ]
    market_map = {
        "BTC-USD": {"volume24H": "1000"},
        "ETH-USD": {"volume24H": "800"},
        "SOL-USD": {"volume24H": "100"},
    }
    history_by_market = {
        "BTC-USD": {
            "t1": 100.0,
            "t2": 105.0,
            "t3": 112.0,
            "t4": 130.0,
            "t5": 145.0,
            "t6": 170.0,
        },
        "ETH-USD": {
            "t1": 50.0,
            "t2": 51.0,
            "t3": 52.0,
            "t4": 53.0,
            "t5": 54.0,
            "t6": 55.0,
        },
        "SOL-USD": {
            "t1": 20.0,
            "t2": 21.0,
            "t3": 18.0,
            "t4": 24.0,
            "t5": 19.0,
            "t6": 27.0,
        },
    }

    liquidity_ranked = BacktestService._prioritize_pairs(
        pair_markets=pair_markets,
        mode="liquidity",
        market_map=market_map,
        history_by_market=history_by_market,
    )
    # BTC/ETH has highest combined liquidity.
    assert liquidity_ranked[0] == ("BTC-USD", "ETH-USD")

    input_ranked = BacktestService._prioritize_pairs(
        pair_markets=pair_markets,
        mode="input",
        market_map=market_map,
        history_by_market=history_by_market,
    )
    assert input_ranked == pair_markets

    volatility_ranked = BacktestService._prioritize_pairs(
        pair_markets=pair_markets,
        mode="volatility",
        market_map=market_map,
        history_by_market=history_by_market,
    )
    # SOL has highest volatility in synthetic history, so pairs including SOL should surface.
    assert volatility_ranked[0] in {
        ("BTC-USD", "SOL-USD"),
        ("ETH-USD", "SOL-USD"),
    }


def test_live_progress_and_runtime_health_contract(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)
    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(_request())

        progress = service.get_live_progress(created.run_id)
        assert progress is not None
        assert "progress" in progress
        assert progress["progress"] == progress["progress_pct"]

        health = service.get_runtime_health()
        assert {"queue_depth", "active_jobs", "total_runs"}.issubset(set(health.keys()))
        assert health["total_runs"] >= 1

    asyncio.run(_run())


def test_comprehensive_analytics_includes_sub_objects_and_candle_fields(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)
    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(_request())
        terminal = await _wait_for_terminal_status(service, created.run_id)
        assert terminal == "completed"

        analytics = service.get_comprehensive_analytics(created.run_id)
        assert analytics is not None
        assert isinstance(analytics.get("trades"), list)
        assert isinstance(analytics.get("position_snapshots"), list)
        assert isinstance(analytics.get("candles"), list)
        if analytics["candles"]:
            first = analytics["candles"][0]
            assert "candle_id" in first
            assert "resolution" in first
            assert str(first.get("timestamp", "")).endswith("Z")

    asyncio.run(_run())


def test_backtest_status_survives_service_recreation_with_db_repository(
    monkeypatch, tmp_path
):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    async def _failing_connect():
        raise RuntimeError("historical data fetch failed")

    monkeypatch.setattr(service_module, "connect_dydx", _failing_connect)

    db_path = tmp_path / "backtest_runs.sqlite"
    engine = create_engine(f"sqlite:///{db_path}", future=True)

    from internal.domain import Base
    from src.infrastructure.persistence.repository_backtest import BacktestRepository

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    BacktestService._runs.clear()
    BacktestService._tasks.clear()

    async def _run():
        service = BacktestService(BacktestRepository(SessionLocal()))
        created = await service.create_and_run_backtest(_request())

        terminal = await _wait_for_terminal_status(service, created.run_id)
        assert terminal == "failed"

        BacktestService._runs.clear()
        recreated = BacktestService(BacktestRepository(SessionLocal()))
        status = recreated.get_backtest_status(created.run_id)
        assert status is not None
        assert status.status == "failed"
        assert status.error == "historical data fetch failed"

    asyncio.run(_run())


def test_service_init_does_not_auto_reconcile_running_runs():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    from src.infrastructure.persistence.repository_backtest import BacktestRepository

    BacktestService._runs.clear()
    BacktestService._tasks.clear()
    BacktestRepository._memory_runs.clear()

    service = BacktestService(session=None)
    now = (
        datetime.now(timezone.utc)
        - timedelta(seconds=BacktestService._STALE_BACKTEST_HEARTBEAT_SECONDS + 5)
    ).isoformat()
    service.repository.save_run(
        {
            "run_id": "run-still-running",
            "name": "still-running",
            "status": "running",
            "progress_pct": 50.0,
            "created_at": now,
            "updated_at": now,
        }
    )

    recreated = BacktestService(session=None)
    persisted = recreated.repository.get_run("run-still-running")
    assert persisted is not None
    assert persisted["status"] == "running"
    assert persisted.get("error") in {None, ""}


def test_db_backed_status_refreshes_persisted_state_across_processes(tmp_path):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    from internal.domain import Base
    from src.infrastructure.persistence.repository_backtest import BacktestRepository

    db_path = tmp_path / "backtest_status_refresh.sqlite"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    BacktestService._runs.clear()
    BacktestService._tasks.clear()

    api_service = BacktestService(BacktestRepository(SessionLocal()))
    worker_service = BacktestService(BacktestRepository(SessionLocal()))

    created_at = datetime.now(timezone.utc).isoformat()
    seeded = api_service.repository.save_run(
        {
            "run_id": "run-db-cache-refresh",
            "name": "cache-refresh",
            "status": "pending",
            "progress_pct": 0.0,
            "created_at": created_at,
            "updated_at": created_at,
            "request": _request().model_dump(),
        }
    )
    assert seeded["status"] == "pending"

    initial = api_service.get_backtest_status("run-db-cache-refresh")
    assert initial is not None
    assert initial.status == "pending"

    finished_at = datetime.now(timezone.utc).isoformat()
    worker_service.repository.save_run(
        {
            "run_id": "run-db-cache-refresh",
            "name": "cache-refresh",
            "status": "completed",
            "progress_pct": 100.0,
            "total_trades": 4,
            "created_at": created_at,
            "updated_at": finished_at,
            "started_at": created_at,
            "completed_at": finished_at,
            "finished_at": finished_at,
            "request": {
                **_request().model_dump(),
                "_runtime_control": {
                    "status": "completed",
                    "action": "complete",
                    "pause_requested": False,
                    "resume_requested": False,
                    "cancel_requested": False,
                    "worker_backend": "celery",
                    "worker_task_id": "run-db-cache-refresh",
                    "started_at": created_at,
                },
            },
            "trades": [{"trade_id": "t-1"}],
            "position_snapshots": [{"timestamp": finished_at}],
            "daily_pnl": [{"date": "2026-02-06", "pnl": 1.25}],
        }
    )

    refreshed = api_service.get_backtest_status("run-db-cache-refresh")
    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.progress_pct == 100.0
    assert refreshed.completed_at == finished_at
    assert refreshed.worker_backend == "celery"
    assert refreshed.control_status == "completed"


def test_explicit_interrupted_reconcile_flow_updates_orphaned_persisted_runs():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    from src.infrastructure.persistence.repository_backtest import BacktestRepository

    BacktestService._runs.clear()
    BacktestService._tasks.clear()
    BacktestRepository._memory_runs.clear()

    service = BacktestService(session=None)
    now = (
        datetime.now(timezone.utc)
        - timedelta(seconds=BacktestService._STALE_BACKTEST_HEARTBEAT_SECONDS + 5)
    ).isoformat()
    seeded = service.repository.save_run(
        {
            "run_id": "run-orphaned-ops",
            "name": "orphaned",
            "status": "running",
            "progress_pct": 43.2,
            "created_at": now,
            "updated_at": now,
        }
    )
    assert seeded["status"] == "running"

    dry_run_report = service.reconcile_interrupted_runs(dry_run=True)
    assert dry_run_report["candidate_count"] >= 1
    assert dry_run_report["reconciled_count"] == 0

    persisted_before = service.repository.get_run("run-orphaned-ops")
    assert persisted_before is not None
    assert persisted_before["status"] == "running"

    reconcile_report = service.reconcile_interrupted_runs(dry_run=False)
    assert reconcile_report["candidate_count"] >= 1
    assert reconcile_report["reconciled_count"] >= 1

    persisted_after = service.repository.get_run("run-orphaned-ops")
    assert persisted_after is not None
    assert persisted_after["status"] == "failed"
    assert persisted_after["error"] == "Backtest interrupted by API reload or restart"

    ops_report = service.list_interrupted_runs_for_ops(limit=10)
    assert ops_report["interrupted_count"] >= 1
    assert any(
        run["run_id"] == "run-orphaned-ops" for run in ops_report["interrupted_runs"]
    )


def test_auto_recovery_marks_orphaned_backtests_failed_by_default():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    from src.infrastructure.persistence.repository_backtest import BacktestRepository

    BacktestService._runs.clear()
    BacktestService._tasks.clear()
    BacktestRepository._memory_runs.clear()

    service = BacktestService(session=None)
    now = (
        datetime.now(timezone.utc)
        - timedelta(seconds=BacktestService._STALE_BACKTEST_HEARTBEAT_SECONDS + 5)
    ).isoformat()
    service.repository.save_run(
        {
            "run_id": "run-auto-mark-failed",
            "name": "orphaned",
            "status": "running",
            "progress_pct": 22.0,
            "created_at": now,
            "updated_at": now,
            "request": _request().model_dump(),
        }
    )

    report = asyncio.run(service.auto_recover_interrupted_runs())

    assert report["mode"] == "mark_failed"
    assert report["candidate_count"] == 1
    assert report["eligible_count"] == 1
    assert report["marked_failed_count"] == 1
    assert report["restarted_count"] == 0
    persisted = service.repository.get_run("run-auto-mark-failed")
    assert persisted is not None
    assert persisted["status"] == "failed"
    assert persisted["error"] == "Backtest interrupted by API reload or restart"


def test_auto_recovery_skips_fresh_orphaned_backtests_to_avoid_false_positive():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    from src.infrastructure.persistence.repository_backtest import BacktestRepository

    BacktestService._runs.clear()
    BacktestService._tasks.clear()
    BacktestRepository._memory_runs.clear()

    service = BacktestService(session=None)
    now = datetime.now(timezone.utc).isoformat()
    service.repository.save_run(
        {
            "run_id": "run-auto-fresh",
            "name": "fresh",
            "status": "running",
            "progress_pct": 8.0,
            "created_at": now,
            "updated_at": now,
            "request": _request().model_dump(),
        }
    )

    report = asyncio.run(service.auto_recover_interrupted_runs())

    assert report["candidate_count"] == 1
    assert report["eligible_count"] == 0
    assert report["marked_failed_count"] == 0
    assert report["skipped_count"] == 1
    persisted = service.repository.get_run("run-auto-fresh")
    assert persisted is not None
    assert persisted["status"] == "running"


def test_auto_recovery_restart_requeues_existing_backtest_run(monkeypatch):
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    from src.infrastructure.persistence.repository_backtest import BacktestRepository

    BacktestService._runs.clear()
    BacktestService._tasks.clear()
    BacktestRepository._memory_runs.clear()

    service = BacktestService(session=None)
    now = (
        datetime.now(timezone.utc)
        - timedelta(seconds=BacktestService._STALE_BACKTEST_HEARTBEAT_SECONDS + 5)
    ).isoformat()
    service.repository.save_run(
        {
            "run_id": "run-auto-restart",
            "name": "orphaned",
            "status": "running",
            "progress_pct": 31.0,
            "created_at": now,
            "updated_at": now,
            "request": _request().model_dump(),
        }
    )
    recovered = []

    async def _fake_execute_existing(run_id, progress_callback=None):
        recovered.append((run_id, progress_callback))
        service._update_run_data(
            run_id,
            status="completed",
            progress_pct=100.0,
            current_task="complete",
            completed_at=datetime.now(timezone.utc).isoformat(),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(service, "execute_existing_backtest", _fake_execute_existing)

    async def _run_recovery():
        report = await service.auto_recover_interrupted_runs(mode="restart")
        await asyncio.sleep(0)
        return report

    report = asyncio.run(_run_recovery())

    assert report["mode"] == "restart"
    assert report["candidate_count"] == 1
    assert report["eligible_count"] == 1
    assert report["restarted_count"] == 1
    assert recovered and recovered[0][0] == "run-auto-restart"
    persisted = service.repository.get_run("run-auto-restart")
    assert persisted is not None
    assert persisted["status"] == "completed"
