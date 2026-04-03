"""Contract tests for backend-facing backtest API response aliases."""

import asyncio
import importlib
import json


def _load_server_module():
    return importlib.import_module("src.api.server")


class _ModelDumpObject:
    def __init__(self, payload):
        self._payload = payload
        for key, value in payload.items():
            setattr(self, key, value)

    def model_dump(self):
        return dict(self._payload)


class _StubService:
    def list_backtest_runs(self, **_kwargs):
        return _ModelDumpObject(
            {
                "runs": [{"run_id": "run-1", "status": "completed", "progress_pct": 100.0}],
                "total": 1,
            }
        )

    def get_backtest_status(self, run_id):
        return _ModelDumpObject(
            {
                "run_id": run_id,
                "status": "running",
                "progress_pct": 42.5,
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )

    def get_backtest_trades(self, **_kwargs):
        return [_ModelDumpObject({"trade_id": "t-1", "market_1": "BTC-USD", "market_2": "ETH-USD"})]

    def get_position_snapshots(self, **_kwargs):
        return [{"timestamp": "2026-01-01T00:00:00Z", "positions": []}]

    def get_runtime_health(self):
        return {"queue_depth": 2, "active_jobs": 1, "total_runs": 5}


async def _call(awaitable):
    return await awaitable


def test_list_backtests_exposes_backtests_alias(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    response = asyncio.run(_call(server.list_backtests()))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert "runs" in payload["data"]
    assert "backtests" in payload["data"]
    assert "count" in payload["data"]
    assert payload["data"]["backtests"][0]["run_id"] == "run-1"


def test_backtest_status_exposes_progress_alias(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    response = asyncio.run(_call(server.get_backtest_status("run-abc")))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["run_id"] == "run-abc"
    assert payload["data"]["progress"] == payload["data"]["progress_pct"]
    assert payload["data"]["count"] == 1


def test_run_scoped_trade_and_snapshot_routes_include_run_id(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    trades_response = asyncio.run(_call(server.get_backtest_trades("run-xyz")))
    trades_payload = json.loads(trades_response.body)
    assert trades_payload["data"]["run_id"] == "run-xyz"
    assert trades_payload["data"]["total"] == 1
    assert trades_payload["data"]["count"] == 1

    snapshots_response = asyncio.run(_call(server.get_position_snapshots("run-xyz")))
    snapshots_payload = json.loads(snapshots_response.body)
    assert snapshots_payload["data"]["run_id"] == "run-xyz"
    assert "position_snapshots" in snapshots_payload["data"]
    assert "snapshots" in snapshots_payload["data"]
    assert snapshots_payload["data"]["count"] == 1


def test_sync_health_endpoint_returns_runtime_counters(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    response = asyncio.run(_call(server.backtest_sync_health()))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["queue_depth"] == 2
    assert payload["data"]["active_jobs"] == 1
    assert payload["data"]["total_runs"] == 5

