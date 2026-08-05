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
