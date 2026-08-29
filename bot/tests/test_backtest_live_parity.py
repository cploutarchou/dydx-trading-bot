"""Live/backtest decision-parity regression tests.

The backtest simulation must compute z-scores and exit rules the same way
the live trading path does (src.trading.analysis.cointegration.calculate_zscore
and position_manager._resolve_exit_reason), otherwise backtest results do
not predict live behavior.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.trading.analysis.cointegration import calculate_zscore


def _synthetic_pair(n: int = 400, seed: int = 7):
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.normal(0, 0.4, n))
    noise = rng.normal(0, 0.25, n)
    prices_b = base + noise
    prices_a = 0.8 * base + 1.5 + rng.normal(0, 0.1, n)
    return prices_a, prices_b


def _timestamps(n: int) -> list[str]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        (start + timedelta(hours=i)).isoformat().replace("+00:00", "Z")
        for i in range(n)
    ]


def _make_service():
    from src.infrastructure.use_cases.service_backtest import BacktestService

    return BacktestService.__new__(BacktestService)


def test_simulate_pair_zscores_match_live_calculate_zscore():
    """Backtest entry z-scores must equal live calculate_zscore at the same bar."""
    service = _make_service()
    prices_a, prices_b = _synthetic_pair()
    ts = _timestamps(len(prices_a))
    params = {
        "stats_window": 21,
        "zscore_threshold": 1.5,
        "usd_per_trade": 10.0,
        "close_at_zscore_cross": True,
        "transaction_fee": 0.0,
        "slippage": 0.0,
    }

    trades, _snapshots, _daily = asyncio.run(
        service._simulate_pair(
            "parity-run",
            "AAA-USD",
            "BBB-USD",
            ts,
            prices_a,
            prices_b,
            params,
            trade_index_offset=0,
        )
    )

    assert trades, "expected at least one synthetic trade"

    # Recompute the simulation's spread the same way it fits it (OLS with
    # intercept) and derive z-scores with the LIVE rolling function.
    coeffs = np.polyfit(prices_b, prices_a, 1)
    spread = prices_a - (coeffs[0] * prices_b) - coeffs[1]
    live_z = calculate_zscore(pd.Series(spread)).to_numpy()

    ts_index = {t: i for i, t in enumerate(ts)}
    for trade in trades:
        idx = ts_index[trade["entry_timestamp"]]
        expected = live_z[idx]
        assert expected == expected, "live z must be defined at entry bar"
        assert abs(trade["entry_zscore"] - float(expected)) < 1e-3, (
            f"entry z mismatch at idx {idx}: backtest={trade['entry_zscore']} "
            f"live={float(expected)}"
        )


def test_simulate_pair_exit_rules_match_live_ladder():
    """Every simulated exit must carry a live exit reason and obey its rule."""
    service = _make_service()
    prices_a, prices_b = _synthetic_pair(seed=11)
    ts = _timestamps(len(prices_a))
    params = {
        "stats_window": 21,
        "zscore_threshold": 1.5,
        "usd_per_trade": 10.0,
        "close_at_zscore_cross": True,
        "transaction_fee": 0.0,
        "slippage": 0.0,
    }

    trades, _snapshots, _daily = asyncio.run(
        service._simulate_pair(
            "parity-run",
            "AAA-USD",
            "BBB-USD",
            ts,
            prices_a,
            prices_b,
            params,
            trade_index_offset=0,
        )
    )

    allowed = {"stop_loss", "take_profit", "timeout", "zscore_reversion"}
    reversion_trades = 0
    for trade in trades:
        assert trade["exit_reason"] in allowed, trade["exit_reason"]
        if trade["exit_reason"] == "zscore_reversion":
            reversion_trades += 1
            entry_z = trade["entry_zscore"]
            exit_z = trade["exit_zscore"]
            sign_crossed = (exit_z < 0 < entry_z) or (exit_z > 0 > entry_z)
            magnitude_held = abs(exit_z) >= abs(entry_z)
            assert sign_crossed and magnitude_held, (
                "zscore_reversion exit violates live rule "
                f"(entry_z={entry_z}, exit_z={exit_z})"
            )
    assert reversion_trades > 0, "expected at least one zscore_reversion exit"


def test_simulate_pair_stop_loss_param_bounds_losses():
    """A tight stop-loss must cap simulated per-trade percentage losses."""
    service = _make_service()
    # Large idiosyncratic noise on leg A so the spread can move well past
    # 1% of notional — otherwise the stop never triggers on synthetic data.
    rng = np.random.default_rng(23)
    n = 400
    base = 100.0 + np.cumsum(rng.normal(0, 0.4, n))
    prices_b = base + rng.normal(0, 0.25, n)
    prices_a = 0.8 * base + 1.5 + rng.normal(0, 4.0, n)
    ts = _timestamps(len(prices_a))
    ts = _timestamps(n)
    params = {
        "stats_window": 21,
        "zscore_threshold": 1.0,
        "usd_per_trade": 10.0,
        "close_at_zscore_cross": True,
        "transaction_fee": 0.0,
        "slippage": 0.0,
        "stop_loss_pct": 1.0,
        "take_profit_pct": 0.0,
        "position_timeout_hours": 0.0,
    }

    trades, _snapshots, _daily = asyncio.run(
        service._simulate_pair(
            "parity-run",
            "AAA-USD",
            "BBB-USD",
            ts,
            prices_a,
            prices_b,
            params,
            trade_index_offset=0,
        )
    )

    # pnl_pct includes fees; with zero fees a 1% stop must bound losses near
    # the stop level (small overshoot between bars is expected).
    for trade in trades:
        if trade["exit_reason"] == "stop_loss":
            assert trade["pnl_pct"] <= 0.0
    stop_exits = [t for t in trades if t["exit_reason"] == "stop_loss"]
    assert stop_exits, "expected the tight stop to trigger at least once"
    worst = min(t["pnl_pct"] for t in stop_exits)
    # Bar-to-bar overshoot can exceed the 1% trigger; anything beyond a
    # generous multiple would indicate the stop is not actually applied.
    assert worst > -10.0, f"stop-loss exit lost {worst}% — stop not applied?"
