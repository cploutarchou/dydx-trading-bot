from src.trading import market_data


def test_notify_circuit_breaker_open_sends_critical_telegram(monkeypatch):
    calls = []

    def _fake_send_error_notification(error_type, error_details, is_critical=False, category=None):
        calls.append(
            {
                "error_type": error_type,
                "error_details": error_details,
                "is_critical": is_critical,
                "category": category,
            }
        )
        return True

    monkeypatch.setattr(market_data, "_send_error_notification", _fake_send_error_notification)

    market_data._notify_circuit_breaker_open(4)

    assert len(calls) == 1
    assert calls[0]["error_type"] == "dYdX circuit breaker open"
    assert "4 consecutive failures" in calls[0]["error_details"]
    assert calls[0]["is_critical"] is True
    assert calls[0]["category"] == "dydx_circuit_open"


def test_notify_circuit_breaker_open_swallow_notifier_errors(monkeypatch):
    def _failing_notifier(*_args, **_kwargs):
        raise RuntimeError("telegram transport unavailable")

    monkeypatch.setattr(market_data, "_send_error_notification", _failing_notifier)

    # Must not raise (best-effort alerting)
    market_data._notify_circuit_breaker_open(3)
