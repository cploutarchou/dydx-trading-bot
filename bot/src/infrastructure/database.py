"""Database configuration and connection management for PostgreSQL only."""

import os
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool


class DatabaseConfig:
    """Database configuration manager"""

    def __init__(self):
        self.cutover_mode = (
            os.getenv("BOT_DB_CUTOVER_MODE", "shared")
            .strip()
            .lower()
            .replace("-", "_")
        )
        if self.cutover_mode not in {
            "shared",
            "dedicated",
            "dedicated_with_shared_fallback",
        }:
            raise ValueError(
                "Unsupported BOT_DB_CUTOVER_MODE. Use one of: "
                "shared, dedicated, dedicated_with_shared_fallback"
            )

        raw_db_type = os.getenv(
            "BOT_DB_TYPE", os.getenv("DB_TYPE", "postgresql")
        ).strip().lower()
        if raw_db_type not in {"postgres", "postgresql"}:
            raise ValueError(
                f"Unsupported DB_TYPE '{raw_db_type}'. Only PostgreSQL is supported."
            )
        self.db_type = "postgresql"
        self.database_url = self._resolve_database_url()
        self.db_name, self.db_host, self.db_port, self.db_user, self.db_password = (
            self._resolve_db_fields()
        )
        self.echo_sql = os.getenv("DB_ECHO_SQL", "false").lower() == "true"
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    @staticmethod
    def _normalize_database_url(raw_url: str) -> str:
        """Normalize postgres URL for SQLAlchemy and enforce supported engine."""
        candidate = (raw_url or "").strip()
        if not candidate:
            return ""
        lowered = candidate.lower()
        if lowered.startswith("postgresql+psycopg2://"):
            return candidate
        if lowered.startswith("postgresql://"):
            return "postgresql+psycopg2://" + candidate[len("postgresql://") :]
        if lowered.startswith("postgres://"):
            return "postgresql+psycopg2://" + candidate[len("postgres://") :]
        raise ValueError(
            "Unsupported database URL scheme. Only PostgreSQL URLs are supported."
        )

    def _resolve_database_url(self) -> str:
        """Resolve optional explicit database URL with cutover-mode behavior."""
        bot_url = self._normalize_database_url(os.getenv("BOT_DATABASE_URL", ""))
        shared_url = self._normalize_database_url(os.getenv("DATABASE_URL", ""))

        if self.cutover_mode == "shared":
            return shared_url
        if self.cutover_mode == "dedicated":
            if bot_url:
                return bot_url
            if self._has_bot_db_fields():
                return ""
            raise ValueError(
                "BOT_DB_CUTOVER_MODE=dedicated requires BOT_DATABASE_URL or BOT_DB_* values"
            )

        # dedicated_with_shared_fallback
        return bot_url or shared_url

    def _resolve_db_fields(self) -> tuple[str, str, str, str, str]:
        """Resolve host/port/name/user/password based on cutover mode."""
        if self.cutover_mode == "shared":
            return (
                os.getenv("DB_NAME", "dydx_bot"),
                os.getenv("DB_HOST", "localhost"),
                os.getenv("DB_PORT", "5432"),
                os.getenv("DB_USER", "postgres"),
                os.getenv("DB_PASSWORD", ""),
            )

        if self.cutover_mode == "dedicated":
            if self.database_url:
                return self._bot_db_fields()
            if self._has_bot_db_fields():
                return self._bot_db_fields()
            raise ValueError(
                "BOT_DB_CUTOVER_MODE=dedicated requires BOT_DB_HOST, BOT_DB_PORT, "
                "BOT_DB_NAME, BOT_DB_USER, and BOT_DB_PASSWORD when BOT_DATABASE_URL is unset"
            )

        # dedicated_with_shared_fallback
        if self._has_bot_db_fields():
            return self._bot_db_fields()
        return (
            os.getenv("DB_NAME", "dydx_bot"),
            os.getenv("DB_HOST", "localhost"),
            os.getenv("DB_PORT", "5432"),
            os.getenv("DB_USER", "postgres"),
            os.getenv("DB_PASSWORD", ""),
        )

    @staticmethod
    def _has_bot_db_fields() -> bool:
        required = [
            os.getenv("BOT_DB_NAME", "").strip(),
            os.getenv("BOT_DB_HOST", "").strip(),
            os.getenv("BOT_DB_PORT", "").strip(),
            os.getenv("BOT_DB_USER", "").strip(),
            os.getenv("BOT_DB_PASSWORD", "").strip(),
        ]
        return all(bool(value) for value in required)

    @staticmethod
    def _bot_db_fields() -> tuple[str, str, str, str, str]:
        return (
            os.getenv("BOT_DB_NAME", "dydx_bot"),
            os.getenv("BOT_DB_HOST", "localhost"),
            os.getenv("BOT_DB_PORT", "5432"),
            os.getenv("BOT_DB_USER", "postgres"),
            os.getenv("BOT_DB_PASSWORD", ""),
        )

    def get_connection_string(self) -> str:
        """Generate database connection string"""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    def get_engine_kwargs(self) -> dict:
        """Get SQLAlchemy engine kwargs for PostgreSQL."""
        return {
            "echo": self.echo_sql,
            "future": True,
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

    def ensure_schema_compatibility(self):
        """Apply small backward-compatible schema fixes for existing databases."""
        engine = self.get_engine()

        with engine.begin() as connection:
            inspector = inspect(connection)

            if inspector.has_table("bot_instances"):
                logger.info("Applying compatibility fix: normalizing bot_instances.status values")
                status_udt = connection.execute(
                    text(
                        """
                        SELECT c.udt_name
                        FROM information_schema.columns c
                        WHERE c.table_name = 'bot_instances'
                          AND c.column_name = 'status'
                        LIMIT 1
                        """
                    )
                ).scalar()

                if status_udt == "botstatusenum":
                    connection.execute(
                        text(
                            """
                            UPDATE bot_instances
                            SET status = CASE UPPER(CAST(status AS TEXT))
                                WHEN 'FAILED' THEN 'ERROR'::botstatusenum
                                WHEN 'PAUSED' THEN 'STOPPED'::botstatusenum
                                ELSE UPPER(CAST(status AS TEXT))::botstatusenum
                            END
                            WHERE UPPER(CAST(status AS TEXT)) <> CAST(status AS TEXT)
                               OR CAST(status AS TEXT) IN ('FAILED', 'failed', 'PAUSED', 'paused')
                            """
                        )
                    )
                else:
                    connection.execute(
                        text(
                            """
                            UPDATE bot_instances
                            SET status = CASE UPPER(CAST(status AS TEXT))
                                WHEN 'FAILED' THEN 'ERROR'
                                WHEN 'PAUSED' THEN 'STOPPED'
                                ELSE UPPER(CAST(status AS TEXT))
                            END
                            WHERE UPPER(CAST(status AS TEXT)) <> CAST(status AS TEXT)
                               OR CAST(status AS TEXT) IN ('FAILED', 'failed', 'PAUSED', 'paused')
                            """
                        )
                    )

            if inspector.has_table("backtest_strategies"):
                columns = {
                    column["name"] for column in inspector.get_columns("backtest_strategies")
                }
                if "pair_selection_mode" not in columns:
                    logger.info(
                        "Applying compatibility fix: adding backtest_strategies.pair_selection_mode"
                    )
                    connection.execute(
                        text(
                            "ALTER TABLE backtest_strategies "
                            "ADD COLUMN pair_selection_mode VARCHAR(32) "
                            "NOT NULL DEFAULT 'liquidity'"
                        )
                    )
                    logger.info(
                        "Compatibility fix applied: backtest_strategies.pair_selection_mode"
                    )


    def _build_alembic_config(self) -> Optional[Config]:
        config = DatabaseConfig()
        alembic_path = Path(__file__).resolve().parents[2] / "alembic.ini"
        if not alembic_path.exists():
            logger.warning("Alembic config not found at {}; skipping migrations", alembic_path)
            return None

        alembic_config = Config(str(alembic_path))
        alembic_config.set_main_option("sqlalchemy.url", config.get_connection_string())
        return alembic_config

    def ensure_alembic_baseline(self, baseline_revision: str = "8c1f34af2f10") -> str:
        """Stamp legacy schemas that were created outside Alembic.

        This keeps startup safe for long-lived deployments where tables were
        created by SQLAlchemy metadata, not revision scripts.
        """
        alembic_config = self._build_alembic_config()
        if alembic_config is None:
            return "skipped-no-config"

        with self.get_engine().begin() as connection:
            inspector = inspect(connection)
            if inspector.has_table("alembic_version"):
                return "already-versioned"

            has_core_schema = inspector.has_table("bot_instances") and inspector.has_table(
                "backtest_strategies"
            )
            if not has_core_schema:
                logger.info("Skipping Alembic baseline stamp: core legacy tables not detected")
                return "skipped-core-schema-not-detected"

        logger.warning(
            "Legacy schema detected without alembic_version; stamping revision {}",
            baseline_revision,
        )
        command.stamp(alembic_config, baseline_revision)
        logger.info("Alembic baseline stamp completed at {}", baseline_revision)
        return "stamped"

    def run_pending_migrations(self):
        """Apply Alembic migrations against the active database URL."""
        alembic_config = self._build_alembic_config()
        if alembic_config is None:
            return

        baseline_revision = "8c1f34af2f10"
        baseline_status = self.ensure_alembic_baseline(baseline_revision=baseline_revision)
        logger.info("Alembic baseline path: {}", baseline_status)
        if baseline_status == "stamped":
            logger.info("Alembic baseline stamped revision={}", baseline_revision)

        with self.get_engine().begin() as connection:
            inspector = inspect(connection)
            if not inspector.has_table("alembic_version"):
                logger.warning(
                    "Alembic version table not found; skipping automatic migrations for legacy schema"
                )
                return

        logger.info("Running pending Alembic migrations...")
        command.upgrade(alembic_config, "head")
        logger.info("Alembic migrations applied successfully")

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


def get_session():
    """Get database session for dependency injection with automatic cleanup"""
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Initialize database (run on startup)"""
    db.create_all_tables()
    logger.info("Database initialized successfully")


if __name__ == "__main__":
    # Test database connection
    import sys

    from src.shared.logging_setup import setup_logging

    setup_logging()

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
