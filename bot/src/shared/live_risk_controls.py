"""Validation helpers for live-runtime risk controls.

Sprint 1 policy:
- Enforce only controls that are proven in the live runtime.
- Reject controls that are still advisory/placeholder so operators do not get
  a false sense of safety.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_UNSUPPORTED_LIVE_RISK_FIELDS = {
    "max_drawdown_pct": (
        "max_drawdown_pct is not enforced by the live runtime and is rejected until "
        "bot-level drawdown policy is implemented."
    ),
    "trailing_stop_pct": (
        "trailing_stop_pct is not enforced by the live runtime and is rejected until "
        "per-position trailing stop logic is implemented."
    ),
    "capital_allocation_usd": (
        "capital_allocation_usd is not enforced by the live runtime and is rejected "
        "until capital-allocation checks are enforced during live order entry."
    ),
}


def _float_value(payload: Mapping[str, Any], field: str) -> float:
    raw = payload.get(field)
    if raw in (None, "", False):
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric; received {raw!r}") from exc


def validate_live_risk_controls(payload: Mapping[str, Any]) -> list[str]:
    """Return validation errors for unsupported live-runtime risk controls."""
    errors: list[str] = []
    for field, message in _UNSUPPORTED_LIVE_RISK_FIELDS.items():
        if _float_value(payload, field) > 0:
            errors.append(message)
    return errors


def assert_supported_live_risk_controls(payload: Mapping[str, Any]) -> None:
    errors = validate_live_risk_controls(payload)
    if errors:
        raise ValueError(" ".join(errors))
