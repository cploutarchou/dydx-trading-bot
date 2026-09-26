"""Runtime-configurable arbitrage improvement flags.

Environment variables remain the startup defaults. Backend/admin settings may
override these values at runtime through the bot API without changing trading
rules unless a feature flag is explicitly enabled.
"""

from __future__ import annotations

import os
from threading import RLock
from typing import Any, Dict

from src.constants import (
    ARBITRAGE_IMPROVEMENTS_ENABLED,
    AUTO_EXECUTION_CHANGES_ENABLED,
    COST_GATE_EDGE_MULTIPLE,
    COST_GATE_ENABLED,
    COST_GATE_SLIPPAGE_BPS,
    COST_GATE_SLIPPAGE_BPS_DEFAULT,
    COST_GATE_TAKER_FEE,
    DEFILLAMA_SIGNALS_ENABLED,
    FUNDING_SAME_SIDE_THRESHOLD,
    FUNDING_SAME_SIDE_THRESHOLD_DEFAULT,
    NEWS_SIGNALS_ENABLED,
    PAIR_PRIORITY_ENGINE_ENABLED,
    POLYMARKET_SIGNALS_ENABLED,
)
from src.trading.entry_cost_gate import (
    DEFAULT_EDGE_MULTIPLE,
    DEFAULT_TAKER_FEE,
    EDGE_MULTIPLE_BOUNDS,
    FUNDING_THRESHOLD_BOUNDS,
    SLIPPAGE_BPS_BOUNDS,
    TAKER_FEE_BOUNDS,
    clamp_setting,
)

FEATURE_FLAG_KEYS = (
    "ARBITRAGE_IMPROVEMENTS_ENABLED",
    "PAIR_PRIORITY_ENGINE_ENABLED",
    "POLYMARKET_SIGNALS_ENABLED",
    "DEFILLAMA_SIGNALS_ENABLED",
    "NEWS_SIGNALS_ENABLED",
    "AUTO_EXECUTION_CHANGES_ENABLED",
    "COST_GATE_ENABLED",
)

INTEGER_SETTING_KEYS = ("PAIR_PRIORITY_MAX_PAIRS",)
FLOAT_SETTING_KEYS = (
    "PAIR_PRIORITY_STALE_SECONDS",
    "COST_GATE_EDGE_MULTIPLE",
    "COST_GATE_TAKER_FEE",
    "COST_GATE_SLIPPAGE_BPS",
    "FUNDING_SAME_SIDE_THRESHOLD",
)

# Explicit (lower, upper) clamps plus the built-in default used when a startup
# value is unparseable or non-finite. A bad runtime override falls back to the
# (clamped) startup default instead. Float settings without an entry keep the
# plain non-negative floor of ``_parse_float``.
_FLOAT_SETTING_CLAMPS: Dict[str, tuple[tuple[float, float], float]] = {
    "COST_GATE_EDGE_MULTIPLE": (EDGE_MULTIPLE_BOUNDS, DEFAULT_EDGE_MULTIPLE),
    "COST_GATE_TAKER_FEE": (TAKER_FEE_BOUNDS, DEFAULT_TAKER_FEE),
    "COST_GATE_SLIPPAGE_BPS": (SLIPPAGE_BPS_BOUNDS, COST_GATE_SLIPPAGE_BPS_DEFAULT),
    "FUNDING_SAME_SIDE_THRESHOLD": (
        FUNDING_THRESHOLD_BOUNDS,
        FUNDING_SAME_SIDE_THRESHOLD_DEFAULT,
    ),
}


def _clamp_float_setting(key: str, value: Any, fallback: Any = None) -> float:
    bounds, builtin_default = _FLOAT_SETTING_CLAMPS[key]
    return clamp_setting(
        value, bounds, builtin_default if fallback is None else fallback
    )


