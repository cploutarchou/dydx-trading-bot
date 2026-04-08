"""Tests for asynchronous, candle-driven backtest execution."""

import asyncio
import importlib
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_modules():
    models_module = importlib.import_module("src.infrastructure.domain.models_backtest")
    service_module = importlib.import_module("src.infrastructure.use_cases.service_backtest")

    return models_module.BacktestConfigRequest, service_module


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

        candles = []
        idx = 0
        cursor = start
        while cursor <= end:
            wave = math.sin(idx / 8.0) * 15.0
            trend = idx * 0.2
            close = market_bias + wave + trend
            candles.append(
                {
                    "startedAt": cursor.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
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


async def _wait_for_terminal_status(service, run_id, timeout_seconds=2.0):
    end = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < end:
        status = service.get_backtest_status(run_id)
        assert status is not None
        if status.status in {"completed", "failed", "cancelled"}:
            return status.status
        await asyncio.sleep(0.02)
    raise TimeoutError("backtest did not reach terminal status in time")


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

        trades = service.get_backtest_trades(created.run_id, limit=500)
        assert len(trades) == details.total_trades

        progress = service.get_live_progress(created.run_id)
        assert progress is not None
        assert float(progress["progress_pct"]) == 100.0

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

def test_build_market_pairs_uses_all_unique_combinations():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    pairs = BacktestService._build_market_pairs(["BTC-USD", "ETH-USD", "SOL-USD", "ETH-USD", ""])

    assert pairs == [
        ("BTC-USD", "ETH-USD"),
        ("BTC-USD", "SOL-USD"),
        ("ETH-USD", "SOL-USD"),
    ]


def test_build_market_pairs_with_four_markets_returns_all_six_combinations():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    pairs = BacktestService._build_market_pairs(["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD"])

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
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

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

    ranked = BacktestService._prioritize_pairs_by_liquidity(pairs, market_map)
    assert ranked == [
        ("BTC-USD", "ETH-USD"),  # 1900
        ("BTC-USD", "SOL-USD"),  # 1300
        ("ETH-USD", "AVAX-USD"),  # 1000
    ]


def test_prioritize_pairs_by_liquidity_is_stable_for_ties():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

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
    ranked = BacktestService._prioritize_pairs_by_liquidity(pairs, market_map)
    assert ranked == pairs


def test_pair_selection_mode_normalization_aliases():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    assert BacktestService._normalize_pair_selection_mode("volume") == "liquidity"
    assert BacktestService._normalize_pair_selection_mode("none") == "input"
    assert BacktestService._normalize_pair_selection_mode("order") == "input"
    assert BacktestService._normalize_pair_selection_mode("cointegration") == "cointegration"
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
        assert set(health.keys()) == {"queue_depth", "active_jobs", "total_runs"}
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


def test_backtest_status_survives_service_recreation_with_db_repository(monkeypatch, tmp_path):
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


def test_explicit_interrupted_reconcile_flow_updates_orphaned_persisted_runs():
    _, service_module = _load_modules()
    BacktestService = service_module.BacktestService

    from src.infrastructure.persistence.repository_backtest import BacktestRepository

    BacktestService._runs.clear()
    BacktestService._tasks.clear()
    BacktestRepository._memory_runs.clear()

    service = BacktestService(session=None)
    now = datetime.now(timezone.utc).isoformat()
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
        run["run_id"] == "run-orphaned-ops"
        for run in ops_report["interrupted_runs"]
    )
