"""Lightweight in-process counters for arbitrage runtime efficiency."""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict

METRIC_NAMES = (
    "arbitrage_scan_cycles_total",
    "exchange_api_calls_total",
    "exchange_api_calls_saved_total",
    "duplicate_api_calls_avoided_total",
    "pair_candidates_total",
    "pair_candidates_skipped_total",
    "opportunities_detected_total",
    "opportunities_rejected_total",
    "opportunities_executed_total",
    "stale_data_detected_total",
    "provider_errors_total",
    "cache_hits_total",
    "cache_misses_total",
    "websocket_reconnects_total",
)

_COUNTERS: defaultdict[str, float] = defaultdict(float)
_REJECTION_REASONS: defaultdict[str, float] = defaultdict(float)
_LOCK = threading.Lock()
_STARTED_AT = datetime.now(timezone.utc)


def increment_metric(name: str, amount: float = 1.0) -> None:
    if name not in METRIC_NAMES:
        return
    with _LOCK:
        _COUNTERS[name] += amount


def record_rejection(reason: str, amount: float = 1.0) -> None:
    """Increment total rejection count and optional reason bucket."""
    normalized = str(reason or "unspecified").strip().lower().replace(" ", "_")
    increment_metric("opportunities_rejected_total", amount=amount)
    with _LOCK:
        _REJECTION_REASONS[normalized] += amount


def snapshot_metrics(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    with _LOCK:
        counters = {name: _COUNTERS.get(name, 0.0) for name in METRIC_NAMES}
        rejection_reasons = dict(sorted(_REJECTION_REASONS.items()))
    payload: Dict[str, Any] = {
        "started_at": _STARTED_AT.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "counters": counters,
        "rejection_reasons": rejection_reasons,
    }
    if extra:
        payload.update(extra)
    return payload


def reset_metrics() -> None:
    with _LOCK:
        _COUNTERS.clear()
        _REJECTION_REASONS.clear()
