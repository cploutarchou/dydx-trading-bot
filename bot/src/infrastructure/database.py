"""Database configuration and connection management for PostgreSQL only."""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config
from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool


class DatabaseConfig:
    """Database configuration manager"""

    @staticmethod
    def _env(name: str, fallback: str = "") -> str:
        value = os.getenv(name)
        return value if value not in (None, "") else fallback

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        value = os.getenv(name)
        if value in (None, ""):
            return default
        try:
            return int(value)
        except ValueError:
            return default

    @staticmethod
    def _env_bool(name: str, default: bool = False) -> bool:
        value = os.getenv(name)
        if value in (None, ""):
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

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

        raw_db_type = self._env("BOT_DB_TYPE", self._env("DB_TYPE", "postgresql")).strip().lower()
        if raw_db_type not in {"postgres", "postgresql"}:
            raise ValueError(
                f"Unsupported DB_TYPE '{raw_db_type}'. Only PostgreSQL is supported."
            )
        self.db_type = "postgresql"
        self.connection_source = "constructed_fields"
        self.field_source = "shared_db_fields"
        self.database_url = self._resolve_database_url()
        self.db_name, self.db_host, self.db_port, self.db_user, self.db_password = (
            self._resolve_db_fields()
        )
        self._shared_target = self._resolve_shared_target_fields()
        self.shared_target_matches_runtime = self._runtime_matches_shared_target()
        self._validate_db_ownership_guardrail()
        self.echo_sql = self._env_bool("DB_ECHO_SQL", default=False)
        self.timeout_seconds = self._env_int("DB_TIMEOUT", 60)
        self.pool_size = self._env_int("DB_POOL_SIZE", 30)
        max_connections = self._env_int("DB_MAX_CONNECTIONS", 0)
        configured_overflow = self._env_int("DB_MAX_OVERFLOW", 60)
        if max_connections > 0:
            configured_overflow = max(0, max_connections - self.pool_size)
        self.max_overflow = configured_overflow
        self.pool_recycle = self._env_int("DB_POOL_RECYCLE", 3600)
        self.ssl_mode = self._env_bool("SSL_MODE", default=False)

    @staticmethod
    def _fields_from_url(raw_url: str) -> Optional[tuple[str, str, str, str, str]]:
        normalized = DatabaseConfig._normalize_database_url(raw_url)
        if not normalized:
            return None
        parsed = urlparse(normalized)
        db_name = parsed.path.lstrip("/") or "dydx_bot"
        host = parsed.hostname or "localhost"
        port = str(parsed.port or 5432)
        user = parsed.username or "postgres"
        password = parsed.password or ""
        return db_name, host, port, user, password

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
            return "postgresql+psycopg2://" + candidate[len("postgresql://"):]
        if lowered.startswith("postgres://"):
            return "postgresql+psycopg2://" + candidate[len("postgres://"):]
        raise ValueError(
            "Unsupported database URL scheme. Only PostgreSQL URLs are supported."
        )

    def _resolve_database_url(self) -> str:
        """Resolve optional explicit database URL with cutover-mode behavior."""
        bot_url = self._normalize_database_url(os.getenv("BOT_DATABASE_URL", ""))
        shared_url = self._normalize_database_url(os.getenv("DATABASE_URL", ""))

        if self.cutover_mode == "shared":
            if shared_url:
                self.connection_source = "shared_database_url"
            return shared_url
        if self.cutover_mode == "dedicated":
            if bot_url:
                self.connection_source = "bot_database_url"
                return bot_url
            if self._has_bot_db_fields():
                self.connection_source = "bot_db_fields"
                return ""
            raise ValueError(
                "BOT_DB_CUTOVER_MODE=dedicated requires BOT_DATABASE_URL or BOT_DB_* values"
            )

        # dedicated_with_shared_fallback
        if bot_url:
            self.connection_source = "bot_database_url"
            return bot_url
        if shared_url:
            self.connection_source = "shared_database_url"
            return shared_url
        self.connection_source = "constructed_fields"
        return ""

    def _resolve_db_fields(self) -> tuple[str, str, str, str, str]:
        """Resolve host/port/name/user/password based on cutover mode."""
        if self.cutover_mode == "shared":
            self.field_source = "shared_db_fields"
            shared_url = self._normalize_database_url(os.getenv("DATABASE_URL", ""))
            if shared_url:
                parsed_fields = self._fields_from_url(shared_url)
                if parsed_fields is not None:
                    self.field_source = "shared_database_url"
                    return parsed_fields
            return (
                self._env("DB_NAME", self._env("POSTGRES_DB", "dydx_bot")),
                self._env("DB_HOST", self._env("POSTGRES_HOST", "localhost")),
                self._env("DB_PORT", self._env("POSTGRES_PORT", "5432")),
                self._env("DB_USER", self._env("POSTGRES_USER", "postgres")),
                self._env("DB_PASSWORD", self._env("POSTGRES_PASSWORD", "")),
            )

        if self.cutover_mode == "dedicated":
            if self.database_url:
                parsed_fields = self._fields_from_url(self.database_url)
                if parsed_fields is not None:
                    self.field_source = "bot_database_url"
                    return parsed_fields
                self.field_source = "bot_db_fields"
                return self._bot_db_fields()
            if self._has_bot_db_fields():
                self.field_source = "bot_db_fields"
                return self._bot_db_fields()
            raise ValueError(
                "BOT_DB_CUTOVER_MODE=dedicated requires BOT_DB_HOST, BOT_DB_PORT, "
                "BOT_DB_NAME, BOT_DB_USER, and BOT_DB_PASSWORD when BOT_DATABASE_URL is unset"
            )

        # dedicated_with_shared_fallback
        if self.database_url and self.connection_source == "bot_database_url":
            parsed_fields = self._fields_from_url(self.database_url)
            if parsed_fields is not None:
                self.field_source = "bot_database_url"
                return parsed_fields
        if self._has_bot_db_fields():
            self.field_source = "bot_db_fields"
            return self._bot_db_fields()
        shared_url = self._normalize_database_url(os.getenv("DATABASE_URL", ""))
        if shared_url:
            parsed_fields = self._fields_from_url(shared_url)
            if parsed_fields is not None:
                self.field_source = "shared_database_url"
                return parsed_fields
        self.field_source = "shared_db_fields"
        return (
            self._env("DB_NAME", self._env("POSTGRES_DB", "dydx_bot")),
            self._env("DB_HOST", self._env("POSTGRES_HOST", "localhost")),
            self._env("DB_PORT", self._env("POSTGRES_PORT", "5432")),
            self._env("DB_USER", self._env("POSTGRES_USER", "postgres")),
            self._env("DB_PASSWORD", self._env("POSTGRES_PASSWORD", "")),
        )

    def to_diagnostics(self) -> dict:
        """Build a sanitized runtime diagnostics payload without exposing secrets."""
        return {
            "db_type": self.db_type,
            "cutover_mode": self.cutover_mode,
            "connection_source": self.connection_source,
            "field_source": self.field_source,
            "database_url_configured": bool(self.database_url),
            "host": self.db_host,
            "port": self.db_port,
            "name": self.db_name,
            "user": self.db_user,
            "password_configured": bool(self.db_password),
            "timeout_seconds": self.timeout_seconds,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "max_connections": self.pool_size + self.max_overflow,
            "ssl_enabled": self.ssl_mode,
            "echo_sql": self.echo_sql,
            "shared_target_detected": self._shared_target is not None,
            "shared_target_matches_runtime": self.shared_target_matches_runtime,
            "ownership_guardrail": "enforced" if self.cutover_mode == "dedicated" else "advisory",
        }

    @staticmethod
    def _normalized_target_fields(
            fields: tuple[str, str, str, str, str] | None,
    ) -> tuple[str, str, str] | None:
        if fields is None:
            return None
        db_name, host, port, _, _ = fields
        return (
            (host or "").strip().lower(),
            str(port or "").strip(),
            (db_name or "").strip().lower(),
        )

    def _resolve_shared_target_fields(self) -> tuple[str, str, str, str, str] | None:
        shared_url = self._normalize_database_url(os.getenv("DATABASE_URL", ""))
        if shared_url:
            parsed_fields = self._fields_from_url(shared_url)
            if parsed_fields is not None:
                return parsed_fields

        shared_fields = (
            self._env("DB_NAME", self._env("POSTGRES_DB", "")),
            self._env("DB_HOST", self._env("POSTGRES_HOST", "")),
            self._env("DB_PORT", self._env("POSTGRES_PORT", "")),
            self._env("DB_USER", self._env("POSTGRES_USER", "")),
            self._env("DB_PASSWORD", self._env("POSTGRES_PASSWORD", "")),
        )
        if any(bool(str(value).strip()) for value in shared_fields):
            return shared_fields
        return None

    def _runtime_matches_shared_target(self) -> bool:
        runtime_target = self._normalized_target_fields(
            (self.db_name, self.db_host, self.db_port, self.db_user, self.db_password)
        )
        shared_target = self._normalized_target_fields(self._shared_target)
        return bool(runtime_target and shared_target and runtime_target == shared_target)

    def _validate_db_ownership_guardrail(self) -> None:
        if self.cutover_mode != "dedicated":
            return
        if self.shared_target_matches_runtime:
            raise ValueError(
                "BOT_DB_CUTOVER_MODE=dedicated cannot target the same database as the shared DB configuration"
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
            "pool_timeout": self.timeout_seconds,
            "connect_args": {
                "connect_timeout": self.timeout_seconds,
                "keepalives": 1,
                "keepalives_idle": 30,
                **({"sslmode": "require"} if self.ssl_mode else {}),
            },
        }


