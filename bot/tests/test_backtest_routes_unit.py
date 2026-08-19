"""Unit coverage for the backtest route family (src/api/v1/backtests.py).

Drives every route handler directly (the established contract-test pattern)
with the compat namespace pinned to a per-test dict, so every
``_compat(...)`` seam is stubbable without importing the server module.
No DB, no Redis, no real dYdX client.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from types import SimpleNamespace

import pytest

import src.api.v1.backtests as backtests
from src.api.v1.backtests import BacktestComparisonRequest, BacktestRunRequestCompat
from src.infrastructure.domain.models_backtest import BacktestConfigRequest


@pytest.fixture(autouse=True)
def compat_ns(monkeypatch):
    """Pin the compat provider to an empty per-test dict and isolate caches."""
    ns: dict = {}
    monkeypatch.setattr(backtests, "_compatibility_namespace_provider", lambda: ns)
    backtests._backtest_endpoint_cache.clear()
    metrics = backtests._strategy_resolution_metrics
    metrics_snapshot = dict(metrics.get("counts", {}))
    recent = list(backtests._strategy_resolution_recent_paths)
    yield ns
    backtests._backtest_endpoint_cache.clear()
    with backtests._strategy_resolution_metrics_lock:
        metrics["counts"] = metrics_snapshot
        backtests._strategy_resolution_recent_paths.clear()
        backtests._strategy_resolution_recent_paths.extend(recent)


class _ModelDump:
    """Attribute bag whose model_dump() round-trips the payload."""

    def __init__(self, payload):
        self._payload = dict(payload)
        for key, value in self._payload.items():
            setattr(self, key, value)

    def model_dump(self):
        return dict(self._payload)


def _payload(response):
    return json.loads(response.body)


def _compat_request(**overrides) -> BacktestRunRequestCompat:
    base = {
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "name": "unit-run",
        "pairs": ["BTC-USD", "ETH-USD"],
    }
    base.update(overrides)
    return BacktestRunRequestCompat(**base)


def _config_request(**overrides) -> BacktestConfigRequest:
    base = {
        "name": "cfg-run",
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "trading_parameters": {"zscore_threshold": 1.5},
        "pairs": ["BTC-USD", "ETH-USD"],
    }
    base.update(overrides)
    return BacktestConfigRequest(**base)


class _FakeDydxClient:
    def __init__(self, markets=None, close_error=None):
        outer = self
        self.close_error = close_error
        self.markets = dict(markets or {})

        class _Node:
            async def close(self):
                if outer.close_error is not None:
                    raise outer.close_error

        class _Markets:
            async def get_perpetual_markets(self):
                return {"markets": dict(outer.markets)}

        self.node = _Node()
        self.indexer = SimpleNamespace(markets=_Markets())


class _HistorySession:
    """Session stub for the backtest-history strategy lookup query chain."""

    def __init__(self, rows=None, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.closed = 0

    def query(self, *args):
        return self

    def order_by(self, *args):
        return self

    def limit(self, count):
        return self

    def all(self):
        if self.error is not None:
            raise self.error
        return list(self.rows)

    def close(self):
        self.closed += 1


class _FakeStrategyStore:
    stored: dict = {}
    error = None
    created_payloads: list = []

    @classmethod
    def get(cls, strategy_id):
        if cls.error is not None:
            raise cls.error
        return cls.stored.get(strategy_id)

    @classmethod
    def create(cls, payload):
        stored = dict(payload)
        stored["id"] = 4242
        cls.created_payloads.append(stored)
        return stored

    @classmethod
    def _reset(cls):
        cls.stored = {}
        cls.error = None
        cls.created_payloads = []


@pytest.fixture(autouse=True)
def _fake_strategy_store(monkeypatch):
    _FakeStrategyStore._reset()
    monkeypatch.setattr(backtests, "InMemoryStrategyStore", _FakeStrategyStore)


class _StubService:
    """Configurable service double for request-scoped route tests."""

    def __init__(self, *, session=None):
        self.session = session
        self.calls = []

    # sync read-side methods used through _run_with_backtest_service
    def list_backtest_runs(self, **kwargs):
        self.calls.append(("list_backtest_runs", kwargs))
        return _ModelDump(
            {"runs": [{"run_id": "run-1", "status": "completed"}], "total": 1}
        )

    def get_backtest_details(self, run_id):
        self.calls.append(("get_backtest_details", run_id))
        return _ModelDump({"run_id": run_id, "name": "det", "status": "completed"})

    def get_backtest_status(self, run_id):
        self.calls.append(("get_backtest_status", run_id))
        return _ModelDump(
            {
                "run_id": run_id,
                "status": "running",
                "progress_pct": 10.0,
                "request_available": True,
            }
        )

    def get_backtest_trades(self, **kwargs):
        self.calls.append(("get_backtest_trades", kwargs))
        return [_ModelDump({"trade_id": "t1", "pnl": 5.0})]

    def get_comprehensive_analytics(self, run_id):
        self.calls.append(("get_comprehensive_analytics", run_id))
        return {
            "run_id": run_id,
            "status": "completed",
            "total_trades": 0,
            "trades": [{"trade_id": "t1"}],
            "daily_pnl": [{"date": "2024-01-02", "pnl": 1.0}],
        }

    def get_position_snapshots(self, **kwargs):
        self.calls.append(("get_position_snapshots", kwargs))
        return [{"timestamp": "2024-01-02T00:00:00Z"}]

    def get_summary_stats(self, days):
        self.calls.append(("get_summary_stats", days))
        return {"total_runs": 7, "days": days}

    def get_runtime_health(self):
        self.calls.append(("get_runtime_health",))
        return {"queue_depth": 0, "active_jobs": 0, "total_runs": 3}

    def compare_backtests(self, run_ids, metrics):
        self.calls.append(("compare_backtests", run_ids, metrics))
        return {"runs": run_ids, "metrics": metrics}

    def get_advanced_performance_metrics(self, run_id, benchmark="BTC-USD"):
        self.calls.append(("get_advanced_performance_metrics", run_id, benchmark))
        return {"run_id": run_id, "sharpe_ratio": 1.2}

    def get_live_progress(self, run_id):
        self.calls.append(("get_live_progress", run_id))
        return {"run_id": run_id, "progress_pct": 33.0}

    def cancel_backtest(self, run_id):
        self.calls.append(("cancel_backtest", run_id))
        return True

    def pause_backtest(self, run_id):
        self.calls.append(("pause_backtest", run_id))
        return {"run_id": run_id, "pause_requested": True}

    def resume_backtest(self, run_id):
        self.calls.append(("resume_backtest", run_id))
        return {"run_id": run_id, "resume_requested": True}

    def delete_backtest(self, run_id):
        self.calls.append(("delete_backtest", run_id))
        return True

    def repair_backtest_request(self, run_id, dry_run=True):
        self.calls.append(("repair_backtest_request", run_id, dry_run))
        return {"run_id": run_id, "dry_run": dry_run}

    def list_interrupted_runs_for_ops(self, limit=50):
        self.calls.append(("list_interrupted_runs_for_ops", limit))
        return {
            "orphaned_in_progress": [{"run_id": "o1"}],
            "interrupted_runs": [{"run_id": "i1"}],
            "orphaned_count": 1,
            "interrupted_count": 1,
        }

    def reconcile_interrupted_runs(self, dry_run=True):
        self.calls.append(("reconcile_interrupted_runs", dry_run))
        return {
            "candidates": [{"run_id": "o1"}],
            "candidate_count": 1,
            "reconciled": [],
            "reconciled_count": 0,
        }

    def update_backtest_metadata(self, run_id, metadata, merge=True):
        self.calls.append(("update_backtest_metadata", run_id, metadata, merge))
        return {"run_id": run_id, "metadata": metadata}

    # async execution-side methods
    async def create_and_run_backtest(self, request, progress_callback=None):
        self.calls.append(("create_and_run_backtest", request))
        return _ModelDump({"run_id": "new-run", "name": "new", "progress_pct": 0.0})

    async def restart_backtest(self, run_id, progress_callback=None):
        self.calls.append(("restart_backtest", run_id))
        return {"new_run_id": "restart-run"}

    async def retry_backtest(self, run_id, progress_callback=None):
        self.calls.append(("retry_backtest", run_id))
        return {"new_run_id": "retry-run"}

    async def validate_against_dydx_data(self, run_id):
        self.calls.append(("validate_against_dydx_data", run_id))
        return {"run_id": run_id, "valid": True}


@pytest.fixture
def stub_service(compat_ns):
    service = _StubService()
    compat_ns["get_backtest_service"] = lambda: service
    return service


# --- provider / env / pure helpers ------------------------------------------


def test_unconfigured_providers_fail_closed(monkeypatch):
    # Pin the unconfigured default: importing the server elsewhere in the
    # suite swaps in a real rate-limit provider via configure_backtest_routes.
    monkeypatch.setattr(
        backtests, "_backtest_rate_limit_provider", backtests._unconfigured_rate_limit
    )
    with pytest.raises(RuntimeError):
        backtests._check_backtest_rate_limit(SimpleNamespace())

    closed = {}

    class _WebSocket:
        async def close(self, code=None, reason=None):
            closed["code"] = code
            closed["reason"] = reason

    result = asyncio.run(backtests._unconfigured_websocket_authorizer(_WebSocket()))
    assert result is False
    assert closed == {"code": 1011, "reason": "Backtest websocket auth unavailable"}


def test_configure_backtest_routes_swaps_providers(monkeypatch):
    seen = []

    def _provider(request):
        seen.append(request)

    async def _authorizer(websocket):
        return True

    # Pre-register originals with monkeypatch so teardown restores them even
    # though configure_backtest_routes assigns the module globals directly.
    monkeypatch.setattr(backtests, "_backtest_rate_limit_provider", _provider)
    monkeypatch.setattr(backtests, "_websocket_authorizer", _authorizer)
    backtests.configure_backtest_routes(
        compatibility_namespace_provider=lambda: {"marker": 1},
        backtest_rate_limit_provider=_provider,
        websocket_authorizer=_authorizer,
    )

    request = SimpleNamespace(request_id="req-1")
    backtests._check_backtest_rate_limit(request)
    assert seen == [request]
    assert backtests._compat("marker", None) == 1


def test_env_reader_variants(monkeypatch):
    for name in (
        "BACKTEST_UNIT_INT",
        "BACKTEST_UNIT_FLOAT",
        "BACKTEST_UNIT_POSITIVE",
    ):
        monkeypatch.delenv(name, raising=False)

    assert backtests._read_non_negative_int_env("BACKTEST_UNIT_INT", 5) == 5
    monkeypatch.setenv("BACKTEST_UNIT_INT", "garbage")
    assert backtests._read_non_negative_int_env("BACKTEST_UNIT_INT", 5) == 5
    monkeypatch.setenv("BACKTEST_UNIT_INT", "-4")
    assert backtests._read_non_negative_int_env("BACKTEST_UNIT_INT", 5) == 0
    monkeypatch.setenv("BACKTEST_UNIT_INT", " 9 ")
    assert backtests._read_non_negative_int_env("BACKTEST_UNIT_INT", 5) == 9

    assert backtests._read_non_negative_float_env("BACKTEST_UNIT_FLOAT", 1.5) == 1.5
    monkeypatch.setenv("BACKTEST_UNIT_FLOAT", "oops")
    assert backtests._read_non_negative_float_env("BACKTEST_UNIT_FLOAT", 1.5) == 1.5
    monkeypatch.setenv("BACKTEST_UNIT_FLOAT", "-2.5")
    assert backtests._read_non_negative_float_env("BACKTEST_UNIT_FLOAT", 1.5) == 0.0
    monkeypatch.setenv("BACKTEST_UNIT_FLOAT", "2.25")
    assert backtests._read_non_negative_float_env("BACKTEST_UNIT_FLOAT", 1.5) == 2.25

    assert backtests._read_positive_int_env("BACKTEST_UNIT_POSITIVE", 3) == 3
    monkeypatch.setenv("BACKTEST_UNIT_POSITIVE", "bad")
    assert backtests._read_positive_int_env("BACKTEST_UNIT_POSITIVE", 3) == 3
    monkeypatch.setenv("BACKTEST_UNIT_POSITIVE", "-8")
    assert backtests._read_positive_int_env("BACKTEST_UNIT_POSITIVE", 3) == 0
    monkeypatch.setenv("BACKTEST_UNIT_POSITIVE", "6")
    assert backtests._read_positive_int_env("BACKTEST_UNIT_POSITIVE", 3) == 6

    monkeypatch.delenv("BACKTEST_UNIT_BOOL", raising=False)
    assert backtests._read_bool_env("BACKTEST_UNIT_BOOL", False) is False
    monkeypatch.setenv("BACKTEST_UNIT_BOOL", "TRUE")
    assert backtests._read_bool_env("BACKTEST_UNIT_BOOL", False) is True
    monkeypatch.setenv("BACKTEST_UNIT_BOOL", "off")
    assert backtests._read_bool_env("BACKTEST_UNIT_BOOL", True) is False


def test_normalize_string_list_and_pair_label_helpers():
    assert backtests._normalize_string_list(None) == []
    assert backtests._normalize_string_list([" btc ", "", "BTC", "eth"]) == [
        "BTC",
        "ETH",
    ]
    assert backtests._markets_from_selected_pair_labels(None) == []
    assert backtests._markets_from_selected_pair_labels(
        ["BTC/ETH", "eth/sol", "sol", "BTC/AVAX"]
    ) == ["BTC", "ETH", "SOL", "AVAX"]
    assert backtests._build_selected_pair_labels(["A", "B", "C"]) == [
        "A/B",
        "A/C",
        "B/C",
    ]


def test_normalize_requested_pair_cap():
    assert backtests._normalize_requested_pair_cap(None) is None
    assert backtests._normalize_requested_pair_cap("nope") is None
    assert backtests._normalize_requested_pair_cap(0) is None
    assert backtests._normalize_requested_pair_cap(-3) is None
    assert backtests._normalize_requested_pair_cap("4") == 4


def test_request_models_normalize_inputs():
    request = _compat_request(pairs=["btc-usd", "BTC-USD", "ETH"], selected_pairs=None)
    assert request.pairs == ["BTC-USD", "ETH"]

    comparison = BacktestComparisonRequest(run_ids=["run-b", "RUN-B", "run-a"])
    assert comparison.run_ids == ["RUN-B", "RUN-A"]

    with pytest.raises(ValueError):
        _compat_request(start_date="2024-05-01", end_date="2024-01-01")


def test_build_backtest_analytics_summary_variants():
    summary = backtests._build_backtest_analytics_summary(
        "run-x",
        {
            "status": "completed",
            "trades": [{"t": 1}, {"t": 2}],
            "daily_pnl": [{"d": 1}],
            "position_snapshots": [{"s": 1}, {"s": 2}],
            "winning_trades": "1",
            "win_rate": "50",
        },
    )
    assert summary["total_trades"] == 2  # falls back to len(trades)
    assert summary["winning_trades"] == 1
    assert summary["win_rate"] == 50.0
    assert summary["daily_pnl_points"] == 1
    assert summary["position_snapshots_points"] == 2
    assert summary["run_id"] == "run-x"

    fallback = backtests._build_backtest_analytics_summary("run-y", None)
    assert fallback["total_trades"] == 0
    assert fallback["win_rate"] == 0.0
    assert fallback["updated_at"]


def test_endpoint_cache_disabled_expiry_and_eviction(monkeypatch):
    monkeypatch.setattr(backtests, "_BACKTEST_ENDPOINT_CACHE_TTL_SECONDS", 0)
    backtests._cache_set("k", "v")
    assert backtests._cache_get("k") is None

    monkeypatch.setattr(backtests, "_BACKTEST_ENDPOINT_CACHE_TTL_SECONDS", 60)
    backtests._cache_set("k", "v")
    assert backtests._cache_get("k") == "v"

    # Expired entries are dropped on read.
    backtests._backtest_endpoint_cache["stale"] = {
        "value": 1,
        "expires_at": 0.0,
        "updated_at": 0.0,
    }
    assert backtests._cache_get("stale") is None
    assert "stale" not in backtests._backtest_endpoint_cache

    # Overflow first evicts expired keys, then the oldest live ones.
    monkeypatch.setattr(backtests, "_BACKTEST_ENDPOINT_CACHE_MAX_ENTRIES", 2)
    backtests._backtest_endpoint_cache.clear()
    now = time.monotonic()
    backtests._backtest_endpoint_cache["expired"] = {
        "value": 1,
        "expires_at": now - 5,
        "updated_at": now - 5,
    }
    backtests._cache_set("live", "v")
    assert set(backtests._backtest_endpoint_cache) == {"expired", "live"}

    backtests._cache_set("newer", "n")  # overflow evicts the expired entry first
    assert "expired" not in backtests._backtest_endpoint_cache

    backtests._cache_set("newest", "x")  # overflow now evicts the oldest live key
    assert "live" not in backtests._backtest_endpoint_cache
    assert backtests._cache_get("newest") == "x"
    assert backtests._cache_get("newer") == "n"


# --- market resolution --------------------------------------------------------


def test_resolve_backtest_markets_matrix(monkeypatch):
    def _client(markets=None, close_error=None):
        return _FakeDydxClient(markets=markets, close_error=close_error)

    # Too few markets before any client call.
    with pytest.raises(ValueError, match="SELECTED_PAIRS_MISSING"):
        asyncio.run(backtests._resolve_backtest_markets(["BTC-USD"], None, 0))

    async def _connect_ok():
        return _client(markets={"BTC-USD": {}, "ETH-USD": {}, "SOL-USD": {}})

    monkeypatch.setattr(backtests, "connect_dydx", _connect_ok)
    resolved = asyncio.run(
        backtests._resolve_backtest_markets(
            None, ["BTC-USD/ETH-USD", "ETH-USD/SOL-USD"], 0
        )
    )
    assert resolved == ["BTC-USD", "ETH-USD", "SOL-USD"]

    # Cap slices explicit markets only.
    capped = asyncio.run(
        backtests._resolve_backtest_markets(["BTC-USD", "ETH-USD", "SOL-USD"], None, 2)
    )
    assert capped == ["BTC-USD", "ETH-USD"]

    with pytest.raises(ValueError, match="SELECTED_PAIRS_INVALID"):
        asyncio.run(backtests._resolve_backtest_markets(["BTC-USD", "NOPE-USD"], 0, 0))

    async def _connect_empty():
        return _client(markets={})

    monkeypatch.setattr(backtests, "connect_dydx", _connect_empty)
    with pytest.raises(ValueError, match="MARKET_RESOLUTION_FAILED"):
        asyncio.run(
            backtests._resolve_backtest_markets(["BTC-USD", "ETH-USD"], None, 0)
        )

    async def _connect_boom():
        raise RuntimeError(" indexer unreachable ")

    monkeypatch.setattr(backtests, "connect_dydx", _connect_boom)
    with pytest.raises(ValueError, match="MARKET_RESOLUTION_FAILED"):
        asyncio.run(
            backtests._resolve_backtest_markets(["BTC-USD", "ETH-USD"], None, 0)
        )

    # A failing node.close() is swallowed after a successful resolution.
    async def _connect_close_error():
        return _client(
            markets={"BTC-USD": {}, "ETH-USD": {}}, close_error=RuntimeError("close")
        )

    monkeypatch.setattr(backtests, "connect_dydx", _connect_close_error)
    resolved = asyncio.run(
        backtests._resolve_backtest_markets(["BTC-USD", "ETH-USD"], None, 0)
    )
    assert resolved == ["BTC-USD", "ETH-USD"]


# --- request building ---------------------------------------------------------


def test_manual_backtest_request_defaults_and_resolution_mirroring():
    request = _compat_request(
        trading_parameters={"candle_resolution": "4HOUR", "zscore_threshold": 2.0}
    )
    built = backtests._manual_backtest_request(request, ["BTC-USD"], ["BTC/ETH"])
    assert built.name == "unit-run"
    assert built.trading_parameters["resolution"] == "4HOUR"
    assert built.pair_selection_mode == "liquidity"
    assert built.pairs == ["BTC-USD"]
    assert built.selected_pairs == ["BTC/ETH"]

    mirrored = backtests._manual_backtest_request(
        _compat_request(trading_parameters={"resolution": "1DAY"}),
        ["BTC-USD"],
        ["BTC/ETH"],
    )
    assert mirrored.trading_parameters["candle_resolution"] == "1DAY"

    defaults = backtests._manual_backtest_request(
        _compat_request(), ["BTC-USD"], ["BTC/ETH"]
    )
    assert defaults.trading_parameters["zscore_threshold"] == 1.5
    assert defaults.description == "Manual backtest run"


def test_strategy_to_backtest_request_merge_and_balance_fallback():
    strategy = {
        "name": "Alpha",
        "description": "desc",
        "starting_balance": 2500.0,
        "zscore_threshold": 2.5,
        "resolution": "4HOUR",
    }
    built = backtests._strategy_to_backtest_request(
        strategy, _compat_request(initial_balance=500.0), ["BTC-USD"], ["BTC/ETH"]
    )
    assert built.initial_balance == 500.0
    assert built.trading_parameters["zscore_threshold"] == 2.5
    assert built.trading_parameters["candle_resolution"] == "4HOUR"
    assert built.strategy_payload_snapshot["name"] == "Alpha"
    assert built.name == "unit-run"

    # Bypass pydantic validation to exercise the zero-balance fallback.
    zero_balance = BacktestRunRequestCompat.model_construct(
        start_date="2024-01-01",
        end_date="2024-03-31",
        initial_balance=0.0,
        max_pairs=0,
    )
    fallback = backtests._strategy_to_backtest_request(
        strategy, zero_balance, ["BTC-USD"], ["BTC/ETH"]
    )
    assert fallback.initial_balance == 2500.0
    assert fallback.name == "Alpha Backtest"


def test_resolve_strategy_backtest_request_matrix(monkeypatch):
    # One-off without payload or trading parameters -> 422.
    response = backtests._resolve_strategy_backtest_request(
        _compat_request(pairs=["BTC-USD", "ETH-USD"]), ["BTC-USD"], ["BTC/ETH"], "/x"
    )
    assert response.status_code == 422
    assert _payload(response)["data"]["error"] == "STRATEGY_PAYLOAD_MISSING"

    # One-off with trading parameters -> manual request.
    manual = backtests._resolve_strategy_backtest_request(
        _compat_request(trading_parameters={"zscore_threshold": 2.0}),
        ["BTC-USD"],
        ["BTC/ETH"],
        "/x",
    )
    assert isinstance(manual, BacktestConfigRequest)

    # Store hit wins first; request balance (>0) overrides strategy default.
    _FakeStrategyStore.stored[7] = {
        "id": 7,
        "name": "Stored",
        "starting_balance": 1500.0,
        "zscore_threshold": 2.5,
    }
    resolved = backtests._resolve_strategy_backtest_request(
        _compat_request(strategy_id=7), ["BTC-USD"], ["BTC/ETH"], "/x"
    )
    assert isinstance(resolved, BacktestConfigRequest)
    assert resolved.initial_balance == 1000.0
    assert resolved.trading_parameters["zscore_threshold"] == 2.5

    # History fallback scans persisted request payloads.
    _FakeStrategyStore.stored.clear()
    session = _HistorySession(
        rows=[
            ("corrupt-payload", "run-bad"),
            (
                {
                    "strategy_payload_snapshot": {"id": "abc", "name": "Broken"},
                    "strategy_id": 7,
                },
                "run-typeerror",
            ),
            (
                {
                    "strategy_payload_snapshot": {"id": 7, "name": "Historical"},
                    "strategy_id": 7,
                },
                "run-good",
            ),
        ]
    )
    monkeypatch.setattr(backtests.db, "get_session", lambda: session)
    resolved = backtests._resolve_strategy_backtest_request(
        _compat_request(strategy_id=7), ["BTC-USD"], ["BTC/ETH"], "/x"
    )
    assert isinstance(resolved, BacktestConfigRequest)
    assert resolved.strategy_payload_snapshot["name"] == "Historical"
    assert session.closed == 1

    # History query failure degrades to request snapshot fallback.
    broken_session = _HistorySession(error=RuntimeError("db down"))
    monkeypatch.setattr(backtests.db, "get_session", lambda: broken_session)
    fallback = backtests._resolve_strategy_backtest_request(
        _compat_request(strategy_id=9, strategy_payload_snapshot={"name": "Req"}),
        ["BTC-USD"],
        ["BTC/ETH"],
        "/x",
    )
    assert isinstance(fallback, BacktestConfigRequest)
    assert fallback.strategy_payload_snapshot["name"] == "Req"

    # Store lookup raising still falls back to the request snapshot.
    _FakeStrategyStore.error = RuntimeError("store exploded")
    fallback_after_error = backtests._resolve_strategy_backtest_request(
        _compat_request(strategy_id=9, strategy_payload_snapshot={"name": "Req"}),
        ["BTC-USD"],
        ["BTC/ETH"],
        "/x",
    )
    assert isinstance(fallback_after_error, BacktestConfigRequest)
    assert fallback_after_error.strategy_payload_snapshot["name"] == "Req"
    _FakeStrategyStore.error = None

    # Nothing resolvable -> 404.
    empty_session = _HistorySession(rows=[])
    monkeypatch.setattr(backtests.db, "get_session", lambda: empty_session)
    missing = backtests._resolve_strategy_backtest_request(
        _compat_request(strategy_id=13), ["BTC-USD"], ["BTC/ETH"], "/x"
    )
    assert missing.status_code == 404
    assert _payload(missing)["data"]["error"] == "STRATEGY_NOT_FOUND"

    # Strict production mode disables the request-snapshot fallback.
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv(
        "BACKTEST_DISABLE_REQUEST_SNAPSHOT_FALLBACK_IN_PRODUCTION", "true"
    )
    strict = backtests._resolve_strategy_backtest_request(
        _compat_request(strategy_id=13, strategy_payload_snapshot={"name": "Req"}),
        ["BTC-USD"],
        ["BTC/ETH"],
        "/x",
    )
    assert strict.status_code == 404


# --- service scope machinery ---------------------------------------------------


class _CloseRecorder:
    def __init__(self):
        self.closed = 0
        self.error = None

    def close(self):
        self.closed += 1
        if self.error is not None:
            raise self.error


def test_backtest_service_scope_and_close_variants(compat_ns):
    session = _CloseRecorder()
    service = _StubService(session=session)
    compat_ns["get_backtest_service"] = lambda: service

    with backtests.backtest_service_scope() as scoped:
        assert scoped is service
    assert session.closed == 1

    # Falls back to repository.session when service.session is absent.
    repo_session = _CloseRecorder()
    repo_service = SimpleNamespace(repository=SimpleNamespace(session=repo_session))
    compat_ns["get_backtest_service"] = lambda: repo_service
    backtests.close_backtest_service(repo_service)
    assert repo_session.closed == 1

    # Nothing to close -> no-op.
    backtests.close_backtest_service(SimpleNamespace())
    backtests.close_backtest_service(None)

    # Close failures are logged, not raised.
    failing = _CloseRecorder()
    failing.error = RuntimeError("close failed")
    backtests.close_backtest_service(SimpleNamespace(session=failing))


def test_run_with_backtest_service_closes_on_operation_error(compat_ns):
    session = _CloseRecorder()
    service = _StubService(session=session)
    compat_ns["get_backtest_service"] = lambda: service

    def _explode(svc):
        raise RuntimeError("operation failed")

    with pytest.raises(RuntimeError, match="operation failed"):
        backtests._run_with_backtest_service(_explode)
    assert session.closed == 1

    result = backtests._run_with_backtest_service(lambda svc: "ok")
    assert result == "ok"


def test_get_backtest_service_wires_repository_session(monkeypatch):
    sessions = [_CloseRecorder()]
    created = {}

    class _Repo:
        def __init__(self, session):
            created["session"] = session

    class _Service:
        def __init__(self, repository):
            created["repository"] = repository

    monkeypatch.setattr(backtests.db, "get_session", lambda: sessions[0])
    monkeypatch.setattr(backtests, "BacktestRepository", _Repo)
    monkeypatch.setattr(backtests, "BacktestService", _Service)

    service = backtests.get_backtest_service()

    assert isinstance(service, _Service)
    assert created["session"] is sessions[0]
    assert getattr(created["repository"], "db") is sessions[0]


def test_check_backtest_admission_branches(monkeypatch):
    plain = SimpleNamespace()
    assert backtests._check_backtest_admission(plain) is None  # no health method

    healthy = SimpleNamespace(
        get_runtime_health=lambda: {"queue_depth": 0, "active_jobs": 0}
    )
    assert backtests._check_backtest_admission(healthy) is None

    monkeypatch.setenv("BACKTEST_MAX_ACTIVE_RUNS_GLOBAL", "2")
    busy = SimpleNamespace(
        get_runtime_health=lambda: {"queue_depth": 2, "active_jobs": 0}
    )
    blocked = backtests._check_backtest_admission(busy)
    assert blocked is not None and blocked.status_code == 429
    assert _payload(blocked)["data"]["reason"] == "global_active_limit_reached"
    assert blocked.headers["Retry-After"] == "15"

    monkeypatch.setenv("BACKTEST_MAX_ACTIVE_RUNS_GLOBAL", "0")
    monkeypatch.setenv("BACKTEST_MAX_QUEUE_DEPTH", "1")
    queued = SimpleNamespace(
        get_runtime_health=lambda: {"queue_depth": 1, "active_jobs": 0}
    )
    blocked = backtests._check_backtest_admission(queued)
    assert _payload(blocked)["data"]["reason"] == "queue_depth_limit_reached"

    monkeypatch.setenv("BACKTEST_MAX_QUEUE_DEPTH", "0")
    monkeypatch.setenv("BACKTEST_MAX_IN_PROCESS_BACKTEST_JOBS", "3")
    in_process = SimpleNamespace(
        get_runtime_health=lambda: {"queue_depth": 0, "active_jobs": 3}
    )
    blocked = backtests._check_backtest_admission(in_process)
    assert _payload(blocked)["data"]["reason"] == "in_process_limit_reached"
    assert "temporarily saturated. " in _payload(blocked)["message"]

    monkeypatch.setenv("BACKTEST_MAX_IN_PROCESS_BACKTEST_JOBS", "0")
    overloaded = SimpleNamespace(
        get_runtime_health=lambda: {"persistence_pool_overloaded": True}
    )
    blocked = backtests._check_backtest_admission(overloaded)
    assert _payload(blocked)["data"]["reason"] == "persistence_pool_overload"
    assert "runtime overload" in _payload(blocked)["message"]

    monkeypatch.setenv("BACKTEST_BLOCK_ON_PERSISTENCE_OVERLOAD", "false")
    assert backtests._check_backtest_admission(overloaded) is None


def test_broadcast_backtest_progress_publishes_and_survives_failures(monkeypatch):
    broadcasts = []

    async def _record(channel, message):
        broadcasts.append((channel, message))

    monkeypatch.setattr(backtests.manager, "broadcast_to_bot", _record)
    asyncio.run(backtests._broadcast_backtest_progress("run-1", 55.0, "BTC/ETH", 120))
    assert len(broadcasts) == 2
    assert broadcasts[0][0] == "backtest-run-1"
    assert broadcasts[0][1]["progress"] == 55.0
    assert broadcasts[1][1]["message"] == "Scanning: BTC/ETH"

    asyncio.run(backtests._broadcast_backtest_progress("run-1", 100.0, "complete", 0))
    assert broadcasts[-1][1]["message"] == "Backtest completed"

    async def _boom(channel, message):
        raise RuntimeError("ws down")

    monkeypatch.setattr(backtests.manager, "broadcast_to_bot", _boom)
    asyncio.run(backtests._broadcast_backtest_progress("run-1", 1.0, "X/Y", 5))


def test_websocket_alias_adapter_rejects_unauthorized(monkeypatch):
    async def _deny(websocket):
        return False

    monkeypatch.setattr(backtests, "_websocket_authorizer", _deny)

    async def _unexpected(websocket, channel):
        raise AssertionError("must not delegate when unauthorized")

    monkeypatch.setattr(backtests.WebSocketServer, "handle_connection", _unexpected)
    asyncio.run(backtests.websocket_backtest_progress_alias(SimpleNamespace(), "run-1"))


def test_maybe_awaitable_passes_sync_and_awaits_async():
    assert asyncio.run(backtests._maybe_awaitable(7)) == 7

    async def _value():
        return 8

    assert asyncio.run(backtests._maybe_awaitable(_value())) == 8


# --- create / run routes -------------------------------------------------------


def test_create_backtest_config_request_short_circuit(stub_service):
    request = _config_request()
    response = asyncio.run(backtests.create_backtest(request, current_user=object()))
    assert response.status_code == 200
    body = _payload(response)
    assert body["success"] is True
    assert body["data"]["run_id"] == "new-run"
    assert stub_service.calls == [
        ("get_runtime_health",),
        ("create_and_run_backtest", request),
    ]


def test_create_backtest_compat_resolves_markets_and_strategy(compat_ns, stub_service):
    async def _markets(pairs, selected, max_pairs):
        return ["BTC-USD", "ETH-USD"]

    resolved_request = _config_request(name="resolved")

    def _resolve(request, pairs, labels, endpoint):
        assert endpoint == "/api/v1/backtests"
        assert pairs == ["BTC-USD", "ETH-USD"]
        assert labels == ["BTC-USD/ETH-USD"]
        return resolved_request

    compat_ns["_resolve_backtest_markets"] = _markets
    compat_ns["_resolve_strategy_backtest_request"] = _resolve

    response = asyncio.run(
        backtests.create_backtest(
            _compat_request(pairs=["BTC-USD", "ETH-USD"]),
            current_user=object(),
        )
    )
    assert response.status_code == 200
    assert stub_service.calls[0] == ("get_runtime_health",)
    assert stub_service.calls[1] == ("create_and_run_backtest", resolved_request)


def test_create_backtest_compat_returns_resolution_error(compat_ns, stub_service):
    async def _markets(pairs, selected, max_pairs):
        return ["BTC-USD", "ETH-USD"]

    def _resolve(request, pairs, labels, endpoint):
        return backtests.api_response(success=False, message="nope", status_code=404)

    compat_ns["_resolve_backtest_markets"] = _markets
    compat_ns["_resolve_strategy_backtest_request"] = _resolve

    response = asyncio.run(
        backtests.create_backtest(_compat_request(), current_user=object())
    )
    assert response.status_code == 404
    assert stub_service.calls == []


def test_create_backtest_value_error_mapping(compat_ns, stub_service):
    async def _invalid(pairs, selected, max_pairs):
        raise ValueError("SELECTED_PAIRS_INVALID: bad pairs")

    async def _generic(pairs, selected, max_pairs):
        raise ValueError("WEIRD_CODE: something else")

    compat_ns["_resolve_backtest_markets"] = _invalid
    response = asyncio.run(
        backtests.create_backtest(_compat_request(), current_user=object())
    )
    assert response.status_code == 422
    assert _payload(response)["data"]["error"] == "SELECTED_PAIRS_INVALID"

    compat_ns["_resolve_backtest_markets"] = _generic
    response = asyncio.run(
        backtests.create_backtest(_compat_request(), current_user=object())
    )
    assert response.status_code == 400
    assert _payload(response)["data"]["error"] == "WEIRD_CODE"


def test_create_backtest_blocked_by_admission(monkeypatch, compat_ns):
    monkeypatch.setenv("BACKTEST_MAX_ACTIVE_RUNS_GLOBAL", "1")
    service = SimpleNamespace(
        get_runtime_health=lambda: {"queue_depth": 1, "active_jobs": 0}
    )
    compat_ns["get_backtest_service"] = lambda: service

    response = asyncio.run(
        backtests.create_backtest(_config_request(), current_user=object())
    )
    assert response.status_code == 429
    assert _payload(response)["data"]["cannot_accept_new_runs"] is True


def test_run_backtest_compat_success_and_errors(compat_ns, stub_service):
    async def _markets(pairs, selected, max_pairs):
        return ["BTC-USD", "ETH-USD"]

    def _resolve(request, pairs, labels, endpoint):
        return _config_request(name="compat-run")

    compat_ns["_resolve_backtest_markets"] = _markets
    compat_ns["_resolve_strategy_backtest_request"] = _resolve

    response = asyncio.run(
        backtests.run_backtest_compat(
            _compat_request(strategy_id=4), current_user=object()
        )
    )
    assert response.status_code == 200
    body = _payload(response)
    assert body["data"]["progress"] == 0.0
    assert body["data"]["count"] == 1

    async def _invalid(pairs, selected, max_pairs):
        raise ValueError("MARKET_RESOLUTION_FAILED: down")

    compat_ns["_resolve_backtest_markets"] = _invalid
    response = asyncio.run(
        backtests.run_backtest_compat(_compat_request(), current_user=object())
    )
    assert response.status_code == 422

    class _ExplodingService(_StubService):
        async def create_and_run_backtest(self, request, progress_callback=None):
            raise RuntimeError("worker exploded")

    compat_ns["_resolve_backtest_markets"] = _markets
    compat_ns["get_backtest_service"] = lambda: _ExplodingService()
    response = asyncio.run(
        backtests.run_backtest_compat(_compat_request(), current_user=object())
    )
    assert response.status_code == 500
    assert _payload(response)["data"]["error"] == "BOT_EXECUTION_FAILED"


# --- read routes ----------------------------------------------------------------


def test_list_backtests_route_and_error_path(compat_ns, stub_service):
    response = asyncio.run(backtests.list_backtests(current_user=object()))
    assert response.status_code == 200
    body = _payload(response)
    assert body["data"]["backtests"][0]["run_id"] == "run-1"
    assert body["data"]["count"] == 1

    def _boom(limit, offset, status, days):
        raise RuntimeError("db down")

    compat_ns["_list_backtests_sync"] = _boom
    response = asyncio.run(backtests.list_backtests(current_user=object()))
    assert response.status_code == 500


def test_interrupted_routes_and_admin_aliases(compat_ns, stub_service):
    response = asyncio.run(backtests.list_interrupted_backtests(current_user=object()))
    assert response.status_code == 200
    assert _payload(response)["data"]["count"] == 2

    admin_response = asyncio.run(
        backtests.list_interrupted_backtests_admin(current_user=object())
    )
    assert admin_response.status_code == 200

    reconciled = asyncio.run(
        backtests.reconcile_interrupted_backtests(dry_run=False, current_user=object())
    )
    assert reconciled.status_code == 200
    assert "reconciliation completed" in _payload(reconciled)["message"]

    dry = asyncio.run(
        backtests.reconcile_interrupted_backtests_admin(current_user=object())
    )
    assert "Dry-run completed" in _payload(dry)["message"]

    def _boom(limit):
        raise RuntimeError("db down")

    compat_ns["_list_interrupted_runs_for_ops_sync"] = _boom
    response = asyncio.run(backtests.list_interrupted_backtests(current_user=object()))
    assert response.status_code == 500


def test_repair_request_routes(compat_ns, stub_service):
    response = asyncio.run(
        backtests.repair_backtest_request_admin(
            "run-1", dry_run=True, current_user=object()
        )
    )
    assert response.status_code == 200
    assert "Dry-run completed" in _payload(response)["message"]

    repaired = asyncio.run(
        backtests._repair_backtest_request_response("run-1", dry_run=False)
    )
    assert "repaired" in _payload(repaired)["message"]

    class _MissingService(_StubService):
        def repair_backtest_request(self, run_id, dry_run=True):
            return None

    compat_ns["get_backtest_service"] = lambda: _MissingService()
    missing = asyncio.run(
        backtests.repair_backtest_request_admin("gone", current_user=object())
    )
    assert missing.status_code == 404


def test_details_status_and_websocket_metrics_routes(monkeypatch, stub_service):
    response = asyncio.run(
        backtests.get_backtest_details("run-1", current_user=object())
    )
    assert response.status_code == 200
    assert _payload(response)["data"]["run_id"] == "run-1"

    monkeypatch.setattr(backtests, "_get_backtest_details_sync", lambda run_id: None)
    missing = asyncio.run(backtests.get_backtest_details("gone", current_user=object()))
    assert missing.status_code == 404

    status = asyncio.run(backtests.get_backtest_status("run-1", current_user=object()))
    body = _payload(status)
    assert body["data"]["progress"] == 10.0
    assert body["data"]["websocket_send_metrics"]["run_id"] == "run-1"

    monkeypatch.setattr(backtests, "_get_backtest_status_sync", lambda run_id: None)
    missing_status = asyncio.run(
        backtests.get_backtest_status("gone", current_user=object())
    )
    assert missing_status.status_code == 404

    monkeypatch.setattr(
        backtests,
        "_get_backtest_status_sync",
        lambda run_id: SimpleNamespace(status="running"),
    )
    metrics = asyncio.run(
        backtests.get_backtest_websocket_metrics("run-1", current_user=object())
    )
    assert _payload(metrics)["data"]["status"] == "running"
    assert "metrics" in _payload(metrics)["data"]

    monkeypatch.setattr(backtests, "_get_backtest_status_sync", lambda run_id: None)
    missing_metrics = asyncio.run(
        backtests.get_backtest_websocket_metrics("gone", current_user=object())
    )
    assert missing_metrics.status_code == 404


def test_metadata_and_create_strategy_routes(compat_ns):
    class _MetadataService(_StubService):
        def __init__(self, result):
            super().__init__()
            self.result = result

        def update_backtest_metadata(self, run_id, metadata, merge=True):
            return self.result

        def get_backtest_details(self, run_id):
            return {"run_id": run_id} if self.result else None

    service = _MetadataService({"merged": True})
    compat_ns["get_backtest_service"] = lambda: service
    response = asyncio.run(
        backtests.update_backtest_metadata(
            "run-1",
            backtests.BacktestMetadataRequest(metadata={"a": 1}),
            current_user=object(),
        )
    )
    assert response.status_code == 200
    assert _payload(response)["data"] == {"merged": True}

    missing_service = _MetadataService(None)
    compat_ns["get_backtest_service"] = lambda: missing_service
    missing = asyncio.run(
        backtests.update_backtest_metadata(
            "gone",
            backtests.BacktestMetadataRequest(metadata={"a": 1}),
            current_user=object(),
        )
    )
    assert missing.status_code == 404

    strategy_missing = asyncio.run(
        backtests.create_strategy_from_backtest(
            "gone",
            backtests.BacktestCreateStrategyRequest(name="S"),
            current_user=object(),
        )
    )
    assert strategy_missing.status_code == 404

    compat_ns["get_backtest_service"] = lambda: service
    created = asyncio.run(
        backtests.create_strategy_from_backtest(
            "run-1",
            backtests.BacktestCreateStrategyRequest(
                name="FromBacktest", description="d", config={"zscore_threshold": 2.0}
            ),
            current_user=object(),
        )
    )
    body = _payload(created)
    assert body["data"]["id"] == 4242
    assert body["data"]["is_public"] is False
    assert body["data"]["source_backtest_run_id"] == "run-1"
    assert _FakeStrategyStore.created_payloads[0]["zscore_threshold"] == 2.0


def test_trades_route_caches_and_error_path(monkeypatch, stub_service):
    response = asyncio.run(
        backtests.get_backtest_trades("run-t", current_user=object())
    )
    assert response.status_code == 200
    body = _payload(response)
    assert body["data"]["total"] == 1
    assert body["data"]["trades"][0]["trade_id"] == "t1"

    # Second identical call is served from cache without hitting the seam.
    calls = list(stub_service.calls)
    asyncio.run(backtests.get_backtest_trades("run-t", current_user=object()))
    assert stub_service.calls == calls

    def _boom(run_id, limit, offset, winning_only):
        raise RuntimeError("db down")

    monkeypatch.setattr(backtests, "_get_backtest_trades_sync", _boom)
    failed = asyncio.run(backtests.get_backtest_trades("run-z", current_user=object()))
    assert failed.status_code == 500


def test_logs_route_variants(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("bot_states")

    missing = asyncio.run(
        backtests.get_backtest_logs("missing-run", current_user=object())
    )
    assert missing.status_code == 404

    log_path = os.path.join("bot_states", "backtest_run-l.log")
    with open(log_path, "w", encoding="utf-8") as handle:
        for index in range(5):
            handle.write(f"line-{index}\n")

    response = asyncio.run(
        backtests.get_backtest_logs("run-l", tail=2, current_user=object())
    )
    body = _payload(response)
    assert body["data"]["logs"] == ["line-3", "line-4"]
    assert body["data"]["tail"] == 2

    # A directory where the log belongs fails closed with a 500 envelope.
    os.remove(log_path)
    os.makedirs(log_path)
    failed = asyncio.run(backtests.get_backtest_logs("run-l", current_user=object()))
    assert failed.status_code == 500


# --- control routes --------------------------------------------------------------


def test_cancel_pause_resume_delete_routes(compat_ns, stub_service):
    cancelled = asyncio.run(backtests.cancel_backtest("run-1", current_user=object()))
    assert cancelled.status_code == 200
    assert "cancelled" in _payload(cancelled)["message"]

    paused = asyncio.run(backtests.pause_backtest("run-1", current_user=object()))
    assert _payload(paused)["data"]["pause_requested"] is True

    resumed = asyncio.run(backtests.resume_backtest("run-1", current_user=object()))
    assert _payload(resumed)["data"]["resume_requested"] is True

    deleted = asyncio.run(backtests.delete_backtest("run-1", current_user=object()))
    assert deleted.status_code == 200

    class _FailingService(_StubService):
        def cancel_backtest(self, run_id):
            return False

        def pause_backtest(self, run_id):
            return None

        def resume_backtest(self, run_id):
            return None

        def delete_backtest(self, run_id):
            return False

    compat_ns["get_backtest_service"] = lambda: _FailingService()
    assert (
        asyncio.run(backtests.cancel_backtest("x", current_user=object())).status_code
        == 404
    )
    assert (
        asyncio.run(backtests.pause_backtest("x", current_user=object())).status_code
        == 404
    )
    assert (
        asyncio.run(backtests.resume_backtest("x", current_user=object())).status_code
        == 404
    )
    assert (
        asyncio.run(backtests.delete_backtest("x", current_user=object())).status_code
        == 404
    )


def test_restart_route_matrix(compat_ns, stub_service):
    ok = asyncio.run(backtests.restart_backtest("run-1", current_user=object()))
    assert ok.status_code == 200
    assert "restart-run" in _payload(ok)["message"]

    compat_ns["_get_backtest_status_sync"] = lambda run_id: None
    missing = asyncio.run(backtests.restart_backtest("gone", current_user=object()))
    assert missing.status_code == 404

    compat_ns["_get_backtest_status_sync"] = lambda run_id: SimpleNamespace(
        request_available=False
    )
    conflict = asyncio.run(backtests.restart_backtest("run-1", current_user=object()))
    assert conflict.status_code == 409
    assert _payload(conflict)["data"]["error"] == "missing_original_request_payload"

    compat_ns["_get_backtest_status_sync"] = lambda run_id: SimpleNamespace(
        request_available=True
    )

    class _NoRestartService(_StubService):
        async def restart_backtest(self, run_id, progress_callback=None):
            return None

    compat_ns["get_backtest_service"] = lambda: _NoRestartService()
    unavailable = asyncio.run(
        backtests.restart_backtest("run-1", current_user=object())
    )
    assert unavailable.status_code == 404

    class _ExplodingService(_StubService):
        async def restart_backtest(self, run_id, progress_callback=None):
            raise RuntimeError("nope")

    compat_ns["get_backtest_service"] = lambda: _ExplodingService()
    failed = asyncio.run(backtests.restart_backtest("run-1", current_user=object()))
    assert failed.status_code == 500


def test_retry_route_matrix(compat_ns, stub_service):
    ok = asyncio.run(backtests.retry_backtest("run-1", current_user=object()))
    assert ok.status_code == 200
    assert "retry-run" in _payload(ok)["message"]

    compat_ns["_get_backtest_status_sync"] = lambda run_id: None
    missing = asyncio.run(backtests.retry_backtest("gone", current_user=object()))
    assert missing.status_code == 404

    compat_ns["_get_backtest_status_sync"] = lambda run_id: SimpleNamespace(
        request_available=False
    )
    conflict = asyncio.run(backtests.retry_backtest("run-1", current_user=object()))
    assert conflict.status_code == 409

    compat_ns["_get_backtest_status_sync"] = lambda run_id: SimpleNamespace(
        request_available=True
    )

    class _NoRetryService(_StubService):
        async def retry_backtest(self, run_id, progress_callback=None):
            return None

    compat_ns["get_backtest_service"] = lambda: _NoRetryService()
    unavailable = asyncio.run(backtests.retry_backtest("run-1", current_user=object()))
    assert unavailable.status_code == 404

    class _ExplodingService(_StubService):
        async def retry_backtest(self, run_id, progress_callback=None):
            raise RuntimeError("nope")

    compat_ns["get_backtest_service"] = lambda: _ExplodingService()
    failed = asyncio.run(backtests.retry_backtest("run-1", current_user=object()))
    assert failed.status_code == 500


# --- analytics / stats routes ------------------------------------------------------


def test_summary_stats_route(monkeypatch, stub_service):
    response = asyncio.run(
        backtests.get_backtest_summary_stats(days=7, current_user=object())
    )
    assert response.status_code == 200
    assert _payload(response)["data"] == {"total_runs": 7, "days": 7}


def test_analytics_routes_with_cache(monkeypatch, stub_service):
    full = asyncio.run(backtests.get_backtest_analytics("run-a", current_user=object()))
    assert full.status_code == 200
    assert _payload(full)["data"]["run_id"] == "run-a"

    # Summary route reuses the full-analytics cache populated above.
    summary = asyncio.run(
        backtests.get_backtest_analytics_summary("run-a", current_user=object())
    )
    body = _payload(summary)
    assert body["data"]["run_id"] == "run-a"
    assert body["data"]["total_trades"] == 1
    assert body["data"]["daily_pnl_points"] == 1

    monkeypatch.setattr(backtests, "_get_backtest_analytics_sync", lambda run_id: None)
    missing = asyncio.run(
        backtests.get_backtest_analytics("gone", current_user=object())
    )
    assert missing.status_code == 404

    missing_summary = asyncio.run(
        backtests.get_backtest_analytics_summary("gone2", current_user=object())
    )
    assert missing_summary.status_code == 404

    def _boom(run_id):
        raise RuntimeError("db down")

    monkeypatch.setattr(backtests, "_get_backtest_analytics_sync", _boom)
    failed = asyncio.run(
        backtests.get_backtest_analytics("boom", current_user=object())
    )
    assert failed.status_code == 500

    backtests._backtest_endpoint_cache.clear()
    monkeypatch.setattr(backtests, "_get_backtest_analytics_sync", _boom)
    failed_summary = asyncio.run(
        backtests.get_backtest_analytics_summary("boom2", current_user=object())
    )
    assert failed_summary.status_code == 500


def test_position_snapshots_compare_and_sync_health_routes(monkeypatch, stub_service):
    snapshots = asyncio.run(
        backtests.get_position_snapshots("run-1", current_user=object())
    )
    body = _payload(snapshots)
    assert body["data"]["snapshots"] == body["data"]["position_snapshots"]
    assert body["data"]["total"] == 1

    compared = asyncio.run(
        backtests.compare_backtests(
            BacktestComparisonRequest(run_ids=["run-1", "run-2"]),
            current_user=object(),
        )
    )
    assert _payload(compared)["data"]["metrics"] == [
        "total_return_pct",
        "sharpe_ratio",
        "win_rate",
    ]

    metrics_only = asyncio.run(
        backtests.backtest_sync_health(metrics_only=True, current_user=object())
    )
    assert _payload(metrics_only)["data"]["strategy_resolution_metrics"]["counts"]

    full_health = asyncio.run(backtests.backtest_sync_health(current_user=object()))
    assert _payload(full_health)["data"]["queue_depth"] == 0

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(backtests, "_get_backtest_runtime_health_sync", _boom)
    failed = asyncio.run(backtests.backtest_sync_health(current_user=object()))
    assert failed.status_code == 500

    monkeypatch.setattr(backtests, "_get_position_snapshots_sync", _boom)
    failed_snapshots = asyncio.run(
        backtests.get_position_snapshots("boom", current_user=object())
    )
    assert failed_snapshots.status_code == 500

    monkeypatch.setattr(backtests, "_compare_backtests_sync", _boom)
    failed_compare = asyncio.run(
        backtests.compare_backtests(
            BacktestComparisonRequest(run_ids=["a", "b"]), current_user=object()
        )
    )
    assert failed_compare.status_code == 500


def test_dydx_validation_route(compat_ns, stub_service):
    validated = asyncio.run(
        backtests.validate_against_dydx_data("run-1", current_user=object())
    )
    assert validated.status_code == 200
    assert _payload(validated)["data"]["valid"] is True

    class _InvalidService(_StubService):
        async def validate_against_dydx_data(self, run_id):
            return None

    compat_ns["get_backtest_service"] = lambda: _InvalidService()
    missing = asyncio.run(
        backtests.validate_against_dydx_data("gone", current_user=object())
    )
    assert missing.status_code == 404

    class _ExplodingService(_StubService):
        async def validate_against_dydx_data(self, run_id):
            raise RuntimeError("indexer down")

    compat_ns["get_backtest_service"] = lambda: _ExplodingService()
    failed = asyncio.run(
        backtests.validate_against_dydx_data("boom", current_user=object())
    )
    assert failed.status_code == 500


def test_performance_metrics_and_live_progress_routes(monkeypatch, stub_service):
    metrics = asyncio.run(
        backtests.get_advanced_performance_metrics(
            "run-1", benchmark="ETH-USD", current_user=object()
        )
    )
    assert _payload(metrics)["data"]["sharpe_ratio"] == 1.2

    progress = asyncio.run(backtests.get_live_progress("run-1", current_user=object()))
    assert _payload(progress)["data"]["progress_pct"] == 33.0

    monkeypatch.setattr(
        backtests,
        "_get_advanced_performance_metrics_sync",
        lambda run_id, benchmark: None,
    )
    missing = asyncio.run(
        backtests.get_advanced_performance_metrics("gone", current_user=object())
    )
    assert missing.status_code == 404

    def _boom(run_id, benchmark):
        raise RuntimeError("db down")

    monkeypatch.setattr(backtests, "_get_advanced_performance_metrics_sync", _boom)
    failed = asyncio.run(
        backtests.get_advanced_performance_metrics("boom", current_user=object())
    )
    assert failed.status_code == 500

    monkeypatch.setattr(backtests, "_get_live_progress_sync", lambda run_id: None)
    missing_progress = asyncio.run(
        backtests.get_live_progress("gone", current_user=object())
    )
    assert missing_progress.status_code == 404
