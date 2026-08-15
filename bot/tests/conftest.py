import os
import sys
from pathlib import Path

import pytest


def _ensure_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


REPO_ROOT = Path(__file__).resolve().parents[2]
BOT_ROOT = REPO_ROOT / "bot"

_ensure_path(REPO_ROOT)
_ensure_path(BOT_ROOT)


# ============================================================================
# Market-data shared (L2) cache isolation
# ============================================================================
#
# The Redis/Valkey-backed L2 cache in ``src/infrastructure/cache`` is shared
# state. Tests must stay deterministic regardless of Redis/Valkey contents, so
# the L2 is kept inert (Noop) by default. Tests that exercise the cache override
# ``src.trading.market_data.get_market_data_cache`` directly with their own
# double (their ``monkeypatch.setattr`` runs after this fixture's setup and so
# takes precedence within the same function-scoped monkeypatch).
@pytest.fixture(autouse=True)
def _isolate_shared_market_data_cache(monkeypatch):
    from src.infrastructure.cache import NoopMarketDataCache, reset_market_data_cache
    from src.trading import market_data

    reset_market_data_cache()
    monkeypatch.setattr(
        market_data, "get_market_data_cache", lambda: NoopMarketDataCache()
    )


# ============================================================================
# Circuit-breaker isolation
# ============================================================================
#
# The centralized breakers in ``src/infrastructure/resilience`` hold shared,
# stateful singletons. Left active across the suite, a failure-simulating test
# would trip a breaker and leave it OPEN for unrelated tests (cascading
# ``CircuitBreakerOpenError``). Defaulting them to disabled also keeps existing
# call-site tests deterministic: they see raw provider behavior exactly as
# before the breakers existed. Tests that exercise a breaker re-enable it with
# ``monkeypatch.setenv("<SERVICE>_CIRCUIT_ENABLED", "true")`` +
# ``resilience.reset_breakers()``.
@pytest.fixture(autouse=True)
def _isolate_circuit_breakers(monkeypatch):
    from src.infrastructure import resilience

    resilience.reset_breakers()
    for service in ("DYDX_INDEXER", "TELEGRAM", "LOKI"):
        monkeypatch.setenv(f"{service}_CIRCUIT_ENABLED", "false")


# ============================================================================
# Cross-worker WebSocket broadcast bus isolation
# ============================================================================
#
# The Redis pub/sub bus in ``src/infrastructure/broadcast`` fans WebSocket
# broadcasts across Uvicorn workers. Tests must stay deterministic regardless of
# Redis/Valkey state, so the bus is kept inert (Noop) by default — every
# ``broadcast_to_bot`` then behaves exactly as it did before the bus existed
# (local-only delivery). The accessor is patched at the *importer*
# (``src.api.websocket_server``), mirroring the market-data cache fixture above;
# a test's own function-scoped monkeypatch runs after this setup and so takes
# precedence when it wants to exercise a real/double bus.
@pytest.fixture(autouse=True)
def _isolate_broadcast_bus(monkeypatch):
    from src.infrastructure.broadcast import NoopBroadcastBus, reset_broadcast_bus

    monkeypatch.setenv("WS_BROADCAST_ENABLED", "false")
    reset_broadcast_bus()
    try:
        from src.api import websocket_server
    except ImportError:  # pragma: no cover - FastAPI/pydantic absent in stripped envs
        # The bus is already Noop via the disabled flag + reset above; this guard
        # only affects stripped local envs (no pydantic_core) so non-FastAPI tests
        # can still run. CI has FastAPI, so the patch applies there. ``ImportError``
        # is intentionally narrow so a genuine regression in websocket_server.py
        # surfaces instead of being silently swallowed.
        return
    monkeypatch.setattr(
        websocket_server, "get_broadcast_bus", lambda: NoopBroadcastBus()
    )


# ============================================================================
# Portfolio drawdown peak-equity store isolation
# ============================================================================
#
# The Redis-backed peak-equity ratchet in ``src/trading/portfolio_risk.py`` is
# shared state. Tests must stay deterministic regardless of Redis/Valkey
# contents, so the store is kept inert (observe -> None, i.e. the drawdown
# check skips itself) by default. Tests exercising the real store inject their
# own double via ``monkeypatch.setattr(portfolio_risk, "get_peak_equity_store", ...)``
# (their function-scoped monkeypatch runs after this fixture's setup and so
# takes precedence).
@pytest.fixture(autouse=True)
def _isolate_portfolio_peak_store(monkeypatch):
    from src.trading import portfolio_risk

    class _InertPeakStore:
        async def observe(self, address, equity):  # pragma: no cover - inert
            del address, equity
            return None

    portfolio_risk.reset_peak_equity_store()
    monkeypatch.setattr(
        portfolio_risk,
        "get_peak_equity_store",
        lambda: _InertPeakStore(),
    )


# ============================================================================
# PostgreSQL database helper functions
# ============================================================================


def get_expected_db_dialect() -> str:
    """Return the expected database dialect for current environment."""
    db_type = os.getenv("DB_TYPE", "postgres").lower()
    if db_type in ("postgres", "postgresql"):
        return "postgresql"
    raise AssertionError(f"Unsupported test DB_TYPE: {db_type}")


def get_driver_name() -> str:
    """Return the Python driver name for the active test database."""
    return "psycopg2"


def assert_connection_string_valid(conn_str: str) -> None:
    """Assert connection string is valid for current database environment.

    Args:
        conn_str: Connection string to validate

    Raises:
        AssertionError: If connection string doesn't match expected dialect
    """
    dialect = get_expected_db_dialect()
    driver = get_driver_name()
    expected_prefix = f"{dialect}+{driver}://"
    assert conn_str.startswith(
        expected_prefix
    ), f"Expected {expected_prefix} in connection string, got: {conn_str}"


def assert_db_type_supported(db_type_str: str) -> None:
    """Assert db_type field contains supported value.

    Args:
        db_type_str: The db_type value from payload or config

    Raises:
        AssertionError: If db_type is not a supported database type
    """
    supported = ("postgres", "postgresql")
    assert (
        db_type_str in supported
    ), f"Unsupported db_type: {db_type_str}. Supported: {supported}"


def get_test_db_port() -> str:
    """Get the bot test PostgreSQL port."""
    return "5432"


def get_test_connection_string(
    user: str = "bot_user",
    password: str = "secret",
    host: str = "db-host",
    db_name: str = "bot_db",
) -> str:
    """Generate a test connection string for current database environment.

    Args:
        user: Database user
        password: Database password
        host: Database host
        db_name: Database name

    Returns:
        Full connection string with appropriate dialect and driver
    """
    port = get_test_db_port()
    return (
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
        "?sslmode=disable"
    )
