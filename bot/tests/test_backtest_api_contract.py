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
                "runs": [
                    {"run_id": "run-1", "status": "completed", "progress_pct": 100.0}
                ],
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
        return [
            _ModelDumpObject(
                {"trade_id": "t-1", "market_1": "BTC-USD", "market_2": "ETH-USD"}
            )
        ]

    def get_position_snapshots(self, **_kwargs):
        return [{"timestamp": "2026-01-01T00:00:00Z", "positions": []}]

    def get_advanced_performance_metrics(self, run_id, benchmark="BTC-USD"):
        return {
            "run_id": run_id,
            "benchmark": benchmark,
            "sharpe_ratio": 1.25,
            "max_drawdown_pct": 3.5,
        }

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
            "reconciled": (
                [] if dry_run else [{"run_id": "run-orphaned", "status": "failed"}]
            ),
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
    def __init__(self):
        self.progress_callback = None
        self.last_request = None

    async def create_and_run_backtest(self, request, progress_callback=None):
        self.progress_callback = progress_callback
        self.last_request = request
        return _RunResult(
            {
                "run_id": "fallback-run",
                "name": request.name,
                "status": "pending",
                "progress_pct": 0.0,
                "timeout_seconds": getattr(request, "timeout_seconds", None),
            }
        )


class _MarketStubClient:
    class _Node:
        async def close(self):
            return None

    class _Markets:
        async def get_perpetual_markets(self):
            return {
                "markets": {
                    "ETH-USD": {"status": "ACTIVE"},
                    "BTC-USD": {"status": "ACTIVE"},
                    "SOL-USD": {"status": "ACTIVE"},
                }
            }

    class _Indexer:
        def __init__(self):
            self.markets = _MarketStubClient._Markets()

    def __init__(self):
        self.node = self._Node()
        self.indexer = self._Indexer()


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
    monkeypatch.setattr(
        server.manager,
        "get_backtest_send_failure_metrics",
        lambda run_id: {
            "run_id": run_id,
            "alert_threshold": 5,
            "alert_window_seconds": 60.0,
            "metrics": {
                "total_send_attempts": 0,
                "total_send_successes": 0,
                "total_send_failures": 0,
                "consecutive_send_failures": 0,
                "recent_send_failures": 0,
                "last_error_type": None,
                "last_error_repr": None,
                "last_failure_at": None,
                "last_success_at": None,
                "updated_at": None,
            },
            "alert_recommended": False,
        },
    )

    response = asyncio.run(_call(server.get_backtest_status("run-abc")))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["run_id"] == "run-abc"
    assert payload["data"]["progress"] == payload["data"]["progress_pct"]
    assert payload["data"]["count"] == 1
    assert payload["data"]["websocket_send_metrics"]["run_id"] == "run-abc"


def test_backtest_websocket_metrics_endpoint_exposes_run_scoped_payload(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())
    monkeypatch.setattr(
        server.manager,
        "get_backtest_send_failure_metrics",
        lambda run_id: {
            "run_id": run_id,
            "alert_threshold": 5,
            "alert_window_seconds": 60.0,
            "metrics": {
                "total_send_attempts": 12,
                "total_send_successes": 9,
                "total_send_failures": 3,
                "consecutive_send_failures": 2,
                "recent_send_failures": 2,
                "last_error_type": "RuntimeError",
                "last_error_repr": "RuntimeError('socket')",
                "last_failure_at": "2026-05-03T00:00:00Z",
                "last_success_at": "2026-05-03T00:00:10Z",
                "updated_at": "2026-05-03T00:00:10Z",
            },
            "alert_recommended": False,
        },
    )

    response = asyncio.run(_call(server.get_backtest_websocket_metrics("run-abc")))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["run_id"] == "run-abc"
    assert payload["data"]["status"] == "running"
    assert payload["data"]["metrics"]["run_id"] == "run-abc"
    assert payload["data"]["metrics"]["metrics"]["total_send_failures"] == 3


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


