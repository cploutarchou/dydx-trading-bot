"""Unit tests for the backtest pair-prioritization engine (module-level core).

Covers the cointegration-scoring paths end to end: the strict
statsmodels path (Engle-Granger + ADF), its significance-penalty branch, its
guard clauses, its exception fallback, and the no-statsmodels heuristic path
(exercised by nulling the module-level ``coint``/``adfuller`` symbols).
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infrastructure.use_cases import backtest_pair_selection as bps  # noqa: E402


def _ar1(n: int, k: float, mu: float, sigma: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    series = np.zeros(n)
    series[0] = mu
    for i in range(1, n):
        series[i] = series[i - 1] + k * (mu - series[i - 1]) + rng.normal(0, sigma)
    return series


def _hist(series) -> dict:
    return {f"k{i:03d}": float(v) for i, v in enumerate(series)}


def _coint_histories(n: int = 120, seed: int = 7):
    """Log-price histories: A/B cointegrated, C/D independent walks."""
    rng = np.random.default_rng(seed)
    base = np.cumsum(rng.normal(0, 0.01, n)) + 5.0
    a = 0.7 * base + _ar1(n, 0.3, 0.0, 0.05, seed + 1)
    b = base
    c = np.cumsum(rng.normal(0, 0.01, n)) + 5.0
    d = np.cumsum(rng.normal(0, 0.01, n)) + 5.0
    return {"A": _hist(a), "B": _hist(b), "C": _hist(c), "D": _hist(d)}


# ------------------------------------------------------------- small helpers


def test_clamp01_bounds():
    assert bps._clamp01(-0.5) == 0.0
    assert bps._clamp01(0.42) == 0.42
    assert bps._clamp01(1.7) == 1.0


def test_safe_float_swallows_bad_values():
    assert bps._safe_float("1.5") == 1.5
    assert bps._safe_float(None) == 0.0
    assert bps._safe_float("nope", default=-1.0) == -1.0


def test_align_series_intersects_and_sorts_keys():
    m1 = {"b": 2.0, "a": 1.0, "c": 3.0}
    m2 = {"c": 30.0, "a": 10.0, "d": 40.0}

    keys, p1, p2 = bps._align_series(m1, m2)

    assert keys == ["a", "c"]
    assert p1.tolist() == [1.0, 3.0]
    assert p2.tolist() == [10.0, 30.0]


def test_extract_market_liquidity_prefers_best_known_field():
    assert bps._extract_market_liquidity({"volume24H": "123.5"}) == 123.5
    assert bps._extract_market_liquidity({"notionalVolume24H": 7}) == 7.0
    assert bps._extract_market_liquidity({"volume24h": 5, "baseVolume": 9}) == 9.0
    assert bps._extract_market_liquidity("not-a-dict") == 0.0
    assert bps._extract_market_liquidity({"volume24H": "garbage"}) == 0.0


def test_compute_market_volatility():
    # Short or non-dict histories score zero
    assert bps._compute_market_volatility({"k": 1.0, "k2": 2.0}) == 0.0
    assert bps._compute_market_volatility("nope") == 0.0

    prices = {"a": 100.0, "b": 101.0, "c": 100.5, "d": 102.0}
    expected_returns = np.diff([100.0, 101.0, 100.5, 102.0]) / np.array(
        [100.0, 101.0, 100.5]
    )
    assert bps._compute_market_volatility(prices) == pytest.approx(
        float(np.std(expected_returns))
    )


# ------------------------------------------------------- volatility ranking


def test_prioritize_pairs_by_volatility_orders_and_passes_through():
    histories = {
        "A": {f"k{i}": v for i, v in enumerate([100, 101, 100.5, 103, 102])},
        "B": {f"k{i}": v for i, v in enumerate([50, 50.1, 50.0, 50.1, 50.2])},
    }
    pairs = [("B", "B"), ("A", "A"), ("A", "B")]

    ranked = bps._prioritize_pairs_by_volatility(pairs, histories)
    assert ranked[0] == ("A", "A")  # highest combined volatility
    assert ranked[-1] == ("B", "B")

    # Empty inputs pass through unchanged
    assert bps._prioritize_pairs_by_volatility([], histories) == []
    assert bps._prioritize_pairs_by_volatility(pairs, {}) == pairs


# ------------------------------------------------- cointegration scoring


def test_pair_cointegration_score_strict_path_ranks_cointegrated_above_walks():
    histories = _coint_histories()

    assert bps.coint is not None and bps.adfuller is not None  # statsmodels live
    cointegrated = bps._pair_cointegration_score("A", "B", histories)
    walks = bps._pair_cointegration_score("C", "D", histories)

    assert cointegrated > 0.0
    # Independent walks fail the significance thresholds -> strict penalty zone
    assert walks < -100.0
    assert cointegrated > walks


def test_pair_cointegration_score_guards():
    histories = _coint_histories()

    # Fewer than 48 aligned points -> unusable
    short = {"A": dict(list(histories["A"].items())[:20]), "B": histories["B"]}
    assert bps._pair_cointegration_score("A", "B", short) == -1e9

    # Non-positive prices (log undefined) -> unusable
    negative = {"A": _hist(np.full(60, -1.0)), "B": histories["B"]}
    assert bps._pair_cointegration_score("A", "B", negative) == -1e9

    # Degenerate spread dynamics (zero-variance lagged spread) -> unusable
    flat_spread = {"A": _hist(np.arange(60.0)), "B": histories["B"]}
    assert bps._pair_cointegration_score("A", "B", flat_spread) == -1e9


def test_pair_cointegration_score_falls_back_when_stats_fail(monkeypatch):
    histories = _coint_histories()

    # Reference: the no-statsmodels heuristic score
    monkeypatch.setattr(bps, "coint", None)
    monkeypatch.setattr(bps, "adfuller", None)
    heuristic = bps._pair_cointegration_score("A", "B", histories)

    # Strict path raising internally must land on the same heuristic score
    def _boom(*args, **kwargs):
        raise RuntimeError("stats unavailable")

    monkeypatch.setattr(bps, "coint", _boom)
    assert bps._pair_cointegration_score("A", "B", histories) == pytest.approx(
        heuristic
    )


def test_pair_cointegration_score_heuristic_fallback_without_statsmodels(
    monkeypatch,
):
    histories = _coint_histories()

    monkeypatch.setattr(bps, "coint", None)
    monkeypatch.setattr(bps, "adfuller", None)

    score = bps._pair_cointegration_score("A", "B", histories)
    # |correlation| in [0,1] plus mean-reversion component capped at 1.0
    assert 0.0 < score <= 2.0

    # Zero-variance quote series -> unusable on the fallback path too
    flat = {"A": histories["A"], "FLAT": _hist(np.full(120, 5.0))}
    assert bps._pair_cointegration_score("A", "FLAT", flat) == -1e9


def test_prioritize_pairs_by_cointegration_orders_by_score():
    histories = _coint_histories()
    pairs = [("C", "D"), ("A", "B")]

    ranked = bps._prioritize_pairs_by_cointegration(pairs, histories)

    assert ranked[0] == ("A", "B")
    assert bps._prioritize_pairs_by_cointegration([], histories) == []
    assert bps._prioritize_pairs_by_cointegration(pairs, {}) == pairs


# ------------------------------------------------------------- dispatch


def test_prioritize_pairs_dispatches_by_mode(monkeypatch):
    pairs = [("A", "B"), ("C", "D")]
    market_map = {
        "A": {"volume24H": 10},
        "B": {"volume24H": 1},
        "C": {"volume24H": 5},
        "D": {"volume24H": 5},
    }

    # input mode returns the plan untouched
    assert bps._prioritize_pairs(pairs, "input", market_map, {}) == pairs

    # liquidity mode sorts by combined volume (A/B = 11 beats C/D = 10)
    assert bps._prioritize_pairs(pairs, "liquidity", market_map, {})[0] == ("A", "B")

    # volatility / cointegration modes route to their engines
    monkeypatch.setattr(
        bps,
        "_prioritize_pairs_by_volatility",
        lambda p, h: list(reversed(p)),
    )
    assert bps._prioritize_pairs(pairs, "volatility", market_map, {}) == list(
        reversed(pairs)
    )

    histories = _coint_histories()
    assert bps._prioritize_pairs(pairs, "cointegration", market_map, histories)[0] == (
        "A",
        "B",
    )
