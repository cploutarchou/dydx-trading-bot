"""Unit tests for the read-side BacktestQueryMixin (backtest reporting methods).

Drives the mixin through a minimal fake host so every projection — status,
trades, analytics, comparison, position snapshots, runtime health — is pinned
without a database.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infrastructure.use_cases import backtest_queries as bq  # noqa: E402
from src.infrastructure.use_cases.backtest_queries import (  # noqa: E402
    BacktestQueryMixin,
)


class _FakeRepository:
    def __init__(self, runs):
        self._runs = runs

    def list_runs(self, limit=None, offset=0, days_filter=None):
        return list(self._runs)


class _FakeHost(BacktestQueryMixin):
    """Minimal host satisfying the mixin's runtime contract."""

    _ACTIVE_STATUSES = {"PENDING", "RUNNING"}

    def __init__(self, data=None, overview=None, runs=None):
        self.repository = _FakeRepository(runs or [])
        self._tasks = {"task-1": object()}
        self._data = data
        self._overview = overview

    def _canonical_status(self, status):
        return str(status or "").upper()

    def _load_run_data(self, run_id):
        return self._data

    def _load_run_overview(self, run_id):
        return self._overview

    def _resolve_stale_run_data(self, data):
        return data

    def _strip_runtime_control(self, request):
        return {k: v for k, v in request.items() if not str(k).startswith("runtime_")}


def _details_payload():
    return {
        "run_id": "run-1",
        "name": "my-run",
        "status": "COMPLETED",
        "total_pnl": 123.5,
        "win_rate": 0.55,
        "sharpe_ratio": 1.4,
        "max_drawdown_pct": -8.2,
        "total_trades": 12,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "profit_factor": 1.7,
    }


