"""Tests for backtest checkpoint/resume (IMPROVEMENTS.md item 7).

Covers the pure checkpoint module (build/save/load/validate/delete against an
in-memory artifact store) and the service integration: resume skips completed
pairs and produces byte-identical results, hash mismatches fail open to a fresh
run, checkpoints are deleted on terminal completed/cancelled states, and the
pause path persists a resume point.
"""

import asyncio
import importlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_artifact_store_base():
    module = importlib.import_module("src.infrastructure.storage.artifacts")
    return module.ArtifactStore


def _load_checkpoint_module():
    return importlib.import_module("src.infrastructure.use_cases.backtest_checkpoint")


def _load_service_module():
    return importlib.import_module("src.infrastructure.use_cases.service_backtest")


def _load_models_module():
    return importlib.import_module("src.infrastructure.domain.models_backtest")


@pytest.fixture(autouse=True)
def _isolate_checkpoint_artifacts(tmp_path, monkeypatch):
    """Keep checkpoint + sidecar writes inside a per-test tmp dir."""
    monkeypatch.setenv("BACKTEST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("BACKTEST_CHECKPOINT_ENABLED", "true")
    # Disable ALL alias gates for external artifact backends. The structured
    # config injects MINIO_ENABLED / BACKTEST_ARTIFACT_STORAGE_ENABLED /
    # CLICKHOUSE_ENABLED from run.json; leaving any alias set makes the
    # repository build real MinIO/ClickHouse clients and attempt network I/O
    # (with transport retry storms) from inside these tests.
    for gate in (
        "BACKTEST_MINIO_ARTIFACTS_ENABLED",
        "BACKTEST_MINIO_ENABLED",
        "MINIO_ENABLED",
        "BACKTEST_ARTIFACT_STORAGE_ENABLED",
        "BACKTEST_CLICKHOUSE_WRITES_ENABLED",
        "BACKTEST_CLICKHOUSE_ENABLED",
        "CLICKHOUSE_ENABLED",
    ):
        monkeypatch.setenv(gate, "false")
    checkpoint_module = _load_checkpoint_module()
    checkpoint_module.reset_checkpoint_store()
    yield
    checkpoint_module.reset_checkpoint_store()


class _MemoryStore(_load_artifact_store_base()):
    """Minimal in-memory ArtifactStore double."""

    def __init__(self):
        self.objects = {}

    def reference_for(self, key):
        return f"memory://{key}"

    def put_bytes(self, key, data, *, content_type=None):
        self.objects[key] = data
        return self.reference_for(key)

    def read_bytes(self, key):
        return self.objects[key]

    def read_text(self, key):
        return self.objects[key].decode("utf-8")

    def exists(self, key):
        return key in self.objects

    def delete(self, key):
        return self.objects.pop(key, None) is not None


def _sample_checkpoint_payload(**overrides):
    checkpoint_module = _load_checkpoint_module()
    payload = checkpoint_module.build_checkpoint(
        run_id="run-1",
        payload_hash="hash-1",
        pair_plan=[["BTC-USD", "ETH-USD"], ["BTC-USD", "SOL-USD"]],
        completed_pairs_count=1,
        trades=[{"trade_id": "t-run-1-000", "pnl_usd": 5.0, "win": True}],
        position_snapshots=[{"timestamp": "2026-02-05T00:00:00Z"}],
        daily_pnl={"2026-02-05": 5.0},
        running_total_pnl=5.0,
        running_winners=1,
        running_gross_profit=5.0,
        running_gross_loss=0.0,
    )
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Pure module tests
# ---------------------------------------------------------------------------


def test_checkpoint_roundtrip_through_store():
    checkpoint_module = _load_checkpoint_module()
    store = _MemoryStore()
    payload = _sample_checkpoint_payload()
    assert checkpoint_module.save_checkpoint(store, payload) is True

    loaded = checkpoint_module.load_checkpoint(
        store, "run-1", expected_payload_hash="hash-1"
    )
    assert loaded is not None
    assert loaded["completed_pairs_count"] == 1
    assert loaded["pair_plan"] == [["BTC-USD", "ETH-USD"], ["BTC-USD", "SOL-USD"]]
    assert loaded["trades"] == payload["accumulators"]["trades"]
    assert loaded["daily_pnl"] == {"2026-02-05": 5.0}
    assert loaded["running_total_pnl"] == 5.0
    assert loaded["running_winners"] == 1


def test_checkpoint_load_missing_returns_none():
    checkpoint_module = _load_checkpoint_module()
    store = _MemoryStore()
    assert (
        checkpoint_module.load_checkpoint(
            store, "run-1", expected_payload_hash="hash-1"
        )
        is None
    )


def test_checkpoint_load_corrupt_json_returns_none():
    checkpoint_module = _load_checkpoint_module()
    store = _MemoryStore()
    store.objects["backtests/run-1/checkpoint.json"] = b"{not json"
    assert (
        checkpoint_module.load_checkpoint(
            store, "run-1", expected_payload_hash="hash-1"
        )
        is None
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": 99},
        {"run_id": "run-other"},
        {"payload_hash": "different-hash"},
        {"completed_pairs_count": 5},
        {"completed_pairs_count": -1},
        {"pair_plan": []},
        {"pair_plan": [["BTC-USD", "ETH-USD", "SOL-USD"]]},
        {"pair_plan": [["BTC-USD", 7]]},
        {"pair_plan": "not-a-list"},
        {"accumulators": {"trades": "nope"}},
        {
            "accumulators": {
                "trades": [],
                "position_snapshots": [],
                "daily_pnl": {"2026-02-05": "not-a-float"},
                "running_total_pnl": 0.0,
                "running_winners": 0,
                "running_gross_profit": 0.0,
                "running_gross_loss": 0.0,
            }
        },
    ],
)
def test_checkpoint_load_invalid_payloads_return_none(overrides):
    checkpoint_module = _load_checkpoint_module()
    store = _MemoryStore()
    assert checkpoint_module.save_checkpoint(
        store, _sample_checkpoint_payload(**overrides)
    )
    assert (
        checkpoint_module.load_checkpoint(
            store, "run-1", expected_payload_hash="hash-1"
        )
        is None
    )


