"""Centralized circuit-breaker framework for external service calls.

Provides a registry of named breakers (``dydx_indexer``, ``telegram``, ``loki``)
backed by pybreaker, with async + sync entry points, a graceful no-op fallback
when pybreaker is absent or a breaker is disabled, operator alerting on OPEN
transitions, and a live-state accessor for monitoring. See
:mod:`src.infrastructure.resilience.breakers` for the design contract.
"""

from src.exceptions import CircuitBreakerOpenError

from .breakers import (
    breaker_states,
    call,
    call_async,
    get_breaker,
    reset_breakers,
    set_breaker_open_notifier,
)

__all__ = [
    "CircuitBreakerOpenError",
    "breaker_states",
    "call",
    "call_async",
    "get_breaker",
    "reset_breakers",
    "set_breaker_open_notifier",
]