def _trade(trade_id="t1", win=True, **overrides):
    payload = {
        "trade_id": trade_id,
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "entry_timestamp": "2026-01-01T00:00:00Z",
        "exit_timestamp": "2026-01-01T06:00:00Z",
        "entry_zscore": 2.0,
        "exit_zscore": 0.1,
        "entry_price_m1": 100.0,
        "exit_price_m1": 105.0,
        "entry_price_m2": 50.0,
        "exit_price_m2": 49.0,
        "hedge_ratio": 1.0,
        "pnl_usd": 12.5,
        "pnl_pct": 0.0125,
        "duration_hours": 6.0,
        "win": win,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------- details


def test_get_backtest_details_maps_payload_and_missing():
    host = _FakeHost(data=_details_payload())
    details = host.get_backtest_details("run-1")

    assert details is not None
    assert details.run_id == "run-1"
    assert details.name == "my-run"
    assert details.total_pnl == 123.5
    assert details.profit_factor == 1.7

    assert _FakeHost(data=None).get_backtest_details("missing") is None


# ---------------------------------------------------------------- status


def test_get_backtest_status_maps_overview_fields():
    host = _FakeHost(
        overview={
            "status": "running",
            "progress_pct": 42.5,
            "updated_at": "2026-01-02T00:00:00Z",
            "completed_at": None,
            "finished_at": "2026-01-03T00:00:00Z",
            "timeout_seconds": 600,
            "heartbeat_age_seconds": 1.5,
            "cancellable": True,
            "pausable": True,
            "resumable": False,
            "restartable": False,
            "request": {"mode": "backtest", "runtime_control": {"x": 1}},
            "current_pair": "BTC-USD/ETH-USD",
            "error": None,
            "error_code": "E_TIMEOUT",
            "strategy_id": 3,
            "retry_count": 2,
            "selected_pairs": ["BTC-USD", "ETH-USD"],
            "metadata": {"origin": "api"},
            "worker_backend": "celery",
            "worker_task_id": "abc",
        }
    )

    status = host.get_backtest_status("run-1")

    assert status.status == "running"
    assert status.progress_pct == 42.5
    assert status.completed_at == "2026-01-03T00:00:00Z"  # finished_at fallback
    assert status.timeout_seconds == 600.0
    assert status.heartbeat_age_seconds == 1.5
    assert status.cancellable and status.pausable
    assert not status.resumable and not status.restartable
    assert status.request == {"mode": "backtest"}  # runtime control stripped
    assert status.request_available is True
    assert status.strategy_id == 3
    assert status.retry_count == 2
    assert status.selected_pairs == ["BTC-USD", "ETH-USD"]
    assert status.metadata == {"origin": "api"}
    assert status.worker_backend == "celery"
    assert status.error_code == "E_TIMEOUT"


def test_get_backtest_status_handles_empty_request_and_non_dict_metadata():
    host = _FakeHost(overview={"status": "pending", "metadata": "garbage"})

    status = host.get_backtest_status("run-1")

    assert status.request is None
    assert status.request_available is False
    assert status.metadata == {}
    assert _FakeHost(overview=None).get_backtest_status("x") is None


# ---------------------------------------------------------------- trades


def test_get_backtest_trades_filters_slices_and_skips_malformed():
    host = _FakeHost(
        data={
            "trades": [
                _trade("t1", win=True),
                {"trade_id": "broken", "unexpected": "shape"},  # skipped
                _trade("t3", win=False),
                _trade("t4", win=True),
            ]
        }
    )

    trades = host.get_backtest_trades("run-1")
    assert [t.trade_id for t in trades] == ["t1", "t3", "t4"]

    winning = host.get_backtest_trades("run-1", winning_only=True)
    assert [t.trade_id for t in winning] == ["t1", "t4"]

    page = host.get_backtest_trades("run-1", limit=2, offset=1)
    assert [t.trade_id for t in page] == ["t3", "t4"]

    assert _FakeHost(data=None).get_backtest_trades("missing") == []


def test_get_backtest_trades_legacy_runs_report_no_trades():
    """Legacy runs without stored trades must return an empty list.

    The previous fallback synthesized a deterministic-random trade history
    seeded by run id — invented execution data presented as history.
    """
    data = {
        "total_trades": 6,
        "win_rate": 0.5,
        "total_pnl": 120.0,
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
    }
    assert _FakeHost(data=data).get_backtest_trades("run-x") == []
    assert _FakeHost(data=data).get_backtest_trades("run-x", winning_only=True) == []


def test_get_backtest_trades_legacy_fallback_with_bad_dates():
    data = {
        "total_trades": 2,
        "win_rate": 1.0,
        "total_pnl": 10.0,
        "start_date": "not-a-date",
    }
    trades = _FakeHost(data=data).get_backtest_trades("run-bad")

    assert trades == []


# ---------------------------------------------------------------- stats/health


def test_get_summary_stats_averages_completed_runs_only():
    host = _FakeHost(
        runs=[
            {"status": "completed", "sharpe_ratio": 1.0},
            {"status": "completed", "sharpe_ratio": 3.0},
            {"status": "failed", "sharpe_ratio": 99.0},
        ]
    )

    stats = host.get_summary_stats(days=30)

    assert stats["total_runs"] == 3
    assert stats["completed_runs"] == 2
    assert stats["avg_sharpe"] == pytest.approx(2.0)

    empty = _FakeHost(runs=[]).get_summary_stats()
    assert empty["avg_sharpe"] == 0.0


def test_get_runtime_health_counts_and_merges_job_metrics(monkeypatch):
    host = _FakeHost(
        runs=[
            {"status": "running"},
            {"status": "PENDING"},
            {"status": "completed"},
        ]
    )

    class Metrics:
        def get_runtime_metrics(self):
            return {"jobs_executing": 7}

    monkeypatch.setattr(bq, "async_job_manager", Metrics())
    health = host.get_runtime_health()

    assert health["queue_depth"] == 2
    assert health["active_jobs"] == 1
    assert health["total_runs"] == 3
    assert health["jobs_executing"] == 7


def test_get_runtime_health_swallows_metrics_failures(monkeypatch):
    class Broken:
        def get_runtime_metrics(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(bq, "async_job_manager", Broken())
    health = _FakeHost().get_runtime_health()

    assert health == {"queue_depth": 0, "active_jobs": 1, "total_runs": 0}


# ---------------------------------------------------------------- analytics


def test_get_backtest_analytics_and_advanced_metrics():
    host = _FakeHost(
        data={"max_drawdown_pct": -5.0, "total_pnl": 50.0, "sharpe_ratio": 2.0}
    )

    analytics = host.get_backtest_analytics("run-1")
    assert analytics == {
        "run_id": "run-1",
        "risk": {"max_drawdown_pct": -5.0},
        "performance": {"total_pnl": 50.0, "sharpe_ratio": 2.0},
    }
    assert _FakeHost(data=None).get_backtest_analytics("x") is None

    advanced = host.get_advanced_performance_metrics("run-1")
    assert advanced["benchmark"] == "BTC-USD"
    assert advanced["sharpe_ratio"] == 2.0
    # Benchmark-relative metrics are not computed anywhere yet; they must be
    # null rather than the fabricated constants they used to return.
    assert advanced["alpha"] is None
    assert advanced["beta"] is None
    assert advanced["information_ratio"] is None

    custom = host.get_advanced_performance_metrics("run-1", benchmark="ETH-USD")
    assert custom["benchmark"] == "ETH-USD"
    assert _FakeHost(data=None).get_advanced_performance_metrics("x") is None


def test_get_live_progress_maps_overview():
    host = _FakeHost(
        overview={
            "status": "RUNNING",
            "progress_pct": 10.0,
            "finished_at": "2026-01-05T00:00:00Z",
            "heartbeat_age_seconds": 2.0,
            "worker_backend": "asyncio",
            "result_summary": {"total_pnl": 5.0},
        }
    )

    progress = host.get_live_progress("run-1")

    assert progress["progress"] == 10.0
    assert progress["progress_pct"] == 10.0
    assert progress["completed_at"] == "2026-01-05T00:00:00Z"
    assert progress["heartbeat_age_seconds"] == 2.0
    assert progress["worker_backend"] == "asyncio"
    assert progress["result_summary"] == {"total_pnl": 5.0}
    assert _FakeHost(overview=None).get_live_progress("x") is None


# ---------------------------------------------------------------- compare


def test_compare_backtests_summarizes_and_tracks_missing():
    host = _FakeHost(
        data={
            "run_id": "a",
            "name": "A",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00Z",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "total_pnl": 100.0,
            "win_rate": 0.6,
            "sharpe_ratio": 1.5,
            "max_drawdown_pct": 10.0,
            "total_trades": 10,
        }
    )
    # Second run loads different data per invocation
    payloads = [
        host._data,
        {
            "run_id": "b",
            "status": "completed",
            "total_pnl": 50.0,
            "win_rate": 0.4,
            "sharpe_ratio": 0.5,
            "max_drawdown_pct": 5.0,
            "total_trades": 20,
        },
    ]
    host._load_run_data = lambda run_id: (
        payloads[0] if run_id == "a" else payloads[1] if run_id == "b" else None
    )

    result = host.compare_backtests(["a", "b", "missing"])

    assert result["run_ids"] == ["a", "b"]
    assert result["missing_runs"] == ["missing"]
    assert [r["run_id"] for r in result["runs"]] == ["a", "b"]
    # For pnl the max wins; for drawdown the min wins (the code treats
    # max_drawdown_pct as a positive magnitude, so min = shallowest = best)
    assert result["summary"]["total_pnl"]["best"] == 100.0
    assert result["summary"]["total_pnl"]["worst"] == 50.0
    assert result["summary"]["total_pnl"]["average"] == 75.0
    assert result["summary"]["max_drawdown_pct"]["best"] == 5.0
    assert result["summary"]["max_drawdown_pct"]["worst"] == 10.0


def test_compare_backtests_all_missing_and_custom_metrics():
    host = _FakeHost()
    host._load_run_data = lambda run_id: None

    result = host.compare_backtests(["gone"])

    assert result["runs"] == []
    assert result["summary"] == {}
    assert result["missing_runs"] == ["gone"]

    host._load_run_data = lambda run_id: {"run_id": "a", "custom_metric": "n/a"}
    result = host.compare_backtests(["a"], metrics=["custom_metric"])
    # Non-numeric values are skipped, not crashed on
    assert result["summary"] == {}
    assert result["metrics"] == ["custom_metric"]


# --------------------------------------------------- comprehensive analytics


def test_get_comprehensive_analytics_passes_through_daily_pnl():
    data = {
        "status": "completed",
        "total_pnl": 10.0,
        "daily_pnl": [{"date": "2026-01-01", "pnl": 5.0}],
        "trades": [{"trade_id": "t1"}],
        "position_snapshots": [],
    }

    result = _FakeHost(data=data).get_comprehensive_analytics("run-1")

    assert result["candles"] == data["daily_pnl"]
    assert result["daily_pnl"] == data["daily_pnl"]
    assert result["trades"] == [{"trade_id": "t1"}]
    assert result["performance"]["total_pnl"] == 10.0


def test_get_comprehensive_analytics_synthesizes_series_when_missing():
    data = {
        "status": "completed",
        "total_pnl": 90.0,
        "total_trades": 9,
        "start_date": "2026-01-01",
        "end_date": "2026-01-11",  # 10 days
    }

    result = _FakeHost(data=data).get_comprehensive_analytics("run-1")

    series = result["daily_pnl"]
    assert len(series) == 10
    assert sum(entry["pnl"] for entry in series) == pytest.approx(90.0, abs=0.1)
    assert {entry["market"] for entry in series} == {"PORTFOLIO"}
    assert series[0]["trades"] == 1  # 9 trades / 10 days, rounded
    # Deterministic per run id
    again = _FakeHost(data=data).get_comprehensive_analytics("run-1")
    assert again["daily_pnl"] == series

    # Bad dates fall back to a 30-day window
    bad_dates = dict(data, start_date="nope")
    fallback = _FakeHost(data=bad_dates).get_comprehensive_analytics("run-2")
    assert len(fallback["daily_pnl"]) == 30


# --------------------------------------------------- position snapshots


def test_get_position_snapshots_filters_and_slices_raw():
    snapshots = [
        {"positions": [{"market_1": "BTC-USD", "market_2": "ETH-USD"}]},
        {"positions": [{"market_1": "SOL-USD", "market_2": "AVAX-USD"}]},
        {"positions": [{"market_1": "BTC-USD", "market_2": "ETH-USD"}]},
    ]
    host = _FakeHost(data={"position_snapshots": snapshots})

    assert len(host.get_position_snapshots("run-1")) == 3
    filtered = host.get_position_snapshots("run-1", market_pair="BTC-USD/ETH-USD")
    assert len(filtered) == 2
    page = host.get_position_snapshots("run-1", limit=1, offset=1)
    assert page == [snapshots[1]]
    assert _FakeHost(data=None).get_position_snapshots("x") == []


def test_get_position_snapshots_legacy_fallback():
    data = {
        "total_trades": 4,
        "win_rate": 0.5,
        "total_pnl": 40.0,
        "start_date": "2026-01-01",
        "end_date": "2026-01-05",
    }

    result = _FakeHost(data=data).get_position_snapshots("run-1")

    assert len(result) == 4
    first_positions = result[0]["positions"]
    assert first_positions[0]["market_1"] == "BTC-USD"
    assert {s["positions"][0]["status"] for s in result} == {"CLOSED", "STOPPED"}

    filtered = _FakeHost(data=data).get_position_snapshots(
        "run-1", market_pair="SOL-USD/AVAX-USD"
    )
    assert len(filtered) == 1
    assert filtered[0]["positions"][0]["market_1"] == "SOL-USD"