_DEFAULTS: Dict[str, Any] = {
    "ARBITRAGE_IMPROVEMENTS_ENABLED": ARBITRAGE_IMPROVEMENTS_ENABLED,
    "PAIR_PRIORITY_ENGINE_ENABLED": PAIR_PRIORITY_ENGINE_ENABLED,
    "POLYMARKET_SIGNALS_ENABLED": POLYMARKET_SIGNALS_ENABLED,
    "DEFILLAMA_SIGNALS_ENABLED": DEFILLAMA_SIGNALS_ENABLED,
    "NEWS_SIGNALS_ENABLED": NEWS_SIGNALS_ENABLED,
    "AUTO_EXECUTION_CHANGES_ENABLED": AUTO_EXECUTION_CHANGES_ENABLED,
    "PAIR_PRIORITY_MAX_PAIRS": int(os.getenv("PAIR_PRIORITY_MAX_PAIRS", "0") or "0"),
    "PAIR_PRIORITY_STALE_SECONDS": float(
        os.getenv("PAIR_PRIORITY_STALE_SECONDS", "86400") or "86400"
    ),
    "COST_GATE_ENABLED": COST_GATE_ENABLED,
    "COST_GATE_EDGE_MULTIPLE": _clamp_float_setting(
        "COST_GATE_EDGE_MULTIPLE", COST_GATE_EDGE_MULTIPLE
    ),
    "COST_GATE_TAKER_FEE": _clamp_float_setting(
        "COST_GATE_TAKER_FEE", COST_GATE_TAKER_FEE
    ),
    "COST_GATE_SLIPPAGE_BPS": _clamp_float_setting(
        "COST_GATE_SLIPPAGE_BPS", COST_GATE_SLIPPAGE_BPS
    ),
    "FUNDING_SAME_SIDE_THRESHOLD": _clamp_float_setting(
        "FUNDING_SAME_SIDE_THRESHOLD", FUNDING_SAME_SIDE_THRESHOLD
    ),
}

_overrides: Dict[str, Any] = {}
_lock = RLock()


def _parse_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return fallback


def _parse_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(0, parsed)


def _parse_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, parsed)


def get_runtime_settings() -> Dict[str, Any]:
    with _lock:
        settings = dict(_DEFAULTS)
        settings.update(_overrides)
    return settings


def get_feature_flags() -> Dict[str, bool]:
    settings = get_runtime_settings()
    return {key: bool(settings.get(key, False)) for key in FEATURE_FLAG_KEYS}


def update_runtime_settings(values: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        for key in FEATURE_FLAG_KEYS:
            if key in values:
                _overrides[key] = _parse_bool(values[key], bool(_DEFAULTS[key]))
        for key in INTEGER_SETTING_KEYS:
            if key in values:
                _overrides[key] = _parse_int(values[key], int(_DEFAULTS[key]))
        for key in FLOAT_SETTING_KEYS:
            if key in values:
                if key in _FLOAT_SETTING_CLAMPS:
                    _overrides[key] = _clamp_float_setting(
                        key, values[key], fallback=_DEFAULTS[key]
                    )
                else:
                    _overrides[key] = _parse_float(values[key], float(_DEFAULTS[key]))
    return get_runtime_settings()


def is_arbitrage_improvements_enabled() -> bool:
    return bool(get_runtime_settings()["ARBITRAGE_IMPROVEMENTS_ENABLED"])


def is_pair_priority_engine_enabled() -> bool:
    return bool(get_runtime_settings()["PAIR_PRIORITY_ENGINE_ENABLED"])


def pair_priority_max_pairs() -> int:
    return int(get_runtime_settings()["PAIR_PRIORITY_MAX_PAIRS"])


def pair_priority_stale_seconds() -> float:
    return float(get_runtime_settings()["PAIR_PRIORITY_STALE_SECONDS"])


def is_cost_gate_enabled(settings: Dict[str, Any] | None = None) -> bool:
    source = settings if settings is not None else get_runtime_settings()
    return bool(source.get("COST_GATE_ENABLED", False))
