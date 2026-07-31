"""Optional pair prioritization for existing cointegration pairs."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from src.trading.arbitrage_observability import increment_metric
from src.trading.arbitrage_runtime_config import pair_priority_stale_seconds


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _pair_value(pair: Any, key: str, default: Any = None) -> Any:
    if isinstance(pair, dict):
        return pair.get(key, default)
    return getattr(pair, key, default)


def _pair_label(pair: Any) -> str:
    return f"{_pair_value(pair, 'base_market', '')}/{_pair_value(pair, 'quote_market', '')}"


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_pair_analysis_stale(pair: Any, *, now: datetime | None = None) -> bool:
    stale_after = _safe_float(pair_priority_stale_seconds(), 86400.0)
    if stale_after <= 0:
        return False
    timestamp = _parse_timestamp(_pair_value(pair, "analysis_timestamp"))
    if timestamp is None:
        return True
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return (
        reference.astimezone(timezone.utc) - timestamp
    ).total_seconds() > stale_after


def _extract_market_liquidity(market_payload: Any) -> float:
    if not isinstance(market_payload, dict):
        return 0.0
    candidates = (
        "volume24H",
        "volume24h",
        "volume",
        "baseVolume",
        "baseVolume24H",
        "notionalVolume24H",
        "notional24H",
        "turnover24H",
    )
    return max(
        (_safe_float(market_payload.get(field), 0.0) for field in candidates),
        default=0.0,
    )


def _scaled_liquidity_score(value: float) -> float:
    if value <= 0:
        return 0.0
    return min(1.0, math.log10(value + 1.0) / 8.0)


@dataclass(frozen=True)
class PairPriorityScore:
    pair: str
    score: float
    components: Dict[str, float]
    explanation: List[str]


def score_pair(
    pair: Any, market_map: Dict[str, Any] | None = None
) -> PairPriorityScore:
    base = str(_pair_value(pair, "base_market", "") or "")
    quote = str(_pair_value(pair, "quote_market", "") or "")
    market_map = market_map or {}

    z_mean = abs(_safe_float(_pair_value(pair, "z_score_mean"), 0.0))
    z_std = abs(_safe_float(_pair_value(pair, "z_score_std"), 0.0))
    confidence = _safe_float(_pair_value(pair, "confidence_score"), 0.0)
    zero_crossings = _safe_float(_pair_value(pair, "zero_crossings"), 0.0)
    half_life = max(0.0, _safe_float(_pair_value(pair, "half_life"), 0.0))

    base_liquidity = _extract_market_liquidity(market_map.get(base, {}))
    quote_liquidity = _extract_market_liquidity(market_map.get(quote, {}))
    liquidity_score = _scaled_liquidity_score(base_liquidity + quote_liquidity)

    stale = is_pair_analysis_stale(pair)
    if stale:
        increment_metric("stale_data_detected_total")

    components = {
        "spread_potential_score": min(2.0, z_mean + z_std),
        "volume_score": liquidity_score,
        "liquidity_score": liquidity_score,
        "volatility_score": min(1.0, z_std),
        "historical_opportunity_score": min(1.0, max(0.0, confidence))
        + min(0.5, zero_crossings / 20.0),
        "slippage_risk": (
            0.25 if liquidity_score <= 0 else max(0.0, 0.25 - liquidity_score * 0.25)
        ),
        "stale_data_penalty": 1.0 if stale else 0.0,
        "api_cost_penalty": 0.05 if stale else 0.0,
        "half_life_penalty": min(1.0, half_life / 48.0),
    }
    score = (
        components["spread_potential_score"]
        + components["volume_score"]
        + components["liquidity_score"]
        + components["volatility_score"]
        + components["historical_opportunity_score"]
        - components["slippage_risk"]
        - components["stale_data_penalty"]
        - components["api_cost_penalty"]
        - components["half_life_penalty"]
    )

    explanation = [
        f"confidence={confidence:.3f}",
        f"z_std={z_std:.3f}",
        f"zero_crossings={zero_crossings:.0f}",
    ]
    if liquidity_score > 0:
        explanation.append(f"liquidity_score={liquidity_score:.3f}")
    if stale:
        explanation.append("analysis_stale")

    return PairPriorityScore(
        pair=_pair_label(pair),
        score=float(score),
        components=components,
        explanation=explanation,
    )


def prioritize_pairs(
    pairs: Iterable[Any],
    *,
    market_map: Dict[str, Any] | None = None,
    max_pairs: int = 0,
) -> Tuple[List[Any], List[PairPriorityScore]]:
    scored = [(pair, score_pair(pair, market_map)) for pair in pairs]
    scored.sort(key=lambda item: item[1].score, reverse=True)
    if max_pairs > 0:
        skipped = max(0, len(scored) - max_pairs)
        if skipped:
            increment_metric("pair_candidates_skipped_total", skipped)
        scored = scored[:max_pairs]
    return [item[0] for item in scored], [item[1] for item in scored]
