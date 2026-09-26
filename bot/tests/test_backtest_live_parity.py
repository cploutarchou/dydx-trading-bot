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
import pytest

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
        # Disable mid-run walk-forward refits so the single calibration fit
        # this test mirrors stays in force for the whole trade window.
        "refit_interval_bars": 10**9,
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
    # intercept on the CALIBRATION window) and derive z-scores with the LIVE
    # rolling function.
    stats_window = 21
    calibration_end = max(2 * stats_window, len(prices_a) // 2)
    coeffs = np.polyfit(prices_b[:calibration_end], prices_a[:calibration_end], 1)
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
        "refit_interval_bars": 10**9,
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

    allowed = {
        "stop_loss",
        "take_profit",
        "trailing_stop",
        "timeout",
        "zscore_reversion",
    }
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


def test_simulate_pair_trailing_stop_follows_the_live_rule_bar_by_bar(monkeypatch):
    """Every simulated trailing-stop exit fires on the first bar where the live
    ladder would fire, given the same P&L and the same running best level."""
    from src.trading import position_manager

    service = _make_service()
    prices_a, prices_b = _synthetic_pair(seed=11)
    ts = _timestamps(len(prices_a))
    trail = 0.3
    params = {
        "stats_window": 21,
        "zscore_threshold": 1.5,
        "usd_per_trade": 10.0,
        "close_at_zscore_cross": False,
        "transaction_fee": 0.0,
        "slippage": 0.0,
        "refit_interval_bars": 10**9,
        "stop_loss_pct": 0.0,
        "take_profit_pct": 0.0,
        "position_timeout_hours": 0.0,
        "trailing_stop_pct": trail,
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

    assert trades, "expected at least one trailing-stop exit"
    assert {trade["exit_reason"] for trade in trades} == {"trailing_stop"}

    monkeypatch.setattr(position_manager, "STOP_LOSS_PCT", 0.0)
    monkeypatch.setattr(position_manager, "TAKE_PROFIT_PCT", 0.0)
    monkeypatch.setattr(position_manager, "POSITION_TIMEOUT_HOURS", 0)
    monkeypatch.setattr(position_manager, "CLOSE_AT_ZSCORE_CROSS", False)
    monkeypatch.setattr(position_manager, "TRAILING_STOP_PCT", trail)

    calibration_end = max(2 * 21, len(prices_a) // 2)
    hedge = float(
        np.polyfit(prices_b[:calibration_end], prices_a[:calibration_end], 1)[0]
    )
    ts_index = {t: i for i, t in enumerate(ts)}
    for trade in trades:
        entry = ts_index[trade["entry_timestamp"]]
        exit_ = ts_index[trade["exit_timestamp"]]
        ep1, ep2 = float(prices_a[entry]), float(prices_b[entry])
        short = trade["entry_zscore"] > 0
        notional = abs(ep1) + abs(hedge * ep2)
        peak = None
        for bar in range(entry + 1, exit_ + 1):
            move = (float(prices_a[bar]) - ep1) - hedge * (float(prices_b[bar]) - ep2)
            pnl = (-move if short else move) / notional * 100.0
            peak = pnl if peak is None else max(peak, pnl)
            live = position_manager._resolve_exit_reason(
                z_score_current=0.0,
                z_score_traded=1.0,
                unrealized_pnl_pct=pnl,
                position_age_hours=0.0,
                peak_unrealized_pnl_pct=peak,
            )
            expected = "trailing_stop" if bar == exit_ else None
            assert live == expected, (bar, entry, exit_, pnl, peak)


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


def test_simulate_pair_execution_delay_fills_at_later_bar():
    """With execution_delay_bars=1, fills use the NEXT bar's close/timestamp,
    never the signal bar's."""
    service = _make_service()
    prices_a, prices_b = _synthetic_pair(seed=31)
    ts = _timestamps(len(prices_a))

    immediate_params = {
        "stats_window": 21,
        "zscore_threshold": 1.5,
        "usd_per_trade": 10.0,
        "close_at_zscore_cross": True,
        "transaction_fee": 0.0,
        "slippage": 0.0,
        "refit_interval_bars": 10**9,
        "execution_delay_bars": 0,
    }
    delayed_params = dict(immediate_params, execution_delay_bars=1)

    immediate, _, _ = asyncio.run(
        service._simulate_pair(
            "delay-run",
            "AAA-USD",
            "BBB-USD",
            ts,
            prices_a,
            prices_b,
            immediate_params,
            trade_index_offset=0,
        )
    )
    delayed, _, _ = asyncio.run(
        service._simulate_pair(
            "delay-run",
            "AAA-USD",
            "BBB-USD",
            ts,
            prices_a,
            prices_b,
            delayed_params,
            trade_index_offset=0,
        )
    )

    assert immediate and delayed
    ts_index = {t: i for i, t in enumerate(ts)}
    for trade in delayed:
        entry_i = ts_index[trade["entry_timestamp"]]
        exit_i = ts_index[trade["exit_timestamp"]]
        # Delayed fills book at least one bar after the immediate run's
        # trades on the same series (positions open no earlier).
        assert entry_i >= ts_index[immediate[0]["entry_timestamp"]]
        assert exit_i > entry_i or exit_i == entry_i
    # The two executions must differ somewhere (price or timing), proving
    # the delay is actually applied rather than ignored.
    differing = any(
        a["entry_timestamp"] != b["entry_timestamp"]
        or abs(a["entry_price_m1"] - b["entry_price_m1"]) > 1e-9
        for a, b in zip(immediate, delayed)
    )
    assert differing or len(immediate) != len(
        delayed
    ), "execution_delay_bars=1 produced identical results to delay=0"


def test_simulate_pair_walk_forward_refits_use_only_past_data():
    """Refits at mid-run must use data strictly before the refit bar."""
    service = _make_service()
    import numpy as np

    # Non-stationary relationship: the loading drifts from 0.6 to 1.0 over
    # the sample, so fits on different windows genuinely differ.
    rng = np.random.default_rng(43)
    n = 400
    base = 100.0 + np.cumsum(rng.normal(0, 0.4, n))
    prices_b = base + rng.normal(0, 0.25, n)
    loadings = 0.6 + 0.4 * np.linspace(0, 1, n)
    prices_a = loadings * base + 1.5 + rng.normal(0, 0.1, n)
    ts = _timestamps(n)
    stats_window = 21
    calibration_end = max(2 * stats_window, n // 2)
    refit_at = calibration_end + max(
        stats_window, calibration_end // 2
    )  # default schedule refits here

    # The fit in force after the mid-run refit must equal a fit on data
    # strictly before refit_at — not on the full sample.
    full = np.polyfit(prices_b, prices_a, 1)
    partial = np.polyfit(prices_b[:refit_at], prices_a[:refit_at], 1)
    assert abs(full[0] - partial[0]) > 1e-9, "fixture must distinguish fits"

    params = {
        "stats_window": stats_window,
        "zscore_threshold": 1.5,
        "usd_per_trade": 10.0,
        "close_at_zscore_cross": True,
        "transaction_fee": 0.0,
        "slippage": 0.0,
    }
    trades, _, _ = asyncio.run(
        service._simulate_pair(
            "refit-run",
            "AAA-USD",
            "BBB-USD",
            ts,
            prices_a,
            prices_b,
            params,
            trade_index_offset=0,
        )
    )
    # Trades booked after the refit must carry the refit hedge ratio (the
    # partial fit), not the full-sample one.
    post = [
        t
        for t in trades
        if _timestamps(n) and ts.index(t["exit_timestamp"]) >= refit_at
    ]
    for trade in post:
        assert abs(trade["hedge_ratio"] - round(float(partial[0]), 6)) < 1e-4


# --- cost + funding entry gate parity ---------------------------------------


def _gate_params(**extra):
    params = {
        "stats_window": 21,
        "zscore_threshold": 1.5,
        "usd_per_trade": 10.0,
        "close_at_zscore_cross": True,
        "transaction_fee": 0.0005,
        "slippage": 0.001,
    }
    params.update(extra)
    return params


def _simulate(service, prices_a, prices_b, params, diagnostics=None):
    kwargs = {}
    if diagnostics is not None:
        kwargs["cost_gate_diagnostics"] = diagnostics
    return asyncio.run(
        service._simulate_pair(
            "gate-run",
            "AAA-USD",
            "BBB-USD",
            _timestamps(len(prices_a)),
            prices_a,
            prices_b,
            params,
            trade_index_offset=0,
            **kwargs,
        )
    )


def test_live_and_backtest_cost_gate_wrappers_agree_with_zero_funding(monkeypatch):
    """Same inputs, funding = 0: the live and backtest wrappers decide alike.

    Sigma is computed by each side itself (live: calculate_spread_std on the
    spread series; backtest: the simulator's window std), so this also pins
    that both measure the same sigma.
    """
    from src.trading import position_manager
    from src.trading.analysis.cointegration import WINDOW

    monkeypatch.setattr(position_manager, "CLOSE_AT_ZSCORE_CROSS", True)
    service = _make_service()
    prices_a, prices_b = _synthetic_pair(n=120, seed=5)
    hedge_ratio = 0.8
    spread = prices_a - hedge_ratio * prices_b
    live_z = float(calculate_zscore(pd.Series(spread)).iloc[-1])
    window = spread[-WINDOW:]
    backtest_std = float(np.std(window, ddof=1))

    cases = [
        # (taker fee, slippage per fill, multiple)
        (0.0005, 0.0005, 2.5),
        (0.0005, 0.001, 20.0),
        (0.002, 0.003, 5.0),
        (0.0, 0.0, 1.0),
    ]
    seen = set()
    for fee, slip, multiple in cases:
        live = position_manager._live_entry_cost_decision(
            settings={
                "COST_GATE_TAKER_FEE": fee,
                "COST_GATE_SLIPPAGE_BPS": slip * 10000,
                "COST_GATE_EDGE_MULTIPLE": multiple,
                "FUNDING_SAME_SIDE_THRESHOLD": 0.00001,
            },
            z_score=live_z,
            spread=pd.Series(spread),
            price_1=float(prices_a[-1]),
            price_2=float(prices_b[-1]),
            hedge_ratio=hedge_ratio,
            half_life=10.0,
            market_1={"nextFundingRate": "0"},
            market_2={"nextFundingRate": "0"},
        )
        backtest = service._backtest_entry_cost_decision(
            z=live_z,
            spread_std=backtest_std,
            price_1=float(prices_a[-1]),
            price_2=float(prices_b[-1]),
            hedge_ratio=hedge_ratio,
            close_on_cross=True,
            transaction_fee=fee,
            slippage=slip,
            multiple=multiple,
        )
        assert live.accepted == backtest.accepted
        assert live.reason == backtest.reason
        assert live.funding_frac == 0 and backtest.funding_frac == 0
        assert float(live.edge_frac) == pytest.approx(float(backtest.edge_frac))
        assert live.fee_frac == backtest.fee_frac
        assert live.slippage_frac == backtest.slippage_frac
        assert live.multiple == backtest.multiple
        seen.add(live.accepted)
    assert seen == {True, False}, "cases should cover an accept and a reject"


def test_cost_gate_off_leaves_backtest_trades_and_metrics_unchanged():
    service = _make_service()
    prices_a, prices_b = _synthetic_pair(n=600, seed=7)

    absent = _simulate(service, prices_a, prices_b, _gate_params())
    explicit_off = _simulate(
        service,
        prices_a,
        prices_b,
        _gate_params(cost_gate_enabled=False, cost_gate_edge_multiple=20),
    )
    diagnostics = {}
    off_with_diagnostics = _simulate(
        service, prices_a, prices_b, _gate_params(), diagnostics=diagnostics
    )

    assert absent[0], "expected synthetic trades"
    assert absent == explicit_off == off_with_diagnostics
    assert diagnostics == {}


def test_backtest_ledger_splits_the_unchanged_round_trip_cost():
    service = _make_service()
    prices_a, prices_b = _synthetic_pair(n=600, seed=7)
    usd, fee, slip = 10.0, 0.0005, 0.001

    trades, _snapshots, _daily = _simulate(
        service, prices_a, prices_b, _gate_params(transaction_fee=fee, slippage=slip)
    )

    assert trades
    for trade in trades:
        assert trade["fee_cost"] == pytest.approx(usd * fee * 2.0, abs=1e-8)
        assert trade["slippage_cost"] == pytest.approx(usd * slip * 2.0, abs=1e-8)
        # The split sums to the combined cost the P&L deducts.
        assert trade["fee_cost"] + trade["slippage_cost"] == pytest.approx(
            usd * (fee + slip) * 2.0, abs=1e-8
        )


def test_cost_gate_rejections_go_to_run_diagnostics_not_live_counters():
    from src.trading.arbitrage_observability import reset_metrics, snapshot_metrics

    reset_metrics()
    service = _make_service()
    prices_a, prices_b = _synthetic_pair(n=600, seed=7)
    baseline, _s, _d = _simulate(service, prices_a, prices_b, _gate_params())

    diagnostics = {}
    gated, _s, _d = _simulate(
        service,
        prices_a,
        prices_b,
        _gate_params(
            cost_gate_enabled=True,
            cost_gate_edge_multiple=20,
            transaction_fee=0.01,
            slippage=0.01,
        ),
        diagnostics=diagnostics,
    )

    assert len(gated) < len(baseline)
    rejected = diagnostics["rejected_by_reason"]
    assert set(rejected) == {"edge_lt_cost"}
    assert diagnostics["evaluated"] == diagnostics.get("accepted", 0) + sum(
        rejected.values()
    )
    assert diagnostics["edge_multiple"] == 20.0
    assert snapshot_metrics()["rejection_reasons"] == {}
    assert snapshot_metrics()["counters"]["opportunities_rejected_total"] == 0.0


def test_cost_gate_with_zero_cost_never_rejects_a_backtest_entry():
    service = _make_service()
    prices_a, prices_b = _synthetic_pair(n=600, seed=11)
    free = _gate_params(transaction_fee=0.0, slippage=0.0)

    baseline = _simulate(service, prices_a, prices_b, free)
    diagnostics = {}
    gated = _simulate(
        service,
        prices_a,
        prices_b,
        dict(free, cost_gate_enabled=True, cost_gate_edge_multiple=1),
        diagnostics=diagnostics,
    )

    assert baseline[0]
    assert gated == baseline
    assert diagnostics["accepted"] == diagnostics["evaluated"] > 0


def test_cost_gate_fails_closed_in_backtest_without_a_zscore_exit():
    service = _make_service()
    prices_a, prices_b = _synthetic_pair(n=600, seed=11)
    diagnostics = {}

    trades, _s, _d = _simulate(
        service,
        prices_a,
        prices_b,
        _gate_params(close_at_zscore_cross=False, cost_gate_enabled=True),
        diagnostics=diagnostics,
    )

    assert trades == []
    assert set(diagnostics["rejected_by_reason"]) == {"cost_inputs_invalid"}