class DatabaseManager:
    """Database connection and session management"""

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None
    _fork_hook_registered: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._initialize()
        self._register_fork_hook()

    def _register_fork_hook(self):
        if self._fork_hook_registered:
            return
        register_at_fork = getattr(os, "register_at_fork", None)
        if register_at_fork is None:
            return

        register_at_fork(after_in_child=self._after_fork_child_reset)
        self._fork_hook_registered = True

    def _after_fork_child_reset(self):
        """Ensure child processes never reuse inherited pooled DB sockets."""
        if self._engine is None:
            return
        try:
            self._engine.dispose()
            logger.info("Disposed inherited SQLAlchemy pool in forked child process")
        except Exception as exc:
            logger.warning("Failed disposing inherited SQLAlchemy pool in child: {}", exc)

    def _initialize(self):
        """Initialize database engine and session factory"""
        config = DatabaseConfig()
        connection_string = config.get_connection_string()
        engine_kwargs = config.get_engine_kwargs()

        def _redact_connection_string(raw: str) -> str:
            parsed = urlparse(raw)
            if parsed.scheme and parsed.hostname:
                port = f":{parsed.port}" if parsed.port else ""
                db_name = parsed.path.lstrip("/")
                db_segment = f"/{db_name}" if db_name else ""
                return f"{parsed.scheme}://***:***@{parsed.hostname}{port}{db_segment}"
            return "configured (redacted)"

        logger.info(f"Initializing database: {config.db_type}")
        logger.info(f"Connection string: {_redact_connection_string(connection_string)}")

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

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Provide a transactional session scope with safe cleanup."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

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
                          AND c.column_name = 'status' LIMIT 1
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

            if inspector.has_table("jobs"):
                job_columns = {
                    column["name"]: column for column in inspector.get_columns("jobs")
                }
                bot_id_column = job_columns.get("bot_id")
                if bot_id_column is not None and not bool(bot_id_column.get("nullable", True)):
                    logger.info("Applying compatibility fix: allowing jobs.bot_id to be nullable")
                    connection.execute(
                        text("ALTER TABLE jobs ALTER COLUMN bot_id DROP NOT NULL")
                    )

            if inspector.has_table("backtest_runtime_runs"):
                run_columns = {
                    column["name"] for column in inspector.get_columns("backtest_runtime_runs")
                }
                add_column_sql = {
                    "started_at": "ALTER TABLE backtest_runtime_runs ADD COLUMN started_at TIMESTAMP NULL",
                    "completed_at": "ALTER TABLE backtest_runtime_runs ADD COLUMN completed_at TIMESTAMP NULL",
                    "deadline_at": "ALTER TABLE backtest_runtime_runs ADD COLUMN deadline_at TIMESTAMP NULL",
                    "timeout_seconds": "ALTER TABLE backtest_runtime_runs ADD COLUMN timeout_seconds FLOAT NULL",
                }
                for column_name, statement in add_column_sql.items():
                    if column_name not in run_columns:
                        logger.info(
                            "Applying compatibility fix: adding backtest_runtime_runs.{}",
                            column_name,
                        )
                        connection.execute(text(statement))

                logger.info("Applying compatibility fix: normalizing backtest runtime statuses")
                connection.execute(
                    text(
                        """
                        UPDATE backtest_runtime_runs
                        SET status = CASE
                            WHEN status IS NULL THEN 'pending'
                            ELSE CASE LOWER(CAST(status AS TEXT))
                            WHEN 'created' THEN 'pending'
                            WHEN 'queued' THEN 'pending'
                            WHEN 'scheduled' THEN 'pending'
                            WHEN 'in_progress' THEN 'running'
                            WHEN 'processing' THEN 'running'
                            WHEN 'active' THEN 'running'
                            WHEN 'succeeded' THEN 'completed'
                            WHEN 'success' THEN 'completed'
                            WHEN 'done' THEN 'completed'
                            WHEN 'error' THEN 'failed'
                            WHEN 'timed_out' THEN 'timeout'
                            WHEN 'stalled' THEN 'stale'
                            WHEN 'canceled' THEN 'cancelled'
                            ELSE LOWER(CAST(status AS TEXT))
                            END
                        END
                        WHERE status IS NULL
                           OR LOWER(CAST(status AS TEXT)) IN (
                                'created', 'queued', 'scheduled', 'in_progress',
                                'processing', 'active', 'succeeded', 'success',
                                'done', 'error', 'timed_out', 'stalled', 'canceled'
                           )
                        """
                    )
                )

    def verify_required_tables(self) -> dict:
        """Verify runtime-critical tables are present in the active bot database."""
        required = {
            "bot_instances",
            "jobs",
            "event_logs",
            "trades",
            "backtest_runtime_runs",
        }
        engine = self.get_engine()
        inspector = inspect(engine)
        present = set(inspector.get_table_names())
        missing = sorted(required - present)
        if missing:
            raise RuntimeError(
                "Bot database schema is missing required tables: "
                + ", ".join(missing)
            )
        return {"required": sorted(required), "missing": missing}

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

        # ── Pre-migration connection eviction ─────────────────────────────────
        # CREATE INDEX CONCURRENTLY waits for all transactions that were open
        # when the build starts to finish.  Long-lived connections from worker
        # subprocesses and the API server's own pool would cause it to hang
        # indefinitely.  We therefore:
        #   1. Dispose our own pool so those connections are not counted.
        #   2. Terminate every other client backend on this database so
        #      CONCURRENTLY can obtain a clean snapshot immediately.
        # Worker subprocesses reconnect transparently on their next query via
        # SQLAlchemy's connection-checkout retry / pool_pre_ping logic.
        self._engine.dispose()
        try:
            with self._engine.connect().execution_options(isolation_level="AUTOCOMMIT") as _conn:
                result = _conn.execute(
                    text(
                        """
                        SELECT COUNT(pg_terminate_backend(pid))
                        FROM pg_stat_activity
                        WHERE datname = current_database()
                          AND pid <> pg_backend_pid()
                          AND backend_type = 'client backend'
                        """
                    )
                )
                terminated = result.scalar() or 0
                if terminated:
                    logger.warning(
                        "Terminated {} other DB connection(s) to allow lock-free index "
                        "migrations. They will reconnect automatically.",
                        terminated,
                    )
        except Exception as _evict_err:
            # Non-superuser roles may lack pg_terminate_backend permission.
            # Log and continue — migrations will still run, but CONCURRENTLY
            # steps may be slower if other connections are present.
            logger.warning(
                "Could not evict other DB connections before migration ({}). "
                "Proceeding anyway — migrations may be slower.",
                _evict_err,
            )

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
