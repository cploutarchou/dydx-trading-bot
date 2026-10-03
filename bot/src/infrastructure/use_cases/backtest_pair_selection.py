"""Pair-prioritization / scoring engine for backtests.

Extracted from :mod:`src.infrastructure.use_cases.service_backtest` (Phase 2 of the
backtest-service decomposition). Decides which market pairs to backtest and in what
order, supporting three modes: ``liquidity``, ``volatility``, and ``cointegration``
(the strict statistical-arbitrage ranking via Engle-Granger cointegration + ADF
stationarity, with a heuristic fallback when ``statsmodels`` is unavailable or a pair
fails the statistical path).

These were ``@staticmethod`` / ``@classmethod`` on ``BacktestService`` taking explicit
arguments (no instance state), so they convert cleanly to module-level functions.
``BacktestService`` keeps thin delegating methods only for the symbols called from
outside this module (``_prioritize_pairs``, ``_safe_float``, ``_align_series``,
``_normalize_pair_selection_mode``); the internal helpers live entirely here.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np

from src.infrastructure.use_cases.backtest_models import _linregress_slope

try:
    # Correct module is `statsmodels.tsa.stattools`; the original `statools`
    # spelling silently failed the import and permanently forced every
    # cointegration-mode ranking onto the heuristic fallback.
    from statsmodels.tsa.stattools import adfuller, coint
except Exception:  # pragma: no cover - statsmodels missing in minimal envs
    adfuller = None
    coint = None


def _clamp01(value: float) -> float:
    """Clamp a value to the [0.0, 1.0] range (used to bound p-values)."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _align_series(
    market_1: Dict[str, float],
    market_2: Dict[str, float],
) -> tuple[list[str], np.ndarray, np.ndarray]:
    common = sorted(set(market_1.keys()) & set(market_2.keys()))
    p1 = np.array([market_1[k] for k in common], dtype=np.float64)
    p2 = np.array([market_2[k] for k in common], dtype=np.float64)
    return common, p1, p2


def _normalize_pair_selection_mode(mode: Any) -> str:
    raw = str(mode or "liquidity").strip().lower()
    aliases = {
        "liquidity": "liquidity",
        "volume": "liquidity",
        "volatility": "volatility",
        "cointegration": "cointegration",
        "input": "input",
        "none": "input",
        "order": "input",
        "original": "input",
    }
    return aliases.get(raw, "liquidity")


def _extract_market_liquidity(market_payload: Any) -> float:
    """Return a best-effort liquidity score from market metadata."""
    if not isinstance(market_payload, dict):
        return 0.0

    # dYdX payload fields can vary by endpoint/version; prefer 24h volumes when present.
    candidates = [
        market_payload.get("volume24H"),
        market_payload.get("volume24h"),
        market_payload.get("volume"),
        market_payload.get("baseVolume"),
        market_payload.get("baseVolume24H"),
        market_payload.get("notionalVolume24H"),
        market_payload.get("notional24H"),
        market_payload.get("turnover24H"),
    ]

    best = 0.0
    for raw in candidates:
        best = max(best, _safe_float(raw, 0.0))
    return best


def _prioritize_pairs_by_liquidity(
    pair_markets: List[tuple[str, str]],
    market_map: Dict[str, Any],
) -> List[tuple[str, str]]:
    """Sort pairs by combined market liquidity descending, preserving stable order for ties."""
    if not pair_markets or not market_map:
        return pair_markets

    def score(pair: tuple[str, str]) -> float:
        a, b = pair
        a_info = market_map.get(a, {})
        b_info = market_map.get(b, {})
        return _extract_market_liquidity(a_info) + _extract_market_liquidity(b_info)

    # Python sort is stable, so equal scores preserve original pair order.
    return sorted(pair_markets, key=score, reverse=True)


def _compute_market_volatility(market_history: Dict[str, float]) -> float:
    if not isinstance(market_history, dict) or len(market_history) < 3:
        return 0.0
    prices = np.array(list(market_history.values()), dtype=np.float64)
    if len(prices) < 3:
        return 0.0
    returns = np.diff(prices) / np.maximum(prices[:-1], 1e-12)
    if len(returns) == 0:
        return 0.0
    return float(np.nanstd(returns))


def _prioritize_pairs_by_volatility(
    pair_markets: List[tuple[str, str]],
    history_by_market: Dict[str, Dict[str, float]],
) -> List[tuple[str, str]]:
    if not pair_markets or not history_by_market:
        return pair_markets

    vol_cache: Dict[str, float] = {
        market: _compute_market_volatility(hist)
        for market, hist in history_by_market.items()
    }

    def score(pair: tuple[str, str]) -> float:
        a, b = pair
        return vol_cache.get(a, 0.0) + vol_cache.get(b, 0.0)

    return sorted(pair_markets, key=score, reverse=True)


