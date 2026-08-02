"""Hierarchy + re-export invariants for the central exception module.

Pins the ``src.exceptions`` taxonomy and guarantees that the pre-existing
exceptions which were canonicalized into it resolve to a single class object
regardless of import path (so ``isinstance`` checks and ``except`` clauses keep
working across the old and new import locations).
"""

import pytest

import src.exceptions as exc

# --------------------------------------------------------------------------- #
# Hierarchy shape
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "subclass",
    [
        exc.InfrastructureError,
        exc.DatabaseError,
        exc.DatabaseConnectionError,
        exc.CacheServiceError,
        exc.StorageError,
        exc.MessageBusError,
        exc.ExternalServiceError,
        exc.ExchangeError,
        exc.TradingError,
        exc.BacktestError,
        exc.BacktestEnqueueError,
        exc.ProcessManagerError,
        exc.CredentialError,
        exc.CredentialCipherError,
        exc.CredentialEncryptionError,
        exc.CredentialDecryptionError,
        exc.ConfigurationError,
    ],
)
def test_domain_exceptions_are_bot_errors(subclass):
    assert issubclass(subclass, exc.BotError)
    assert issubclass(subclass, Exception)


def test_infrastructure_and_external_branches():
    assert issubclass(exc.DatabaseError, exc.InfrastructureError)
    assert issubclass(exc.CacheServiceError, exc.InfrastructureError)
    assert issubclass(exc.StorageError, exc.InfrastructureError)
    assert issubclass(exc.MessageBusError, exc.InfrastructureError)
    assert issubclass(exc.ExchangeError, exc.ExternalServiceError)


def test_credential_hierarchy():
    assert issubclass(exc.CredentialEncryptionError, exc.CredentialCipherError)
    assert issubclass(exc.CredentialDecryptionError, exc.CredentialCipherError)
    assert issubclass(exc.CredentialCipherError, exc.CredentialError)


def test_backtest_enqueue_is_backtest_error():
    assert issubclass(exc.BacktestEnqueueError, exc.BacktestError)


# --------------------------------------------------------------------------- #
# Re-export identity (old import path == new canonical class)
# --------------------------------------------------------------------------- #


def test_database_connection_error_identity():
    from src.infrastructure.database import DatabaseConnectionError as Old

    assert Old is exc.DatabaseConnectionError
    assert issubclass(Old, exc.DatabaseError)


def test_backtest_enqueue_error_identity():
    from src.infrastructure.use_cases.service_backtest import (
        BacktestEnqueueError as Old,
    )

    assert Old is exc.BacktestEnqueueError
    assert issubclass(Old, exc.BacktestError)


@pytest.mark.parametrize(
    "name",
    ["CredentialCipherError", "CredentialEncryptionError", "CredentialDecryptionError"],
)
def test_credential_exception_identity(name):
    old = __import__("src.shared.credentials_cipher", fromlist=[name])
    old_cls = getattr(old, name)
    new_cls = getattr(exc, name)
    assert old_cls is new_cls
    assert issubclass(new_cls, exc.CredentialError)


def test_graceful_shutdown_exception_is_not_a_bot_error():
    """Control-flow signal must stay outside the BotError taxonomy."""
    from src.main_instance import GracefulShutdownException

    assert not issubclass(GracefulShutdownException, exc.BotError)
    assert issubclass(GracefulShutdownException, Exception)


def test_bot_error_does_not_swallow_keyboard_interrupt():
    """BaseException subclasses must not be caught by ``except BotError``."""
    assert not issubclass(KeyboardInterrupt, exc.BotError)
    assert not issubclass(SystemExit, exc.BotError)


def test_raising_and_catching_at_category_level():
    with pytest.raises(exc.DatabaseError):
        raise exc.DatabaseConnectionError("boom")
    with pytest.raises(exc.BotError):
        raise exc.ExchangeError("network")
