"""Centralized circuit-breaker framework for external service calls.

Consolidates the ad-hoc pybreaker wiring that previously lived only in
``src/trading/market_data.py`` into a reusable registry of **named** breakers
with async + sync entry points, a graceful no-op fallback when pybreaker is
absent, operator alerting on state transitions, and a live-state accessor for
monitoring. Mirrors the storage-adapter conventions of
:mod:`src.infrastructure.cache` (per-service ``enabled`` flag, lazy registry,
``breaker_states()`` health accessor, graceful degradation).

Design contract
---------------
* Breakers are a **resilience optimization**, never a correctness mechanism for
  trading. A disabled breaker (``<SERVICE>_CIRCUIT_ENABLED=false``) or an absent
  pybreaker install always executes the call directly with zero overhead.
* There is exactly one broad catch — the best-effort alert-notifier guard in
  :func:`_fire_breaker_open_alert` — so a buggy/custom open-notifier can never
  corrupt the breaker state machine or crash the trading loop. It is intentional
  best-effort fault isolation and is counted by the broad-catch ratchet
  (``tests/test_exception_handling_ratchet.py``). Migrating the ad-hoc
  ``market_data`` breaker into this module removed two market_data catches and
  added one here, so the net effect is a ratchet reduction.
* pybreaker 1.4.x is used (pinned ``<2.0``). Its ``exclude`` accepts both
  exception types **and** predicate callables; we use a predicate for the dYdX
  indexer so client HTTP errors (4xx except 429 — e.g. 404 for a fresh account)
  do NOT trip the circuit, while transport errors, timeouts, 429, and 5xx DO.
* When a breaker is OPEN, :func:`call` / :func:`call_async` raise
  :class:`~src.exceptions.CircuitBreakerOpenError` (a typed bot exception) so
  callers can degrade per-dependency. The original ``pybreaker.CircuitBreakerError``
  is chained as ``__cause__``.

Named breakers: ``dydx_indexer``, ``telegram``, ``loki``. The dYdX indexer breaker
preserves the legacy ``DYDX_CIRCUIT_FAIL_MAX`` / ``DYDX_CIRCUIT_RESET_TIMEOUT`` env
var names (with ``DYDX_INDEXER_CIRCUIT_*`` as new preferred aliases) so existing
operator configs keep working unchanged.
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any, Awaitable, Callable, TypeVar

from loguru import logger

from src.exceptions import CircuitBreakerOpenError

T = TypeVar("T")

# --------------------------------------------------------------------------- #
# pybreaker availability (resolved once at import)
# --------------------------------------------------------------------------- #

_PYBREAKER_AVAILABLE = False
if importlib.util.find_spec("pybreaker") is not None:
    try:
        import pybreaker  # type: ignore[import]

        _PYBREAKER_AVAILABLE = True
    except ImportError:  # pragma: no cover - optional dependency
        _PYBREAKER_AVAILABLE = False

# Exception class matched in `except` clauses below. When pybreaker is absent,
# breakers are noop (circuit is None) and the except is never reached; the
# sentinel matches nothing so any other exception still propagates correctly.
_CIRCUIT_BREAKER_ERROR: type[BaseException]
if _PYBREAKER_AVAILABLE:
    _CIRCUIT_BREAKER_ERROR = pybreaker.CircuitBreakerError
else:  # pragma: no cover - optional dependency absent

    class _NeverRaisedError(Exception):
        """Placeholder so `except` resolves without pybreaker; never raised."""

    _CIRCUIT_BREAKER_ERROR = _NeverRaisedError


# --------------------------------------------------------------------------- #
# Failure predicates
# --------------------------------------------------------------------------- #


def _is_excluded_indexer_error(exc: BaseException) -> bool:
    """Return True for dYdX indexer errors that must NOT trip the circuit.

    Client-side HTTP errors (4xx except 429) reflect a bad request or missing
    resource — e.g. a 404 for a fresh testnet account, a 400/422 for a malformed
    query — not an outage, so pybreaker re-raises them unchanged without counting
    toward opening the circuit. Transport errors (``httpx.ConnectError`` /
    ``TimeoutException``), 429 rate-limiting, and 5xx responses are signals of
    system malfunction and DO count (predicate returns False).
    """
    try:
        import httpx  # type: ignore[import]
    except ImportError:  # pragma: no cover - httpx is a core dependency
        return False
    if isinstance(exc, httpx.HTTPStatusError):
        status = int(getattr(exc.response, "status_code", 0) or 0)
        # 4xx except 429 (rate limit) == client error, not an outage.
        return 400 <= status < 500 and status != 429
    return False


# --------------------------------------------------------------------------- #
# Per-service configuration
# --------------------------------------------------------------------------- #
#
# `fail_max_envs` / `reset_envs` are tried in order (first set wins) so the
# dYdX indexer breaker can honor the legacy DYDX_CIRCUIT_* names while also
# accepting the new DYDX_INDEXER_CIRCUIT_* aliases.

_SERVICE_SPECS: dict[str, dict[str, Any]] = {
    "dydx_indexer": {
        "label": "dYdX indexer",
        "alert_title": "dYdX circuit breaker open",
        "alert_category": "dydx_circuit_open",
        "enabled_env": "DYDX_INDEXER_CIRCUIT_ENABLED",
        "fail_max_envs": ("DYDX_CIRCUIT_FAIL_MAX", "DYDX_INDEXER_CIRCUIT_FAIL_MAX"),
        "reset_envs": (
            "DYDX_CIRCUIT_RESET_TIMEOUT",
            "DYDX_INDEXER_CIRCUIT_RESET_TIMEOUT",
        ),
        "fail_max_default": 3,
        "reset_default": 30,
        "exclude": (_is_excluded_indexer_error,),
    },
    "telegram": {
        "label": "Telegram",
        "alert_title": "Telegram circuit breaker open",
        "alert_category": "telegram_circuit_open",
        "enabled_env": "TELEGRAM_CIRCUIT_ENABLED",
        "fail_max_envs": ("TELEGRAM_CIRCUIT_FAIL_MAX",),
        "reset_envs": ("TELEGRAM_CIRCUIT_RESET_TIMEOUT",),
        "fail_max_default": 5,
        "reset_default": 60,
        "exclude": (),
    },
    "loki": {
        "label": "Loki",
        "alert_title": "Loki circuit breaker open",
        "alert_category": "loki_circuit_open",
        "enabled_env": "LOKI_CIRCUIT_ENABLED",
        "fail_max_envs": ("LOKI_CIRCUIT_FAIL_MAX",),
        "reset_envs": ("LOKI_CIRCUIT_RESET_TIMEOUT",),
        "fail_max_default": 5,
        "reset_default": 60,
        "exclude": (),
    },
}


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _first_env_int(names: tuple[str, ...], default: int) -> int:
    for name in names:
        raw = os.getenv(name)
        if raw is None or raw.strip() == "":
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    return default


# --------------------------------------------------------------------------- #
# Open-state alert notifier (swappable for tests)
# --------------------------------------------------------------------------- #
#
# The default notifier calls the (non-raising) Telegram `send_error_notification`.
# A custom notifier set via `set_breaker_open_notifier` may raise; `_fire_breaker_open_alert`
# swallows such errors so a faulty notifier can never break the breaker state machine.

_breaker_open_notifier: Callable[[str, int], None] | None = None


def set_breaker_open_notifier(fn: Callable[[str, int], None] | None) -> None:
    """Install a custom open-state notifier (tests / observability wiring)."""
    global _breaker_open_notifier
    _breaker_open_notifier = fn


def _default_breaker_open_notifier(service: str, fail_counter: int) -> None:
    """Best-effort operator alert when a named breaker transitions to OPEN."""
    spec = _SERVICE_SPECS.get(service, {})
    title = spec.get("alert_title", f"{service} circuit breaker open")
    category = spec.get("alert_category", f"{service}_circuit_open")
    label = spec.get("label", service)
    try:
        from src.shared.notifications import send_error_notification
    except ImportError:  # pragma: no cover - notifications is a core module
        logger.warning(
            "circuit_breaker_open_alert_skipped service={} (no notifier)", service
        )
        return
    delivered = send_error_notification(
        title,
        (
            f"{label} circuit opened after {fail_counter} consecutive failures. "
            "Calls to this dependency are temporarily paused until half-open recovery."
        ),
        is_critical=True,
        category=category,
    )
    if not delivered:
        logger.warning("circuit_breaker_open_alert_undelivered service={}", service)


def _fire_breaker_open_alert(service: str, fail_counter: int) -> None:
    """Invoke the open-state notifier, isolating any notifier failure."""
    notifier = _breaker_open_notifier or _default_breaker_open_notifier
    # Best-effort isolation: a faulty/custom notifier must never break the breaker
    # state machine. This is the one broad catch in the module (counted by the
    # broad-catch ratchet — see the module docstring). Kept on a single line so the
    # ratchet's text-based matcher sees it.
    try:
        notifier(service, fail_counter)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "circuit_breaker_open_notifier_failed service={} error={!r}", service, exc
        )


# --------------------------------------------------------------------------- #
# pybreaker listener (logging + alert on state transitions)
# --------------------------------------------------------------------------- #

if _PYBREAKER_AVAILABLE:

    class _BreakerStateListener(pybreaker.CircuitBreakerListener):  # type: ignore[misc]
        """Log every breaker state transition and alert operators on OPEN."""

        def state_change(self, cb, _old_state, new_state):  # type: ignore[override]
            name = cb.name or "breaker"
            state_name = getattr(new_state, "name", str(new_state))
            if state_name == "open":
                logger.critical(
                    "circuit_breaker_open name={} fail_max={} recent_failures={}",
                    name,
                    cb.fail_max,
                    cb.fail_counter,
                )
                _fire_breaker_open_alert(name, int(cb.fail_counter))
            elif state_name == "half-open":
                logger.info("circuit_breaker_half_open name={}", name)
            elif state_name == "closed":
                logger.info("circuit_breaker_closed name={}", name)


# --------------------------------------------------------------------------- #
# Breaker handle + registry
# --------------------------------------------------------------------------- #


class _BreakerHandle:
    """Resolved configuration + underlying pybreaker instance (or None for noop)."""

    __slots__ = ("name", "enabled", "fail_max", "reset_timeout", "circuit")

    def __init__(
        self,
        *,
        name: str,
        enabled: bool,
        fail_max: int,
        reset_timeout: int,
        circuit: Any,
    ) -> None:
        self.name = name
        self.enabled = enabled
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.circuit = circuit  # pybreaker.CircuitBreaker | None


def _build_handle(name: str) -> _BreakerHandle:
    """Resolve a breaker's config from env and build its pybreaker instance."""
    spec = _SERVICE_SPECS[name]
    enabled = _env_flag(spec["enabled_env"], True)
    fail_max = _first_env_int(spec["fail_max_envs"], spec["fail_max_default"])
    reset_timeout = _first_env_int(spec["reset_envs"], spec["reset_default"])
    circuit: Any = None
    if enabled and _PYBREAKER_AVAILABLE:
        circuit = pybreaker.CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            exclude=list(spec["exclude"]),
            listeners=[_BreakerStateListener()],
            name=name,
        )
    return _BreakerHandle(
        name=name,
        enabled=enabled,
        fail_max=fail_max,
        reset_timeout=reset_timeout,
        circuit=circuit,
    )


