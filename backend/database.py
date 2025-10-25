"""
Database configuration and session management for backtest results storage.
Supports both SQLite (development) and PostgreSQL (production).

All table models have been moved to backend.models subpackage for better organization.
"""

# ⚠️ CRITICAL: Load environment variables FIRST, before any other imports
# This ensures DB_* environment variables are available for database configuration
from dotenv import load_dotenv

load_dotenv()

import logging
import os
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Import Base from models package (single source of truth for declarative base)
from .models.base import Base

# Import all models to register them with Base
from .models.backtest import (
    BacktestCandle,
    BacktestComparison,
    BacktestLog,
    BacktestPosition,
    BacktestResult,
    BacktestRun,
    BacktestTrade,
)
from .models.strategy import (
    BacktestStrategy,
    StrategyExecutionState,
    StrategyVersionHistory,
)
from .models.trade import TradeLog
from .models.user import AuditLog, User
from .models.settings import BotSetting, RedisSetting

__all__ = [
    "BacktestRun",
    "BacktestResult",
    "BacktestTrade",
    "BacktestLog",
    "BacktestPosition",
    "BacktestCandle",
    "BacktestComparison",
    "BacktestStrategy",
    "StrategyVersionHistory",
    "StrategyExecutionState",
    "TradeLog",
    "User",
    "AuditLog",
    "BotSetting",
    "RedisSetting",
]


def get_database_url() -> str:
    """Get database URL from config.yaml or environment variables.

    Priority:
    1. config.yaml (database section)
    2. Environment variables (DB_*)
    3. Built-in defaults

    Returns:
        SQLAlchemy database URL
    """
    try:
        from backend.config_loader import get_config_loader

        config_loader = get_config_loader()
        db_config = config_loader.get_database_config()
    except ImportError:
        # Fallback to direct environment variables
        db_config = {
            "type": os.getenv("DB_TYPE", "sqlite"),
            "name": os.getenv("DB_NAME", "dydx_backtest.db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
        }

    db_type = db_config.get("type", "sqlite")
    db_name = db_config.get("name", "dydx_backtest.db")
    db_user = db_config.get("user", "postgres")
    db_password = db_config.get("password", "")
    db_host = db_config.get("host", "localhost")
    db_port = db_config.get("port", "5432")

    if db_type == "postgresql":
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        # SQLite - create file in app directory
        db_path = os.path.join(os.path.dirname(__file__), "..", "app", db_name)
        db_url = f"sqlite:///{db_path}"

    return db_url


# Get database configuration and log it
DATABASE_URL = get_database_url()
log_msg = (
    f"Using database: {os.getenv('DB_TYPE', 'sqlite')} - "
    f"{DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}"
)
logger.info(log_msg)

# Database engine and session factory
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database - create all tables and seed default admin user."""
    try:
        # Create all tables that don't exist
        # This is safe to run even if tables already exist - SQLAlchemy won't recreate them
        Base.metadata.create_all(bind=engine)

        # Log all tables that should exist
        inspector = __import__("sqlalchemy", fromlist=["inspect"]).inspect
        inspector_obj = inspector(engine)
        existing_tables = inspector_obj.get_table_names()

        logger.info("✅ Database initialized successfully")
        logger.info(
            f"   Existing tables ({len(existing_tables)}): {', '.join(sorted(existing_tables))}"
        )

        # Verify all expected model tables exist
        expected_tables = {table.name for table in Base.metadata.tables.values()}
        missing_tables = expected_tables - set(existing_tables)

        if missing_tables:
            logger.warning(f"⚠️  Missing tables: {', '.join(sorted(missing_tables))}")
        else:
            logger.info(f"✅ All {len(expected_tables)} expected tables present")

    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}", exc_info=True)
        raise

    # Seed default admin user on first run
    _seed_admin_user()


def _seed_admin_user():
    """Create default admin user if it doesn't exist.

    Behavior:
    - Uses environment variables ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL when provided.
    - If ADMIN_PASSWORD is not set, generate a secure random password and save it to
      `app/admin_credentials.txt` with restrictive permissions (0o600).
    - Never log the plaintext password to logs. Log only the username and the path
      where credentials were saved (if generated).
    - Idempotent: will not recreate admin if a user with the same username exists.
    """
    from backend.auth import hash_password
    import secrets
    from pathlib import Path

    db = SessionLocal()
    try:
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@dydx-backtest.local")
        admin_password = os.getenv("ADMIN_PASSWORD", None)

        # Check if admin user already exists
        admin_exists = db.query(User).filter(User.username == admin_username).first()

        if admin_exists:
            logger.info(f"ℹ️  Admin user '{admin_username}' already exists, skipping creation")
            return

        generated_password_path = None
        if not admin_password:
            # Generate a secure random password and persist it to a local file with restricted permissions
            admin_password = secrets.token_urlsafe(16)
            try:
                cred_path = Path(__file__).resolve().parents[1] / "app" / "admin_credentials.txt"
                cred_path.parent.mkdir(parents=True, exist_ok=True)
                with cred_path.open("w", encoding="utf-8") as f:
                    f.write(f"username: {admin_username}\n")
                    f.write(f"password: {admin_password}\n")
                    f.write(f"email: {admin_email}\n")
                    f.write(f"created_at: {datetime.utcnow().isoformat()}Z\n")
                # Restrict file permissions to owner read/write
                try:
                    cred_path.chmod(0o600)
                except Exception:
                    pass  # Some systems don't support chmod
                generated_password_path = str(cred_path)
            except Exception as e:
                logger.error(f"Failed to save credentials file: {e}")

        # Create admin user with hashed password
        admin = User(
            username=admin_username,
            email=admin_email,
            hashed_password=hash_password(admin_password),
            full_name="Administrator",
            is_active=True,
            is_admin=True,
        )

        db.add(admin)
        db.commit()

        if generated_password_path:
            logger.info(f"✅ Admin user '{admin_username}' created successfully")
            logger.info(f"   Password saved to: {generated_password_path}")
        else:
            logger.info(f"✅ Admin user '{admin_username}' created successfully")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error seeding admin user: {e}", exc_info=True)
    finally:
        db.close()


def get_db():
    """Get a database session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
