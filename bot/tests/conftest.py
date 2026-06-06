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
# Database Helper Functions (Phase 4, Task 4)
# Support both PostgreSQL and MySQL/MariaDB test environments
# ============================================================================

def get_expected_db_dialect() -> str:
    """Return the expected database dialect for current environment.
    
    Returns:
        "mysql" if DB_TYPE env var indicates MySQL/MariaDB, otherwise "postgresql"
    """
    db_type = os.getenv("DB_TYPE", "postgresql").lower()
    if db_type in ("mysql", "mariadb"):
        return "mysql"
    return "postgresql"


def get_driver_name() -> str:
    """Return the appropriate Python driver name for current database.
    
    Returns:
        "pymysql" for MySQL/MariaDB, "psycopg2" for PostgreSQL
    """
    dialect = get_expected_db_dialect()
    return "pymysql" if dialect == "mysql" else "psycopg2"


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
    supported = ("postgresql", "mysql", "mariadb")
    assert db_type_str in supported, (
        f"Unsupported db_type: {db_type_str}. Supported: {supported}"
    )


def get_test_db_port() -> str:
    """Get the test database port for current environment.
    
    Returns:
        "5432" for PostgreSQL, "3307" for MySQL (bot-specific port)
    """
    dialect = get_expected_db_dialect()
    return "3307" if dialect == "mysql" else "5432"


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
    dialect = get_expected_db_dialect()
    driver = get_driver_name()
    port = get_test_db_port()
    
    if dialect == "mysql":
        return f"mysql://{user}:{password}@{host}:{port}/{db_name}"
    else:
        return f"postgresql://{user}:{password}@{host}:5432/{db_name}"