# Module-level registry — built lazily on first access (after `load_repo_env`).
# Tests reset it via `reset_breakers()`; env is re-read on next access.
_breakers: dict[str, _BreakerHandle] = {}


def get_breaker(name: str) -> _BreakerHandle:
    """Return the named breaker handle, building it lazily on first access."""
    if name not in _SERVICE_SPECS:
        raise ValueError(f"Unknown circuit breaker: {name!r}")
    handle = _breakers.get(name)
    if handle is None:
        handle = _build_handle(name)
        _breakers[name] = handle
    return handle


def reset_breakers() -> None:
    """Drop all cached breaker handles (tests / forced reconfiguration)."""
    _breakers.clear()


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #


async def call_async(name: str, coro_factory: Callable[[], Awaitable[T]]) -> T:
    """Run *coro_factory()* guarded by the named async circuit breaker.

    ``coro_factory`` is a zero-arg callable returning a coroutine (matching the
    pattern already proven in ``market_data.py``, e.g.
    ``lambda: asyncio.wait_for(client.indexer...(), timeout=15.0)``). Falls back
    to direct execution when the breaker is disabled or pybreaker is absent.
    Raises :class:`~src.exceptions.CircuitBreakerOpenError` (with the underlying
    ``pybreaker.CircuitBreakerError`` chained) when the circuit is open.

    Note: pybreaker 1.x drives the call through a tornado ``gen.coroutine``;
    on Python 3.12+ this can emit a cosmetic ``RuntimeWarning: coroutine ...
    was never awaited`` during state transitions (the existing market_data
    breaker has the same behavior). The call result and breaker state are
    correct; the warning is a tornado/native-coroutine interop artifact.
    """
    handle = get_breaker(name)
    if handle.circuit is None:
        return await coro_factory()
    try:
        return await handle.circuit.call_async(coro_factory)
    except _CIRCUIT_BREAKER_ERROR as exc:
        raise CircuitBreakerOpenError(
            f"Circuit breaker '{name}' is open", service=name
        ) from exc


