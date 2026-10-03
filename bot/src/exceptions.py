"""Central typed exception hierarchy for the bot service.

This module is the canonical home for bot-domain exceptions. It is intentionally a
**leaf** module (no imports from other ``src`` packages) so it can be imported from
any layer without triggering environment load-order or circular-import concerns
(see AGENTS.md rule #1).

Design:

- ``BotError`` is the common base for all bot-domain errors. Callers can catch at the
  category level (e.g. ``except DatabaseError``) or the broad level
  (``except BotError``) without trapping unrelated stdlib/3rd-party exceptions.
- Pre-existing exceptions that used to live in domain modules
  (``DatabaseConnectionError``, ``BacktestEnqueueError``, the ``CredentialCipher*``
  hierarchy, ``GracefulShutdownException``) are defined here and **re-imported by their
  original modules**, so every existing import path keeps resolving to the same class
  object. ``GracefulShutdownException`` is intentionally *not* a ``BotError`` — it is a
  control-flow signal for the runtime entrypoint, not a fault.

When adding new error sites: raise the most specific subtype; reserve broad
``except Exception`` for genuinely best-effort cleanup/telemetry (and log with
context). The ratchet test (``tests/test_exception_handling_ratchet.py``) prevents the
broad-catch count from growing.
"""

from __future__ import annotations


class BotError(Exception):
    """Base class for all bot-domain exceptions."""


# --------------------------------------------------------------------------- #
# Infrastructure
# --------------------------------------------------------------------------- #


class InfrastructureError(BotError):
    """Failures from cross-cutting infrastructure (DB, cache, storage, message bus)."""


class DatabaseError(InfrastructureError):
    """Database access or connection failures."""


class DatabaseConnectionError(DatabaseError):
    """Exception raised when database connection fails."""


class CacheServiceError(InfrastructureError):
    """Redis/Valkey cache service failures."""


class StorageError(InfrastructureError):
    """Optional analytics/artifact storage failures (ClickHouse, MinIO/S3)."""


class MessageBusError(InfrastructureError):
    """NATS/event-bus messaging failures."""


class ConfigurationError(BotError):
    """Invalid or incomplete runtime configuration."""


# --------------------------------------------------------------------------- #
# External integrations
# --------------------------------------------------------------------------- #


class ExternalServiceError(BotError):
    """Failures communicating with an external service."""


class ExchangeError(ExternalServiceError):
    """dYdX exchange client failures (network, API, signing)."""


class CircuitBreakerOpenError(ExternalServiceError):
    """Raised when a named circuit breaker rejects a call because it is OPEN.

    Carries the originating ``service`` name (e.g. ``"dydx_indexer"``) so callers
    can degrade per-dependency — e.g. serve cached market data, skip a
    best-effort notification, or surface a typed error instead of hanging on a
    downed dependency. This is a control-flow signal for graceful degradation
    during a sustained external-service outage, NOT a transient error to blindly
    retry through (the breaker is already rate-limiting attempts on our behalf).
    See :mod:`src.infrastructure.resilience`.
    """

    def __init__(self, message: str = "", *, service: str | None = None) -> None:
        super().__init__(message)
        self.service = service


# --------------------------------------------------------------------------- #
# Domain
# --------------------------------------------------------------------------- #


class TradingError(BotError):
    """Trading-domain logic failures (strategy, positions, market data)."""


class UnhedgedExposureError(TradingError, RuntimeError):
    """An emergency close failed: a leg may be open with no hedge.

    Raised by the pair agent when it could not flatten a partially built pair.
    It is also a ``RuntimeError`` so existing handlers keep working; the entry
    scanner reacts to this type specifically by halting new entries.
    """


class OrderRejectedError(TradingError):
    """The node rejected the order transaction at broadcast time.

    Raised before any indexer polling: a rejected transaction never becomes an
    order, so looking for it can only time out or bind to somebody else's.
    """

    def __init__(self, market: str, code: int, detail: str = "") -> None:
        self.market = market
        self.code = code
        self.detail = detail
        suffix = f": {detail}" if detail else ""
        super().__init__(
            f"order for {market} rejected by the node (code {code}){suffix}"
        )


class BacktestError(BotError):
    """Backtest orchestration/execution failures."""


class BacktestEnqueueError(BacktestError):
    """Raised when a backtest cannot be handed off to its configured worker."""


class ProcessManagerError(BotError):
    """Bot instance lifecycle/process management failures."""


class CredentialError(BotError):
    """Credential handling failures (encryption, decryption, format)."""


class CredentialCipherError(CredentialError):
    """Base for credential at-rest encryption/decryption failures."""


class CredentialEncryptionError(CredentialCipherError):
    """Raised when credential plaintext cannot be encrypted (sealed)."""


class CredentialDecryptionError(CredentialCipherError):
    """Raised when a sealed credential envelope cannot be decrypted."""


# --------------------------------------------------------------------------- #
# Control-flow signals (NOT faults — must not be caught as BotError)
# --------------------------------------------------------------------------- #
#
# ``GracefulShutdownException`` is intentionally NOT defined here: it lives in
# ``src/main_instance.py`` (entangled with the ``BotInstance`` signal-handling
# setup) and stays a standalone ``Exception``. Import it from there directly.


__all__ = [
    "BacktestEnqueueError",
    "BacktestError",
    "BotError",
    "CacheServiceError",
    "CircuitBreakerOpenError",
    "ConfigurationError",
    "CredentialDecryptionError",
    "CredentialEncryptionError",
    "CredentialCipherError",
    "CredentialError",
    "DatabaseConnectionError",
    "DatabaseError",
    "ExchangeError",
    "ExternalServiceError",
    "InfrastructureError",
    "MessageBusError",
    "ProcessManagerError",
    "StorageError",
    "TradingError",
]