def test_performance_metrics_endpoint_accepts_sync_service(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    response = asyncio.run(_call(server.get_advanced_performance_metrics("run-xyz")))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["run_id"] == "run-xyz"
    assert payload["data"]["benchmark"] == "BTC-USD"


def test_perpetual_markets_endpoint_returns_sorted_chain_markets(monkeypatch):
    server = _load_server_module()

    async def connect_stub():
        return _MarketStubClient()

    monkeypatch.setattr(server, "connect_dydx", connect_stub)

    response = asyncio.run(_call(server.list_perpetual_markets(limit=2)))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["markets"] == ["BTC-USD", "ETH-USD"]
    assert payload["data"]["source"] == "dydx"


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


def test_restart_returns_409_when_original_request_payload_missing(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    response = asyncio.run(_call(server.restart_backtest("run-abc")))
    payload = json.loads(response.body)

    assert response.status_code == 409
    assert payload["success"] is False
    assert "payload is unavailable" in payload["message"]
    assert payload["data"]["error"] == "missing_original_request_payload"


def test_retry_returns_409_when_original_request_payload_missing(monkeypatch):
    server = _load_server_module()
    monkeypatch.setattr(server, "get_backtest_service", lambda: _StubService())

    response = asyncio.run(_call(server.retry_backtest("run-abc")))
    payload = json.loads(response.body)

    assert response.status_code == 409
    assert payload["success"] is False
    assert "payload is unavailable" in payload["message"]
    assert payload["data"]["error"] == "missing_original_request_payload"


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
    assert "/api/v1/runtime/db-config" in schema["paths"]

    status_schema = schema["paths"]["/api/v1/backtests/{run_id}/status"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]
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


def test_run_backtest_compat_errors_when_strategy_lookup_fails(monkeypatch):
    server = _load_server_module()
    stub_service = _RunStubService()
    monkeypatch.setattr(server, "get_backtest_service", lambda: stub_service)

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
        pairs=["BTC-USD", "ETH-USD"],
        timeout_seconds=120,
    )

    response = asyncio.run(_call(server.run_backtest_compat(request)))
    payload = json.loads(response.body)

    assert response.status_code == 404
    assert payload["success"] is False
    assert payload["data"]["error"] == "STRATEGY_NOT_FOUND"
    assert stub_service.last_request is None


def test_run_backtest_compat_uses_strategy_snapshot_when_lookup_fails(monkeypatch):
    server = _load_server_module()
    stub_service = _RunStubService()
    monkeypatch.setattr(server, "get_backtest_service", lambda: stub_service)

    async def _stub_markets(_pairs, _max):
        return ["BTC-USD", "ETH-USD"]

    monkeypatch.setattr(server, "_resolve_backtest_markets", _stub_markets)

    def _raise_lookup(_strategy_id):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(server.InMemoryStrategyStore, "get", _raise_lookup)

    request = server.BacktestRunRequestCompat(
        start_date="2026-03-01",
        end_date="2026-03-31",
        strategy_id=4,
        name="snapshot fallback",
        pairs=["BTC-USD", "ETH-USD"],
        strategy_payload_snapshot={
            "id": 4,
            "name": "Backend Strategy",
            "description": "Snapshot from backend DB",
            "starting_balance": 2500,
            "pair_selection_mode": "liquidity",
            "zscore_threshold": 1.2,
            "stats_window": 18,
        },
    )

    response = asyncio.run(_call(server.run_backtest_compat(request)))
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["success"] is True
    assert stub_service.last_request is not None
    assert stub_service.last_request.strategy_id == 4
    assert stub_service.last_request.strategy_payload_snapshot["id"] == 4
    assert (
        stub_service.last_request.strategy_payload_snapshot["name"]
        == "Backend Strategy"
    )


def test_create_backtest_uses_strategy_snapshot_when_lookup_returns_none(monkeypatch):
    server = _load_server_module()
    stub_service = _RunStubService()
    monkeypatch.setattr(server, "get_backtest_service", lambda: stub_service)

    async def _stub_markets(_pairs, _max):
        return ["BTC-USD", "ETH-USD"]

    monkeypatch.setattr(server, "_resolve_backtest_markets", _stub_markets)
    monkeypatch.setattr(server.InMemoryStrategyStore, "get", lambda _strategy_id: None)

    request = server.BacktestRunRequestCompat(
        start_date="2026-03-01",
        end_date="2026-03-31",
        strategy_id=9,
        pairs=["BTC-USD", "ETH-USD"],
        strategy_payload_snapshot={
            "name": "Backend-only Strategy",
            "description": "Persisted in backend DB",
            "starting_balance": 1500,
            "pair_selection_mode": "liquidity",
            "zscore_threshold": 1.4,
            "stats_window": 20,
        },
    )

    response = asyncio.run(_call(server.create_backtest(request)))
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["success"] is True
    assert stub_service.last_request is not None
    assert stub_service.last_request.strategy_id == 9
    assert stub_service.last_request.strategy_payload_snapshot["id"] == 9
    assert (
        stub_service.last_request.strategy_payload_snapshot["name"]
        == "Backend-only Strategy"
    )


def test_run_backtest_compat_errors_when_selected_pairs_missing(monkeypatch):
    server = _load_server_module()
    stub_service = _RunStubService()
    monkeypatch.setattr(server, "get_backtest_service", lambda: stub_service)

    request = server.BacktestRunRequestCompat(
        start_date="2026-03-01",
        end_date="2026-03-31",
        strategy_id=1,
        timeout_seconds=120,
    )

    response = asyncio.run(_call(server.run_backtest_compat(request)))
    payload = json.loads(response.body)

    assert response.status_code == 422
    assert payload["success"] is False
    assert payload["data"]["error"] == "SELECTED_PAIRS_MISSING"
    assert stub_service.last_request is None


def test_strategy_to_backtest_request_preserves_request_trading_parameters():
    server = _load_server_module()

    strategy = {
        "id": 4,
        "name": "Aggressive Strategy",
        "description": "Aggressive strategy with lower thresholds for frequent trading",
        "starting_balance": 1000,
        "pair_selection_mode": "liquidity",
        "benchmark_symbol": "BTC-USD",
    }

    request = server.BacktestRunRequestCompat(
        start_date="2026-03-29",
        end_date="2026-04-28",
        strategy_id=4,
        max_pairs=6,
        pair_selection_mode="liquidity",
        trading_parameters={
            "zscore_threshold": 1.0,
            "stats_window": 14,
            "benchmark_symbol": "ETH-USD",
            "resolution": "4HOUR",
            "max_history_days": 120,
        },
    )

    result = server._strategy_to_backtest_request(
        strategy,
        request,
        ["ETH-USD", "SOL-USD", "ADA-USD"],
    )

    assert result.trading_parameters["benchmark_symbol"] == "ETH-USD"
    assert result.trading_parameters["resolution"] == "4HOUR"
    assert result.trading_parameters["max_history_days"] == 120
    assert result.trading_parameters["pair_selection_mode"] == "liquidity"
    assert result.trading_parameters["max_pairs"] == 6
    assert result.pairs == ["ETH-USD", "SOL-USD", "ADA-USD"]
    assert result.selected_pairs == ["ETH-USD", "SOL-USD", "ADA-USD"]
    assert result.strategy_payload_snapshot["id"] == 4


def test_run_backtest_compat_preserves_explicit_payload_semantics(monkeypatch):
    server = _load_server_module()
    stub_service = _RunStubService()
    monkeypatch.setattr(server, "get_backtest_service", lambda: stub_service)

    async def _stub_markets(_pairs, _max):
        return ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD"]

    monkeypatch.setattr(server, "_resolve_backtest_markets", _stub_markets)
    monkeypatch.setattr(
        server.InMemoryStrategyStore,
        "get",
        lambda _strategy_id: {
            "id": 7,
            "name": "Stored Strategy",
            "description": "Stored defaults should not override explicit request values",
            "starting_balance": 9999.0,
            "pair_selection_mode": "liquidity",
            "zscore_threshold": 2.5,
            "stats_window": 60,
            "benchmark_symbol": "BTC-USD",
            "resolution": "1HOUR",
        },
    )

    request = server.BacktestRunRequestCompat(
        start_date="2026-03-01",
        end_date="2026-03-31",
        strategy_id=7,
        name="Payload Fidelity Run",
        description="should keep explicit request semantics",
        initial_balance=4321.0,
        max_pairs=7,
        pairs=["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD"],
        trading_parameters={
            "zscore_threshold": 1.1,
            "stats_window": 18,
            "usd_per_trade": 25.0,
            "pair_selection_mode": "cointegration",
            "benchmark_symbol": "ETH-USD",
            "resolution": "4HOURS",
            "max_history_days": 150,
        },
    )

    response = asyncio.run(_call(server.run_backtest_compat(request)))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert stub_service.last_request is not None

    executed_request = stub_service.last_request
    assert executed_request.strategy_id == 7
    assert executed_request.strategy_payload_snapshot["id"] == 7
    assert executed_request.start_date == "2026-03-01"
    assert executed_request.end_date == "2026-03-31"
    assert executed_request.initial_balance == 4321.0
    assert executed_request.max_pairs == 7
    assert executed_request.pair_selection_mode == "cointegration"
    assert executed_request.pairs == ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD"]
    assert executed_request.selected_pairs == [
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
        "AVAX-USD",
    ]

    # Explicit request values should win over strategy defaults.
    assert executed_request.trading_parameters["zscore_threshold"] == 1.1
    assert executed_request.trading_parameters["stats_window"] == 18
    assert executed_request.trading_parameters["benchmark_symbol"] == "ETH-USD"
    assert executed_request.trading_parameters["resolution"] == "4HOURS"
    assert executed_request.trading_parameters["pair_selection_mode"] == "cointegration"
    assert executed_request.trading_parameters["max_pairs"] == 7

    # Missing values can still be filled from strategy defaults.
    assert "stop_loss_pct" in executed_request.trading_parameters
    assert "take_profit_pct" in executed_request.trading_parameters


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


def test_runtime_db_config_endpoint_returns_sanitized_payload(monkeypatch):
    server = _load_server_module()

    class _FakeDbConfig:
        def to_diagnostics(self):
            return {
                "db_type": "postgresql",
                "cutover_mode": "shared",
                "connection_source": "shared_db_fields",
                "field_source": "shared_db_fields",
                "database_url_configured": False,
                "host": "localhost",
                "port": "5432",
                "name": "dydx_bot",
                "user": "dydx_bot",
                "password_configured": True,
                "timeout_seconds": 5,
                "pool_size": 5,
                "max_overflow": 5,
                "max_connections": 10,
                "ssl_enabled": False,
                "echo_sql": False,
            }

    monkeypatch.setattr(server, "DatabaseConfig", _FakeDbConfig)

    response = asyncio.run(_call(server.runtime_db_config(current_user=object())))
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["data"]["db_type"] == "postgresql"
    assert payload["data"]["password_configured"] is True
    assert payload["data"]["max_connections"] == 10
    assert payload["data"]["count"] == 1


def test_check_backtest_admission_blocks_on_persistence_overload(monkeypatch):
    server = _load_server_module()
    monkeypatch.setenv("BACKTEST_BLOCK_ON_PERSISTENCE_OVERLOAD", "true")

    class _OverloadedService:
        def get_runtime_health(self):
            return {
                "queue_depth": 0,
                "active_jobs": 0,
                "total_runs": 0,
                "persistence_pool_overloaded": True,
                "persistence_pool_overload_events_recent": 3,
            }

    response = server._check_backtest_admission(_OverloadedService())
    assert response is not None

    payload = json.loads(response.body)
    assert payload["success"] is False
    assert payload["data"]["error"] == "backtest_capacity_reached"
    assert payload["data"]["reason"] == "persistence_pool_overload"
    assert payload["data"]["cannot_accept_new_runs"] is True