def call(name: str, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Call *func(args, kwargs)* guarded by the named sync circuit breaker.

    Falls back to direct execution when the breaker is disabled or pybreaker is
    absent. Raises :class:`~src.exceptions.CircuitBreakerOpenError` when open.
    Thread-safe (pybreaker guards transitions with an RLock); safe to use from
    short-lived daemon threads (e.g. the Telegram/Loki send threads).
    """
    handle = get_breaker(name)
    if handle.circuit is None:
        return func(*args, **kwargs)
    try:
        return handle.circuit.call(func, *args, **kwargs)
    except _CIRCUIT_BREAKER_ERROR as exc:
        raise CircuitBreakerOpenError(
            f"Circuit breaker '{name}' is open", service=name
        ) from exc


def breaker_states() -> dict[str, dict[str, Any]]:
    """Return live state for every registered breaker (sync, no I/O).

    Each entry: ``{enabled, backend, state, fail_counter, fail_max,
    reset_timeout, label}``. Used by the ``/api/v1/monitoring/circuit-breakers``
    endpoint for operator visibility.
    """
    result: dict[str, dict[str, Any]] = {}
    for name, spec in _SERVICE_SPECS.items():
        handle = get_breaker(name)
        if handle.circuit is None:
            result[name] = {
                "enabled": False,
                "backend": "noop",
                "state": "closed",
                "fail_counter": 0,
                "fail_max": handle.fail_max,
                "reset_timeout": handle.reset_timeout,
                "label": spec["label"],
            }
        else:
            cb = handle.circuit
            result[name] = {
                "enabled": True,
                "backend": "pybreaker",
                "state": cb.current_state,
                "fail_counter": int(cb.fail_counter),
                "fail_max": int(cb.fail_max),
                "reset_timeout": int(cb.reset_timeout),
                "label": spec["label"],
            }
    return result
