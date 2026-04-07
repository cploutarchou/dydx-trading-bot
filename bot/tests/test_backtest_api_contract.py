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

    def list_interrupted_runs_for_ops(self, limit=50):
        return {
            "interruption_error": "Backtest interrupted by API reload or restart",
            "orphaned_in_progress": [
                {
                    "run_id": "run-orphaned",
                    "status": "running",
                    "error": None,
                }
            ][:limit],
            "interrupted_runs": [
                {
                    "run_id": "run-interrupted",
                    "status": "failed",
                    "error": "Backtest interrupted by API reload or restart",
                }
            ][:limit],
            "orphaned_count": 1,
            "interrupted_count": 1,
        }

    def reconcile_interrupted_runs(self, dry_run=True):
        return {
            "interruption_error": "Backtest interrupted by API reload or restart",
            "dry_run": bool(dry_run),
            "candidates": [{"run_id": "run-orphaned", "status": "running"}],
            "reconciled": ([] if dry_run else [{"run_id": "run-orphaned", "status": "failed"}]),
            "candidate_count": 1,
            "reconciled_count": 0 if dry_run else 1,
        }


class _RunResult:
    def __init__(self, payload):
        self._payload = payload
        self.name = payload.get("name", "manual-backtest")

    def model_dump(self):
        return dict(self._payload)


class _RunStubService:
    async def create_and_run_backtest(self, request):
        return _RunResult(
            {
                "run_id": "fallback-run",
                "name": request.name,
                "status": "queued",
                "progress_pct": 0.0,
            }
        )


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


def test_interrupted_runs_endpoint_exposes_ops_visibility_fields(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    response = asyncio.run(_call(server.list_interrupted_backtests()))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["orphaned_count"] == 1
    assert payload["data"]["interrupted_count"] == 1
    assert payload["data"]["count"] == 2
    assert payload["data"]["interrupted_runs"][0]["run_id"] == "run-interrupted"


def test_interrupted_reconcile_endpoint_supports_dry_run(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    response = asyncio.run(_call(server.reconcile_interrupted_backtests(dry_run=True)))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["candidate_count"] == 1
    assert payload["data"]["reconciled_count"] == 0


def test_admin_interrupted_routes_reuse_same_payload_contract(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    list_response = asyncio.run(
        _call(server.list_interrupted_backtests_admin(limit=10, current_user=object()))
    )
    list_payload = json.loads(list_response.body)
    assert list_payload["success"] is True
    assert list_payload["data"]["orphaned_count"] == 1
    assert list_payload["data"]["interrupted_count"] == 1

    reconcile_response = asyncio.run(
        _call(
            server.reconcile_interrupted_backtests_admin(
                dry_run=False,
                current_user=object(),
            )
        )
    )
    reconcile_payload = json.loads(reconcile_response.body)
    assert reconcile_payload["success"] is True
    assert reconcile_payload["data"]["dry_run"] is False
    assert reconcile_payload["data"]["reconciled_count"] == 1


def test_openapi_documents_standard_response_envelope():
    server = _load_server_module()
    schema = server.app.openapi()

    assert "/api/v1/admin/backtests/interrupted" in schema["paths"]
    assert "/api/v1/admin/backtests/interrupted/reconcile" in schema["paths"]
    assert "/api/v1/capabilities" in schema["paths"]

    status_schema = schema["paths"]["/api/v1/backtests/{run_id}/status"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    all_of = status_schema.get("allOf", [])

    assert any(
        isinstance(item, dict)
        and item.get("$ref") == "#/components/schemas/StandardApiResponse"
        for item in all_of
    )


def test_capabilities_endpoint_lists_http_and_websocket_scopes():
    server = _load_server_module()

    response = asyncio.run(_call(server.api_capabilities()))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert "GET /api/v1/bots" in payload["data"]["http_endpoints"]
    assert "GET /api/v1/backtests" in payload["data"]["http_endpoints"]
    assert "POST /api/v1/bots" in payload["data"]["command_endpoints"]
    assert "GET /api/v1/bots" in payload["data"]["query_endpoints"]
    assert "WS /ws/strategies" in payload["data"]["websocket_channels"]
    assert payload["data"]["event_channels"] == payload["data"]["websocket_channels"]
    assert "WS /ws/bots/{bot_instance_id}" in payload["data"]["websocket_channels"]
    assert "WS /ws/backtests/{run_id}" in payload["data"]["websocket_channels"]


def test_run_backtest_compat_falls_back_when_strategy_lookup_fails(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _RunStubService())

    async def _stub_markets(_pairs, _max):
        return ["BTC-USD", "ETH-USD"]

    monkeypatch.setattr(server, "_resolve_backtest_markets", _stub_markets)

    def _raise_lookup(_strategy_id):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(server.InMemoryStrategyStore, "get", _raise_lookup)

    request = server.BacktestRunRequestCompat(
        start_date="2026-03-01",
        end_date="2026-03-31",
        strategy_id=1,
    )

    response = asyncio.run(_call(server.run_backtest_compat(request)))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["run_id"] == "fallback-run"
    assert payload["data"]["progress"] == 0.0


def test_api_response_sanitizes_internal_error_details():
    server = _load_server_module()

    response = server.api_response(
        success=False,
        message="Internal server error: (psycopg2.OperationalError) db exploded",
        status_code=500,
    )
    payload = json.loads(response.body)

    assert payload["message"] == "Internal server error"
    assert "psycopg2" not in payload["message"]


