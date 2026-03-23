"""Tests for asynchronous, candle-driven backtest execution."""

import asyncio
import importlib
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
