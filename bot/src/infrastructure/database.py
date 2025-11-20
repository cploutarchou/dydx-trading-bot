"""
Database configuration and connection management
Supports SQLite (development) and PostgreSQL (production)
"""

import logging
import os
from typing import Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration manager"""

    def __init__(self):
        self.db_type = os.getenv("DB_TYPE", "sqlite")  # sqlite or postgresql
        self.db_name = os.getenv("DB_NAME", "trading_bot.db")
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_user = os.getenv("DB_USER", "postgres")
        self.db_password = os.getenv("DB_PASSWORD", "")
        self.echo_sql = os.getenv("DB_ECHO_SQL", "false").lower() == "true"
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    def get_connection_string(self) -> str:
        """Generate database connection string"""
        if self.db_type == "postgresql":
            return (
                f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        elif self.db_type == "sqlite":
            return f"sqlite:///{self.db_name}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def get_engine_kwargs(self) -> dict:
        """Get SQLAlchemy engine kwargs based on a DB type"""
        base_kwargs = {
            "echo": self.echo_sql,
            "future": True,
        }

        if self.db_type == "postgresql":
            base_kwargs.update(
                {
                    "poolclass": QueuePool,
                    "pool_size": self.pool_size,
                    "max_overflow": self.max_overflow,
                    "pool_recycle": self.pool_recycle,
                    "connect_args": {
                        "connect_timeout": 10,
                        "keepalives": 1,
                        "keepalives_idle": 30,
                    },
                }
            )
        elif self.db_type == "sqlite":
            base_kwargs.update(
                {
                    "poolclass": StaticPool,
                    "connect_args": {"check_same_thread": False},
                }
            )

        return base_kwargs


class DatabaseManager:
    """Database connection and session management"""

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._initialize()

    def _initialize(self):
        """Initialize database engine and session factory"""
        config = DatabaseConfig()
        connection_string = config.get_connection_string()
        engine_kwargs = config.get_engine_kwargs()

        logger.info(f"Initializing database: {config.db_type}")
        logger.info(f"Connection string: {connection_string.split('@')[0]}@***")

        self._engine = create_engine(connection_string, **engine_kwargs)

        # Enable WAL mode for SQLite (better for concurrent access)
        if config.db_type == "sqlite":

            @event.listens_for(Engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

        self._session_factory = sessionmaker(
            bind=self._engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

        logger.info("Database initialization complete")

    def get_engine(self) -> Engine:
        """Get SQLAlchemy engine"""
        if self._engine is None:
            self._initialize()
        return self._engine

    def get_session(self) -> Session:
        """Get new database session"""
        if self._session_factory is None:
            self._initialize()
        return self._session_factory()

    def create_all_tables(self):
        """Create all database tables from models"""
        from internal.domain import Base

        engine = self.get_engine()
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

    def drop_all_tables(self):
        """Drop all database tables (DANGEROUS - use only in development)"""
        from internal.domain import Base

        engine = self.get_engine()
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped")

    def health_check(self) -> bool:
        """Check database connection health"""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            logger.info("Database health check passed")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self._engine:
            self._engine.dispose()
            logger.info("Database connection closed")


# Global database manager instance
db = DatabaseManager()


def get_session() -> Session:
    """Get database session for dependency injection"""
    return db.get_session()


def init_db():
    """Initialize database (run on startup)"""
    db.create_all_tables()
    logger.info("Database initialized successfully")


if __name__ == "__main__":
    # Test database connection
    import sys

    logging.basicConfig(level=logging.INFO)

    try:
        db_manager = DatabaseManager()
        if db_manager.health_check():
            print("✅ Database connection successful")
            sys.exit(0)
        else:
            print("❌ Database connection failed")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
