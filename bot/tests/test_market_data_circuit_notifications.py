"""Operator-alert behavior for the circuit breaker that guards dYdX market data.

The ad-hoc breaker wiring (and its ``_notify_circuit_breaker_open`` /
``_send_error_notification`` helpers) previously lived in
``src/trading/market_data.py``. It has migrated to the centralized framework in
``src/infrastructure/resilience``; these tests now pin the operator-facing alert
contract (title / category / severity / fail-count wording) and the best-effort
swallowing of notifier failures at that new home.
"""

from __future__ import annotations

import src.infrastructure.resilience as resilience
from src.infrastructure.resilience.breakers import (
    _default_breaker_open_notifier,
    _fire_breaker_open_alert,
)


def test_default_notifier_sends_critical_dydx_alert(monkeypatch):
    calls = []

    def _fake_send_error_notification(
        error_type, error_details, is_critical=False, category=None
    ):
        calls.append(
            {
                "error_type": error_type,
                "error_details": error_details,
                "is_critical": is_critical,
                "category": category,
            }
        )
        return True

    # The default notifier imports send_error_notification lazily from the
    # notifications module; patch it there.
    import src.shared.notifications as notifications_mod

    monkeypatch.setattr(
        notifications_mod, "send_error_notification", _fake_send_error_notification
    )

    _default_breaker_open_notifier("dydx_indexer", 4)

    assert len(calls) == 1
    assert calls[0]["error_type"] == "dYdX circuit breaker open"
    assert "4 consecutive failures" in calls[0]["error_details"]
    assert calls[0]["is_critical"] is True
    assert calls[0]["category"] == "dydx_circuit_open"


def test_failing_open_notifier_is_swallowed():
    """A raising open-notifier must never escape the breaker state machine."""

    def _failing_notifier(_service, _count):
        raise RuntimeError("notifier transport unavailable")

    resilience.set_breaker_open_notifier(_failing_notifier)
    try:
        # Must not raise (best-effort alert isolation).
        _fire_breaker_open_alert("dydx_indexer", 3)
    finally:
        resilience.set_breaker_open_notifier(None)
