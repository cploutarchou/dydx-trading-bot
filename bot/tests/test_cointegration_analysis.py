"""Unit tests for the cointegration analysis module (pairs-trading math core).

The statistical helpers are exercised against seeded synthetic series so every
assertion is deterministic: an AR(1) mean-reverting process with a known
half-life, a synthetic cointegrated pair (random walk + scaled random walk plus
stationary spread), and independent random walks as the negative case.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants import MAX_HALF_LIFE, WINDOW  # noqa: E402
from src.trading.analysis import cointegration as coint_mod  # noqa: E402
from src.trading.analysis.cointegration import (  # noqa: E402
    calculate_cointegration,
    calculate_zscore,
    count_zero_crossings,
    half_life_mean_reversion,
    store_cointegration_results,
)


def _ar1(n: int, k: float, mu: float, sigma: float, seed: int) -> np.ndarray:
    """AR(1) mean reversion: x[t+1] = x[t] + k*(mu - x[t]) + noise (half-life ln(2)/k)."""
    rng = np.random.default_rng(seed)
    series = np.zeros(n)
    series[0] = mu
    for i in range(1, n):
        series[i] = series[i - 1] + k * (mu - series[i - 1]) + rng.normal(0, sigma)
    return series


def _cointegrated_pair(n: int = 300, beta: float = 0.8, seed: int = 7):
    """Return (series_1, series_2) with series_1 = beta*series_2 + stationary AR(1)."""
    rng = np.random.default_rng(seed)
    series_2 = np.cumsum(rng.normal(0, 1.0, n)) + 100.0
    spread = _ar1(n, 0.25, 0.0, 0.6, seed + 1)
    return beta * series_2 + spread, series_2


def _random_walks(n: int = 300, seed: int = 42):
    rng = np.random.default_rng(seed)
    return (
        np.cumsum(rng.normal(0, 1.0, n)) + 100.0,
        np.cumsum(rng.normal(0, 1.0, n)) + 100.0,
    )


# ---------------------------------------------------------------- half life


def test_half_life_recovers_synthetic_ar1_half_life():
    # k=0.2 -> theoretical half-life ln(2)/0.2 ~= 3.47; estimator adds noise
    half_life = half_life_mean_reversion(_ar1(2000, 0.2, 0.0, 0.5, seed=3))
    assert half_life == pytest.approx(3.47, abs=1.5)


def test_half_life_rejects_series_of_length_one():
    with pytest.raises(coint_mod.SmartError, match="greater than 1"):
        half_life_mean_reversion([5.0])


def test_half_life_rejects_zero_variance_series():
    with pytest.raises(coint_mod.SmartError, match="variance is too small"):
        half_life_mean_reversion([5.0, 5.0, 5.0, 5.0])


def test_half_life_rejects_zero_slope(monkeypatch):
    import scipy.stats

    # A real series with healthy variance; the regression is forced to report
    # an exactly-zero slope so the guard branch is reached deterministically.
    monkeypatch.setattr(
        scipy.stats, "linregress", lambda *a, **k: (0.0, 0.0, 0.0, 0.0, 0.0)
    )
    walk = np.cumsum(np.random.default_rng(0).normal(0, 1, 100))
    with pytest.raises(coint_mod.SmartError, match="close to zero"):
        half_life_mean_reversion(walk)


# ---------------------------------------------------------------- z-score


def test_calculate_zscore_shapes_and_values():
    spread = pd.Series(np.sin(np.linspace(0, 40, 200)))
    zscore = calculate_zscore(spread)

    assert len(zscore) == len(spread)
    # Rolling window needs WINDOW observations before producing a value
    assert zscore.iloc[: WINDOW - 1].isna().all()
    assert not zscore.iloc[WINDOW - 1 :].isna().any()

    tail = spread.iloc[-WINDOW:]
    expected_last = (spread.iloc[-1] - tail.mean()) / tail.std()
    assert float(zscore.iloc[-1]) == pytest.approx(float(expected_last))


# ------------------------------------------------------- cointegration test


def test_calculate_cointegration_detects_synthetic_cointegrated_pair():
    series_1, series_2 = _cointegrated_pair()

    flag, hedge_ratio, half_life, intercept, p_value = calculate_cointegration(
        series_1, series_2
    )

    assert flag == 1
    assert float(hedge_ratio) == pytest.approx(0.8, abs=0.05)
    assert half_life > 0
    assert np.isfinite(intercept)
    assert 0.0 <= p_value < 0.05


def test_calculate_cointegration_rejects_independent_random_walks():
    flag, hedge_ratio, _, _, _ = calculate_cointegration(*_random_walks())

    assert flag == 0
    assert np.isfinite(hedge_ratio)


def test_calculate_cointegration_guards():
    walk = np.cumsum(np.random.default_rng(3).normal(0, 1, 200)) + 100.0

    with pytest.raises(coint_mod.SmartError, match="NaN"):
        calculate_cointegration(walk, walk + np.nan)
    with pytest.raises(coint_mod.SmartError, match="variance is too small"):
        calculate_cointegration(walk, np.full_like(walk, 5.0))
    with pytest.raises(coint_mod.SmartError, match="nearly identical"):
        calculate_cointegration(walk, walk.copy())
    with pytest.raises(coint_mod.SmartError, match="spread variance"):
        calculate_cointegration(walk, walk + 1.0)


# ------------------------------------------------------- zero crossings


def test_count_zero_crossings_counts_sign_flips():
    assert count_zero_crossings(pd.Series([1.0, -1.0, 1.0, -1.0])) == 3
    assert count_zero_crossings(pd.Series([1.0, 2.0, 3.0])) == 0


def test_count_zero_crossings_handles_short_and_nan_series():
    assert count_zero_crossings(pd.Series([1.0])) == 0
    assert count_zero_crossings(pd.Series([])) == 0
    assert count_zero_crossings(pd.Series([np.nan, 1.0])) == 0
    # NaNs are dropped before counting; two real sign flips remain
    assert count_zero_crossings(pd.Series([1.0, np.nan, -1.0, np.nan, 2.0])) == 2


# ------------------------------------------------------- full storage pass


def test_store_cointegration_results_finds_and_saves_cointegrated_pairs(
    monkeypatch,
):
    series_1, series_2 = _cointegrated_pair(seed=5)
    walk = _random_walks(seed=11)[0]
    frame = pd.DataFrame(
        {
            "COINTA": series_1,
            "COINTB": series_2,
            "WALK": walk,
            "FLAT": np.full_like(series_1, 42.0),
        }
    )

    calls: dict = {}

    class FakeMessenger:
        def send_cointegration_results(self, pairs_found, analysis_time, high):
            calls["messenger"] = (pairs_found, high)

    class FakeStorage:
        def save_pairs(self, pairs):
            calls["pairs"] = list(pairs)
            return {"success": True, "pairs_saved": len(pairs)}

    monkeypatch.setattr(coint_mod, "TelegramMessenger", FakeMessenger)
    monkeypatch.setattr(coint_mod, "pair_storage", FakeStorage())

    result = store_cointegration_results(frame)

    assert result == {"success": True, "pairs_saved": 1}
    # The zero-volatility FLAT market and the non-cointegrated WALK are excluded
    saved = calls["pairs"]
    assert [(p.base_market, p.quote_market) for p in saved] == [("COINTA", "COINTB")]
    pair = saved[0]
    assert 0 < pair.half_life <= MAX_HALF_LIFE
    assert pair.zero_crossings > 0
    assert 0.0 <= pair.confidence_score <= 1.0
    assert calls["messenger"] == (1, 1)


def test_store_cointegration_results_survives_dead_markets(monkeypatch):
    # Every market flat -> zero pairs found, storage still called, no crash
    frame = pd.DataFrame({"A": np.full(100, 10.0), "B": np.full(100, 20.0)})

    calls: dict = {}

    class FakeMessenger:
        def send_cointegration_results(self, pairs_found, analysis_time, high):
            calls["messenger"] = (pairs_found, high)

    class FakeStorage:
        def save_pairs(self, pairs):
            calls["pairs"] = list(pairs)
            return {"success": True, "pairs_saved": len(pairs)}

    monkeypatch.setattr(coint_mod, "TelegramMessenger", FakeMessenger)
    monkeypatch.setattr(coint_mod, "pair_storage", FakeStorage())

    result = store_cointegration_results(frame)

    assert result == {"success": True, "pairs_saved": 0}
    assert calls["pairs"] == []
    assert calls["messenger"] == (0, 0)
