"""Tests for the centralized circuit-breaker framework (``src.infrastructure.resilience``).

The autouse ``_isolate_circuit_breakers`` fixture in ``conftest.py`` disables all
breakers by default so the rest of the suite stays deterministic. These tests
re-enable specific breakers (via env + ``reset_breakers()``) to exercise the real
pybreaker state machine. No real network is used — failure injection is via
``httpx`` error objects and plain exceptions.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from src.exceptions import CircuitBreakerOpenError, ExternalServiceError
from src.infrastructure import resilience

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _enable(monkeypatch, service: str, *, fail_max: int = 2, reset_timeout: int = 1):
    """Re-enable a named breaker with small thresholds and rebuild its handle."""
    prefix = {"dydx_indexer": "DYDX_INDEXER", "telegram": "TELEGRAM", "loki": "LOKI"}[
        service
    ]
    monkeypatch.setenv(f"{prefix}_CIRCUIT_ENABLED", "true")
    monkeypatch.setenv(f"{prefix}_CIRCUIT_FAIL_MAX", str(fail_max))
    monkeypatch.setenv(f"{prefix}_CIRCUIT_RESET_TIMEOUT", str(reset_timeout))
    resilience.reset_breakers()
    return resilience.get_breaker(service)


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://indexer.test/")
    response = httpx.Response(status)
    return httpx.HTTPStatusError(f"status {status}", request=request, response=response)


# --------------------------------------------------------------------------- #
# Async breaker: open / short-circuit / typed error
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_open_after_fail_max_then_short_circuits(monkeypatch):
    _enable(monkeypatch, "dydx_indexer", fail_max=2)

    async def conn_error():
        raise httpx.ConnectError("boom")

    # fail_max=2 -> first failure counted, second failure trips the circuit
    # (the tripping call raises CircuitBreakerOpenError, not the original error).
    for _ in range(2):
        with pytest.raises((httpx.ConnectError, CircuitBreakerOpenError)):
            await resilience.call_async("dydx_indexer", conn_error)

    assert resilience.breaker_states()["dydx_indexer"]["state"] == "open"

    # Open breaker short-circuits without invoking the coroutine.
    invoked = False

    async def should_not_run():
        nonlocal invoked
        invoked = True
        return "nope"

    with pytest.raises(CircuitBreakerOpenError) as ei:
        await resilience.call_async("dydx_indexer", should_not_run)

    assert invoked is False
    assert ei.value.service == "dydx_indexer"
    assert isinstance(ei.value, ExternalServiceError)
    assert ei.value.__cause__ is not None  # pybreaker.CircuitBreakerError chained


# --------------------------------------------------------------------------- #
# Exclude predicate: 4xx (except 429) excluded; 5xx / 429 / transport trip
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_client_http_errors_do_not_trip(monkeypatch):
    _enable(monkeypatch, "dydx_indexer", fail_max=2)

    async def not_found():
        raise _http_status_error(404)

    for _ in range(5):
        with pytest.raises(httpx.HTTPStatusError):
            await resilience.call_async("dydx_indexer", not_found)

    state = resilience.breaker_states()["dydx_indexer"]
    assert state["state"] == "closed"
    assert state["fail_counter"] == 0


@pytest.mark.asyncio
async def test_5xx_and_429_do_trip(monkeypatch):
    _enable(monkeypatch, "dydx_indexer", fail_max=3)

    async def server_error():
        raise _http_status_error(503)

    for _ in range(3):
        with pytest.raises((httpx.HTTPStatusError, CircuitBreakerOpenError)):
            await resilience.call_async("dydx_indexer", server_error)

    assert resilience.breaker_states()["dydx_indexer"]["state"] == "open"


@pytest.mark.asyncio
async def test_429_trips(monkeypatch):
    _enable(monkeypatch, "dydx_indexer", fail_max=2)

    async def rate_limited():
        raise _http_status_error(429)

    for _ in range(2):
        with pytest.raises((httpx.HTTPStatusError, CircuitBreakerOpenError)):
            await resilience.call_async("dydx_indexer", rate_limited)

    assert resilience.breaker_states()["dydx_indexer"]["state"] == "open"


# --------------------------------------------------------------------------- #
# Half-open recovery
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_half_open_recovery(monkeypatch):
    _enable(monkeypatch, "dydx_indexer", fail_max=2, reset_timeout=1)

    async def fail():
        raise httpx.ConnectError("boom")

    for _ in range(2):
        with pytest.raises((httpx.ConnectError, CircuitBreakerOpenError)):
            await resilience.call_async("dydx_indexer", fail)
    assert resilience.breaker_states()["dydx_indexer"]["state"] == "open"

    await asyncio.sleep(1.15)  # past reset_timeout -> half-open

    async def ok():
        return 7

    result = await resilience.call_async("dydx_indexer", ok)
    assert result == 7
    assert resilience.breaker_states()["dydx_indexer"]["state"] == "closed"


# --------------------------------------------------------------------------- #
# Sync breaker + named-breaker isolation
# --------------------------------------------------------------------------- #


def test_sync_call_open_path_and_isolation(monkeypatch):
    _enable(monkeypatch, "telegram", fail_max=3)
    _enable(monkeypatch, "loki", fail_max=3)

    def boom():
        raise ConnectionError("x")

    for _ in range(4):
        try:
            resilience.call("telegram", boom)
        except (ConnectionError, CircuitBreakerOpenError):
            pass

    assert resilience.breaker_states()["telegram"]["state"] == "open"
    # Loki is a separate instance and stays closed.
    assert resilience.breaker_states()["loki"]["state"] == "closed"

    with pytest.raises(CircuitBreakerOpenError):
        resilience.call("telegram", lambda: "nope")


# --------------------------------------------------------------------------- #
# Disabled / pybreaker-absent -> noop passthrough
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_disabled_breaker_is_noop(monkeypatch):
    monkeypatch.setenv("DYDX_INDEXER_CIRCUIT_ENABLED", "false")
    resilience.reset_breakers()
    assert resilience.get_breaker("dydx_indexer").circuit is None

    async def ok():
        return 21

    assert await resilience.call_async("dydx_indexer", ok) == 21

    async def boom():
        raise ValueError("real error")

    with pytest.raises(ValueError):  # original error propagates, not breaker error
        await resilience.call_async("dydx_indexer", boom)


def test_pybreaker_absent_is_noop(monkeypatch):
    from src.infrastructure.resilience import breakers as breakers_mod

    monkeypatch.setattr(breakers_mod, "_PYBREAKER_AVAILABLE", False)
    monkeypatch.setenv("DYDX_INDEXER_CIRCUIT_ENABLED", "true")
    resilience.reset_breakers()
    assert resilience.get_breaker("dydx_indexer").circuit is None
    assert resilience.call("dydx_indexer", lambda v: v * 2, 5) == 10


# --------------------------------------------------------------------------- #
# Config: legacy DYDX_CIRCUIT_* env vars honored for dydx_indexer
# --------------------------------------------------------------------------- #


def test_legacy_dydx_env_vars_honored(monkeypatch):
    monkeypatch.setenv("DYDX_INDEXER_CIRCUIT_ENABLED", "true")
    monkeypatch.setenv("DYDX_CIRCUIT_FAIL_MAX", "7")
    monkeypatch.setenv("DYDX_CIRCUIT_RESET_TIMEOUT", "42")
    resilience.reset_breakers()
    handle = resilience.get_breaker("dydx_indexer")
    assert handle.fail_max == 7
    assert handle.reset_timeout == 42


def test_new_alias_env_vars_honored(monkeypatch):
    monkeypatch.setenv("DYDX_INDEXER_CIRCUIT_ENABLED", "true")
    monkeypatch.setenv("DYDX_INDEXER_CIRCUIT_FAIL_MAX", "9")
    monkeypatch.setenv("DYDX_INDEXER_CIRCUIT_RESET_TIMEOUT", "55")
    resilience.reset_breakers()
    handle = resilience.get_breaker("dydx_indexer")
    assert handle.fail_max == 9
    assert handle.reset_timeout == 55


# --------------------------------------------------------------------------- #
# Registry / accessor behavior
# --------------------------------------------------------------------------- #


def test_unknown_breaker_raises():
    with pytest.raises(ValueError):
        resilience.get_breaker("does_not_exist")


def test_breaker_states_shape(monkeypatch):
    monkeypatch.setenv("DYDX_INDEXER_CIRCUIT_ENABLED", "false")
    monkeypatch.setenv("TELEGRAM_CIRCUIT_ENABLED", "true")
    monkeypatch.setenv("LOKI_CIRCUIT_ENABLED", "true")
    resilience.reset_breakers()
    states = resilience.breaker_states()
    assert set(states) == {"dydx_indexer", "telegram", "loki"}
    for entry in states.values():
        assert {
            "enabled",
            "backend",
            "state",
            "fail_counter",
            "fail_max",
            "reset_timeout",
            "label",
        } <= set(entry)
    assert states["dydx_indexer"]["enabled"] is False
    assert states["dydx_indexer"]["backend"] == "noop"
    assert states["telegram"]["enabled"] is True
    assert states["telegram"]["backend"] == "pybreaker"


# --------------------------------------------------------------------------- #
# Open-state alert notifier
# --------------------------------------------------------------------------- #


def test_open_notifier_fires_on_trip(monkeypatch):
    fired = []
    resilience.set_breaker_open_notifier(
        lambda service, count: fired.append((service, count))
    )
    _enable(monkeypatch, "telegram", fail_max=2)
    try:
        for _ in range(3):
            try:
                resilience.call(
                    "telegram", lambda: (_ for _ in ()).throw(ConnectionError("x"))
                )
            except (ConnectionError, CircuitBreakerOpenError):
                pass
        assert resilience.breaker_states()["telegram"]["state"] == "open"
        assert ("telegram", 2) in fired
    finally:
        resilience.set_breaker_open_notifier(None)


def test_open_notifier_swallows_failing_notifier(monkeypatch):
    def bad_notifier(_service, _count):
        raise RuntimeError("notifier down")

    resilience.set_breaker_open_notifier(bad_notifier)
    _enable(monkeypatch, "loki", fail_max=2)
    try:
        # Tripping must not raise despite the failing notifier.
        for _ in range(3):
            try:
                resilience.call(
                    "loki", lambda: (_ for _ in ()).throw(ConnectionError("x"))
                )
            except (ConnectionError, CircuitBreakerOpenError):
                pass
        assert resilience.breaker_states()["loki"]["state"] == "open"
    finally:
        resilience.set_breaker_open_notifier(None)
