"""Regression tests for parameter-sensitive simulated backtest results."""

import asyncio
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_modules():
    models_module = importlib.import_module(
        "src.infrastructure.domain.models_backtest"
    )
    service_module = importlib.import_module(
        "src.infrastructure.use_cases.service_backtest"
    )

    return models_module.BacktestConfigRequest, service_module.BacktestService


def _request(**trading_parameters):
    BacktestConfigRequest, _ = _load_modules()
    return BacktestConfigRequest(
        name="test-run",
        description="test",
        start_date="2026-02-05",
        end_date="2026-03-07",
        initial_balance=1000.0,
        trading_parameters=trading_parameters,
        pairs=["BTC-USD", "ETH-USD", "SOL-USD"],
    )


def test_default_parameters_match_historical_baseline_metrics():
    _, BacktestService = _load_modules()
    service = BacktestService(session=None)

    result = asyncio.run(
        service.create_and_run_backtest(
            _request(
                zscore_threshold=1.5,
                usd_per_trade=10.0,
                stats_window=21,
                close_at_zscore_cross=True,
            )
        )
    )

    assert result.total_pnl == 48.2
    assert result.win_rate == 0.59
    assert result.sharpe_ratio == 1.33
    assert result.max_drawdown_pct == 10.9
    assert result.total_trades == 24


def test_production_profile_cost_inputs_match_expected_smoke_metrics():
    _, BacktestService = _load_modules()
    service = BacktestService(session=None)

    result = asyncio.run(
        service.create_and_run_backtest(
            _request(
                zscore_threshold=1.5,
                usd_per_trade=10.0,
                stats_window=21,
                close_at_zscore_cross=True,
                transaction_fee=0.0005,
                slippage=0.001,
                risk_free_rate=0.02,
                max_positions=5,
            )
        )
    )

    assert result.total_pnl == 41.8
    assert result.win_rate == 0.59
    assert result.sharpe_ratio == 1.24
    assert result.max_drawdown_pct == 12.7
    assert result.total_trades == 29


def test_parameter_changes_produce_distinct_results():
    _, BacktestService = _load_modules()
    service = BacktestService(session=None)

    aggressive = asyncio.run(
        service.create_and_run_backtest(
            _request(
                zscore_threshold=1.0,
                usd_per_trade=25.0,
                stats_window=14,
                close_at_zscore_cross=True,
            )
        )
    )
    conservative = asyncio.run(
        service.create_and_run_backtest(
            _request(
                zscore_threshold=2.0,
                usd_per_trade=10.0,
                stats_window=30,
                close_at_zscore_cross=True,
            )
        )
    )

    assert aggressive.total_pnl != conservative.total_pnl
    assert aggressive.sharpe_ratio != conservative.sharpe_ratio
    assert aggressive.total_trades != conservative.total_trades
    assert aggressive.max_drawdown_pct != conservative.max_drawdown_pct
