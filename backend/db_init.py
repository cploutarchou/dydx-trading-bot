"""
Database initialization and management module.
Handles engine creation, session management, and table creation.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.config import DatabaseSettings
import os
import logging

logger = logging.getLogger(__name__)


def get_database_config() -> DatabaseSettings:
    """Get database configuration from environment variables."""
    return DatabaseSettings(
        type=os.getenv("DB_TYPE", "postgresql"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "dydx_bot"),
        user=os.getenv("DB_USER", "dydx_bot"),
        password=os.getenv("DB_PASSWORD", ""),
        ssl=os.getenv("DB_SSL", "false").lower() == "true",
        timeout=int(os.getenv("DB_TIMEOUT", "5")),
        max_connections=int(os.getenv("DB_MAX_CONNECTIONS", "10")),
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    )


# Initialize database configuration
_db_config = get_database_config()
DATABASE_URL = _db_config.dsn

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=_db_config.pool_size,
    max_overflow=_db_config.max_overflow,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    """Get a database session."""
    return SessionLocal()


def init_db():
    """Initialize database tables."""
    from models.sqlmodel_models import SQLModel

    logger.info(f"Initializing database: {_db_config.dbname}")
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def close_db():
    """Close database connection."""
    engine.dispose()
    logger.info("Database connection closed")


class DatabaseSession:
    """Context manager for automatic session handling."""

    def __init__(self):
        self.session: Session = None

    def __enter__(self) -> Session:
        self.session = SessionLocal()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type:
                self.session.rollback()
                logger.error(f"Transaction rolled back due to {exc_type}: {exc_val}")
            self.session.close()