def test_checkpoint_delete_best_effort():
    checkpoint_module = _load_checkpoint_module()
    store = _MemoryStore()
    assert checkpoint_module.delete_checkpoint(store, "run-1") is False
    checkpoint_module.save_checkpoint(store, _sample_checkpoint_payload())
    assert checkpoint_module.delete_checkpoint(store, "run-1") is True
    assert (
        checkpoint_module.load_checkpoint(
            store, "run-1", expected_payload_hash="hash-1"
        )
        is None
    )


def test_checkpoint_key_rejects_unsafe_run_ids():
    checkpoint_module = _load_checkpoint_module()
    with pytest.raises(ValueError):
        checkpoint_module._checkpoint_key("../escape")
    with pytest.raises(ValueError):
        checkpoint_module._checkpoint_key("a/b")


def test_checkpoints_enabled_env_parsing(monkeypatch):
    checkpoint_module = _load_checkpoint_module()
    monkeypatch.delenv("BACKTEST_CHECKPOINT_ENABLED", raising=False)
    assert checkpoint_module.checkpoints_enabled() is True
    for off in ("false", "0", "no", "off", "FALSE"):
        monkeypatch.setenv("BACKTEST_CHECKPOINT_ENABLED", off)
        assert checkpoint_module.checkpoints_enabled() is False
    monkeypatch.setenv("BACKTEST_CHECKPOINT_ENABLED", "true")
    assert checkpoint_module.checkpoints_enabled() is True


def test_local_artifact_store_delete(tmp_path):
    from src.infrastructure.storage.artifacts import LocalArtifactStore

    store = LocalArtifactStore(tmp_path / "artifacts")
    store.put_text("backtests/run-1/checkpoint.json", "{}")
    assert store.exists("backtests/run-1/checkpoint.json")
    assert store.delete("backtests/run-1/checkpoint.json") is True
    assert not store.exists("backtests/run-1/checkpoint.json")
    assert store.delete("backtests/run-1/checkpoint.json") is False