def _pair_cointegration_score(
    market_a: str,
    market_b: str,
    history_by_market: Dict[str, Dict[str, float]],
) -> float:
    h1 = history_by_market.get(market_a, {})
    h2 = history_by_market.get(market_b, {})
    timestamps, p1, p2 = _align_series(h1, h2)
    if len(timestamps) < 48:
        return -1e9

    # Statsmodels path: strict ranking using cointegration + stationarity tests.
    if coint is not None and adfuller is not None:
        try:
            if np.min(p1) <= 0 or np.min(p2) <= 0:
                return -1e9

            log_p1 = np.log(p1)
            log_p2 = np.log(p2)

            coint_stat, coint_pvalue, _ = coint(log_p1, log_p2)

            # Estimate hedge ratio on log prices and test spread stationarity.
            hedge_ratio = _linregress_slope(log_p2, log_p1)
            spread = log_p1 - (hedge_ratio * log_p2)

            adf_stat, adf_pvalue, *_ = adfuller(spread, autolag="AIC")

            # Half-life estimate from OU approximation: dS_t = k*S_{t-1}+e_t.
            lagged = spread[:-1]
            delta = np.diff(spread)
            if len(lagged) < 3 or np.std(lagged) <= 1e-12:
                return -1e9

            kappa = _linregress_slope(lagged, delta)
            if kappa >= 0:
                half_life = float("inf")
            else:
                half_life = -math.log(2.0) / kappa

            # Return-correlation as a secondary quality signal.
            r1 = np.diff(log_p1)
            r2 = np.diff(log_p2)
            corr = float(np.corrcoef(r1, r2)[0, 1]) if len(r1) > 1 else 0.0
            if math.isnan(corr):
                corr = 0.0

            # Strict penalty: deprioritize pairs that fail significance thresholds.
            if coint_pvalue > 0.10 or adf_pvalue > 0.10:
                return -100.0 - float(coint_pvalue) - float(adf_pvalue)

            # Half-life gate for live/backtest parity: the live pipeline
            # (cointegration.store_cointegration_results) only accepts pairs
            # with 0 < half_life <= MAX_HALF_LIFE. Pairs the live bot would
            # never trade must not rank as tradable in backtests.
            from src.constants import MAX_HALF_LIFE

            if not np.isfinite(half_life) or not (
                0 < half_life <= float(MAX_HALF_LIFE)
            ):
                return -50.0 - (0.0 if not np.isfinite(half_life) else float(half_life))

            coint_score = 1.0 - _clamp01(float(coint_pvalue))
            adf_score = 1.0 - _clamp01(float(adf_pvalue))
            half_life_score = (
                0.0 if not np.isfinite(half_life) else 1.0 / (1.0 + max(0.0, half_life))
            )
            corr_score = abs(corr)

            # Weighted blend (tests dominate, dynamics refine ties).
            score = (2.5 * coint_score) + (2.5 * adf_score) + (0.75 * corr_score)
            score += 0.5 * half_life_score

            # Small tie-breaker with test statistics where more negative is better.
            score += 0.01 * abs(float(coint_stat))
            score += 0.01 * abs(float(adf_stat))
            return float(score)
        except Exception:
            # Fall through to heuristic fallback if statistical path fails.
            pass

    # Fallback heuristic when strict tests are unavailable.
    var_b = float(np.var(p2))
    if var_b <= 1e-12:
        return -1e9
    hedge_ratio = float(np.cov(p1, p2)[0, 1] / var_b)
    spread = p1 - (hedge_ratio * p2)

    spread_std = float(np.std(spread))
    if spread_std <= 1e-12:
        return -1e9

    diff_std = float(np.std(np.diff(spread))) if len(spread) > 1 else 0.0
    corr = float(np.corrcoef(p1, p2)[0, 1]) if len(p1) > 1 else 0.0
    if math.isnan(corr):
        corr = 0.0

    # Heuristic: prefer high absolute correlation and faster spread dynamics.
    mean_reversion_component = min(1.0, diff_std / max(spread_std, 1e-12))
    return abs(corr) + mean_reversion_component


def _prioritize_pairs_by_cointegration(
    pair_markets: List[tuple[str, str]],
    history_by_market: Dict[str, Dict[str, float]],
) -> List[tuple[str, str]]:
    if not pair_markets or not history_by_market:
        return pair_markets

    def score(pair: tuple[str, str]) -> float:
        return _pair_cointegration_score(pair[0], pair[1], history_by_market)

    return sorted(pair_markets, key=score, reverse=True)


def _prioritize_pairs(
    pair_markets: List[tuple[str, str]],
    mode: str,
    market_map: Dict[str, Any],
    history_by_market: Dict[str, Dict[str, float]],
) -> List[tuple[str, str]]:
    normalized_mode = _normalize_pair_selection_mode(mode)
    if normalized_mode == "input":
        return pair_markets
    if normalized_mode == "volatility":
        return _prioritize_pairs_by_volatility(pair_markets, history_by_market)
    if normalized_mode == "cointegration":
        return _prioritize_pairs_by_cointegration(pair_markets, history_by_market)
    return _prioritize_pairs_by_liquidity(pair_markets, market_map)


def _truncate_history_for_selection(
    history: Dict[str, float],
) -> Dict[str, float]:
    """Keep only the first half (by timestamp order) of a market's history.

    Pair ranking must run on the calibration window so selection is
    out-of-sample relative to the simulated trading window; ranking on the
    full sample and then trading the same sample is in-sample selection
    bias that overstates backtest results.
    """
    if not history:
        return {}
    ordered = sorted(history.items(), key=lambda item: item[0])
    cut = max(1, len(ordered) // 2)
    return dict(ordered[:cut])
