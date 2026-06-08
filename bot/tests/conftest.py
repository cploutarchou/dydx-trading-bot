import os
import sys
from pathlib import Path


def _ensure_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


REPO_ROOT = Path(__file__).resolve().parents[2]
BOT_ROOT = REPO_ROOT / "bot"

_ensure_path(REPO_ROOT)
_ensure_path(BOT_ROOT)


# ============================================================================
# MariaDB database helper functions
# ============================================================================

def get_expected_db_dialect() -> str:
    """Return the expected database dialect for current environment."""
    db_type = os.getenv("DB_TYPE", "mysql").lower()
    if db_type in ("mysql", "mariadb"):
        return "mysql"
    raise AssertionError(f"Unsupported test DB_TYPE: {db_type}")


def get_driver_name() -> str:
    """Return the Python driver name for MariaDB tests."""
    return "pymysql"


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
    assert conn_str.startswith(expected_prefix), (
        f"Expected {expected_prefix} in connection string, got: {conn_str}"
    )


def assert_db_type_supported(db_type_str: str) -> None:
    """Assert db_type field contains supported value.
    
    Args:
        db_type_str: The db_type value from payload or config
        
    Raises:
        AssertionError: If db_type is not a supported database type
    """
    supported = ("mysql", "mariadb")
    assert db_type_str in supported, (
        f"Unsupported db_type: {db_type_str}. Supported: {supported}"
    )


def get_test_db_port() -> str:
    """Get the bot test MariaDB port."""
    return "3307"


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
    return f"mysql://{user}:{password}@{host}:{port}/{db_name}"