# ---------------------------------------------------------------------------
# Service integration tests
# ---------------------------------------------------------------------------


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

        candles = []
        idx = 0
        cursor = start
        while cursor <= end:
            wave = math.sin(idx / 8.0) * 15.0
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


def _request_dict():
    return {
        "name": "ckpt-run",
        "description": "checkpoint test",
        "start_date": "2026-02-05",
        "end_date": "2026-02-07",
        "initial_balance": 1000.0,
        "trading_parameters": {
            "resolution": "1HOUR",
            "zscore_threshold": 1.2,
            "usd_per_trade": 20.0,
            "stats_window": 12,
            "close_at_zscore_cross": True,
        },
        "pairs": ["BTC-USD", "ETH-USD", "SOL-USD"],
    }


async def _wait_for_terminal_status(service, run_id, timeout_seconds=15.0):
    end = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < end:
        status = service.get_backtest_status(run_id)
        assert status is not None
        if status.status in {"completed", "failed", "timeout", "cancelled", "stale"}:
            return status.status
        await asyncio.sleep(0.02)
    raise TimeoutError("backtest did not reach terminal status in time")


def _install_simulate_recorder(monkeypatch):
    """Wrap ``_simulate_pair`` to record (pair, offset, outputs) per call."""
    service_module = _load_service_module()
    original = service_module.BacktestService._simulate_pair
    calls = []

    async def _recording(self, **kwargs):
        trades, snapshots, daily_pnl = await original(self, **kwargs)
        calls.append(
            {
                "pair": (kwargs["market_a"], kwargs["market_b"]),
                "offset": kwargs["trade_index_offset"],
                "trades": trades,
                "snapshots": snapshots,
                "daily_pnl": daily_pnl,
            }
        )
        return trades, snapshots, daily_pnl

    monkeypatch.setattr(service_module.BacktestService, "_simulate_pair", _recording)
    return calls


def _aggregate_pair_outputs(pair_records):
    """Mirror the pair-loop accumulation for the given per-pair records."""
    trades = []
    snapshots = []
    daily_pnl = {}
    total_pnl = 0.0
    winners = 0
    gross_profit = 0.0
    gross_loss = 0.0
    for record in pair_records:
        for trade in record["trades"]:
            pnl = float(trade["pnl_usd"])
            total_pnl += pnl
            if bool(trade["win"]):
                winners += 1
            if pnl > 0:
                gross_profit += pnl
            elif pnl < 0:
                gross_loss += pnl
        trades.extend(record["trades"])
        snapshots.extend(record["snapshots"])
        for day, pnl in record["daily_pnl"].items():
            daily_pnl[day] = round(daily_pnl.get(day, 0.0) + pnl, 4)
    return {
        "trades": trades,
        "position_snapshots": snapshots,
        "daily_pnl": daily_pnl,
        "running_total_pnl": total_pnl,
        "running_winners": winners,
        "running_gross_profit": gross_profit,
        "running_gross_loss": gross_loss,
    }


def test_resume_skips_completed_pairs_and_matches_fresh_results(monkeypatch, tmp_path):
    service_module = _load_service_module()
    checkpoint_module = _load_checkpoint_module()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "false")

    service = BacktestService(session=None)
    request = _request_dict()

    async def _run():
        # Phase 1 — reference fresh run (asyncio backend executes inline).
        calls_a = _install_simulate_recorder(monkeypatch)
        created_a = await service.create_and_run_backtest(dict(request))
        assert await _wait_for_terminal_status(service, created_a.run_id) == (
            "completed"
        )
        details_a = service.get_backtest_details(created_a.run_id)
        plan_a = [record["pair"] for record in calls_a]
        assert len(plan_a) >= 2

        # Phase 2 — seed a checkpoint claiming the first pair is complete,
        # then execute the real recovery path on the same request.
        completed_pair_records = calls_a[:1]
        accumulators = _aggregate_pair_outputs(completed_pair_records)
        monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "nats")
        created_b = await service.create_and_run_backtest(dict(request))
        assert created_b.status == "pending"

        run_b = service._load_run_data(created_b.run_id)
        payload_hash = service._request_payload_hash(run_b["request"])
        checkpoint = checkpoint_module.build_checkpoint(
            run_id=created_b.run_id,
            payload_hash=payload_hash,
            pair_plan=plan_a,
            completed_pairs_count=1,
            **accumulators,
        )
        store = checkpoint_module.get_checkpoint_store()
        assert checkpoint_module.save_checkpoint(store, checkpoint) is True

        calls_b = _install_simulate_recorder(monkeypatch)
        await service.execute_existing_backtest(created_b.run_id, None)

        # Skipped the completed pair entirely; offsets continue past loaded trades.
        assert [record["pair"] for record in calls_b] == plan_a[1:]
        assert calls_b[0]["offset"] == len(accumulators["trades"])

        # Final results identical to the uninterrupted reference run
        # (trade_id embeds the run_id, so compare it as index continuity).
        trades_b = service.get_backtest_trades(created_b.run_id, limit=5000)
        trades_a = service.get_backtest_trades(created_a.run_id, limit=5000)

        def _without_ids(trades):
            stripped = []
            for trade in trades:
                data = (
                    trade.model_dump(exclude={"trade_id"})
                    if hasattr(trade, "model_dump")
                    else {k: v for k, v in vars(trade).items() if k != "trade_id"}
                )
                stripped.append(data)
            return stripped

        def _id_indexes(trades):
            return [int(trade.trade_id.rsplit("-", 1)[1]) for trade in trades]

        assert _without_ids(trades_b) == _without_ids(trades_a)
        assert _id_indexes(trades_b) == _id_indexes(trades_a)
        details_b = service.get_backtest_details(created_b.run_id)
        assert details_b.total_trades == details_a.total_trades
        assert details_b.total_pnl == details_a.total_pnl
        assert details_b.win_rate == details_a.win_rate
        assert details_b.sharpe_ratio == details_a.sharpe_ratio
        assert details_b.max_drawdown_pct == details_a.max_drawdown_pct
        assert details_b.profit_factor == details_a.profit_factor

    asyncio.run(_run())


def test_resume_ignored_on_payload_hash_mismatch(monkeypatch, tmp_path, caplog):
    service_module = _load_service_module()
    checkpoint_module = _load_checkpoint_module()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "false")

    service = BacktestService(session=None)
    request = _request_dict()

    async def _run():
        calls_ref = _install_simulate_recorder(monkeypatch)
        created_ref = await service.create_and_run_backtest(dict(request))
        assert await _wait_for_terminal_status(service, created_ref.run_id) == (
            "completed"
        )
        plan_ref = [record["pair"] for record in calls_ref]

        monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "nats")
        created = await service.create_and_run_backtest(dict(request))

        checkpoint = checkpoint_module.build_checkpoint(
            run_id=created.run_id,
            payload_hash="stale-hash",
            pair_plan=plan_ref,
            completed_pairs_count=1,
            **_aggregate_pair_outputs(calls_ref[:1]),
        )
        store = checkpoint_module.get_checkpoint_store()
        assert checkpoint_module.save_checkpoint(store, checkpoint) is True

        calls = _install_simulate_recorder(monkeypatch)
        with caplog.at_level("WARNING"):
            await service.execute_existing_backtest(created.run_id, None)
        assert [record["pair"] for record in calls] == plan_ref
        assert any("payload hash mismatch" in message for message in caplog.messages)

    asyncio.run(_run())


def test_checkpoint_deleted_after_terminal_completion(monkeypatch):
    service_module = _load_service_module()
    checkpoint_module = _load_checkpoint_module()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "false")

    saved = []
    original_save = checkpoint_module.save_checkpoint

    def _recording_save(store, payload):
        result = original_save(store, payload)
        saved.append(payload.get("run_id"))
        return result

    monkeypatch.setattr(checkpoint_module, "save_checkpoint", _recording_save)

    service = BacktestService(session=None)

    async def _run():
        created = await service.create_and_run_backtest(_request_dict())
        assert await _wait_for_terminal_status(service, created.run_id) == ("completed")
        # Checkpoints were written during the run...
        assert set(saved) == {created.run_id}
        # ...and the terminal state cleaned the resume point up.
        store = checkpoint_module.get_checkpoint_store()
        assert not store.exists(f"backtests/{created.run_id}/checkpoint.json")

    asyncio.run(_run())


def test_checkpoints_disabled_writes_and_resumes_nothing(monkeypatch):
    service_module = _load_service_module()
    checkpoint_module = _load_checkpoint_module()
    BacktestService = service_module.BacktestService

    async def _fake_connect():
        return _FakeClient()

    monkeypatch.setattr(service_module, "connect_dydx", _fake_connect)
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "asyncio")
    monkeypatch.setenv("BACKTEST_WORKER_BACKEND_AUTO_REPROBE", "false")
    monkeypatch.setenv("BACKTEST_CHECKPOINT_ENABLED", "false")

    saved = []
    monkeypatch.setattr(
        checkpoint_module,
        "save_checkpoint",
        lambda store, payload: saved.append(payload.get("run_id")) or True,
    )

    service = BacktestService(session=None)
    request = _request_dict()

    async def _run():
        created = await service.create_and_run_backtest(dict(request))
        assert await _wait_for_terminal_status(service, created.run_id) == ("completed")
        assert saved == []

        # A pre-existing checkpoint must also be ignored when disabled.
        monkeypatch.setenv("BACKTEST_WORKER_BACKEND", "nats")
        created_b = await service.create_and_run_backtest(dict(request))
        run_b = service._load_run_data(created_b.run_id)
        checkpoint = checkpoint_module.build_checkpoint(
            run_id=created_b.run_id,
            payload_hash=service._request_payload_hash(run_b["request"]),
            pair_plan=[("BTC-USD", "ETH-USD")],
            completed_pairs_count=1,
            **{
                "trades": [{"trade_id": "x", "pnl_usd": 1.0, "win": True}],
                "position_snapshots": [],
                "daily_pnl": {},
                "running_total_pnl": 1.0,
                "running_winners": 1,
                "running_gross_profit": 1.0,
                "running_gross_loss": 0.0,
            },
        )
        store = checkpoint_module.get_checkpoint_store()
        assert checkpoint_module.save_checkpoint(store, checkpoint) is True

        calls = _install_simulate_recorder(monkeypatch)
        await service.execute_existing_backtest(created_b.run_id, None)
        assert ("BTC-USD", "ETH-USD") in [record["pair"] for record in calls]

    asyncio.run(_run())


def test_pause_entry_invokes_checkpoint_writer(monkeypatch):
    service_module = _load_service_module()
    BacktestService = service_module.BacktestService
    service = BacktestService(session=None)

    control_states = [
        {"pause_requested": True, "resume_requested": False},
        {"pause_requested": False, "resume_requested": True},
    ]
    control_calls = []

    def _fake_control(run_id):
        del run_id
        control_calls.append(1)
        if len(control_calls) == 1:
            return dict(control_states[0])
        return dict(control_states[1])

    monkeypatch.setattr(service, "_load_fresh_runtime_control", _fake_control)
    monkeypatch.setattr(service, "_persist_run_data", lambda run_data: run_data)

    writer_calls = []

    async def _run():
        import time as _time

        deadline = _time.monotonic() + 30.0
        await service._honor_runtime_control(
            "run-pause",
            {"run_id": "run-pause", "status": "running"},
            deadline,
            checkpoint_writer=lambda: writer_calls.append(1),
        )

    asyncio.run(_run())
    assert writer_calls == [1]
