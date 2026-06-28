"""Database configuration and connection management for PostgreSQL."""

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlencode, urlparse

# =============================================================================
# macOS multiprocessing workaround
# =============================================================================
# On macOS, the default fork() multiprocessing start method is incompatible with
# the Objective-C runtime. If any library (e.g., PIL/Pillow via qrcode, pandas, etc.)
# has initialized the Objective-C runtime in the parent process, child processes
# created via fork() will crash with:
#   "objc_initializeAfterForkError: Objective-C runtime was already initialized..."
# 
# Solution: Use 'spawn' as the multiprocessing start method on macOS.
# This must be set BEFORE any imports that might trigger Objective-C initialization.
# =============================================================================
if sys.platform == "darwin":
    # On macOS, set multiprocessing start method to 'spawn'
    # This must happen before any other imports that might load Objective-C
    import multiprocessing
    try:
        multiprocessing.set_start_method("spawn", force=True)
        os.environ["PYTHON_MULTIPROCESSING_START_METHOD"] = "spawn"
    except RuntimeError:
        # Already set, that's fine
        pass

from alembic import command
from alembic.config import Config
from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool


class DatabaseConfig:
    """Database configuration manager"""

    _SUPPORTED_DB_TYPES = {"postgres", "postgresql"}
    _SUPPORTED_URL_SCHEMES = {
        "postgres://",
        "postgresql://",
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
    }

    @staticmethod
    def _env(name: str, fallback: str = "") -> str:
        value = os.getenv(name)
        if value in (None, ""):
            return fallback
        return str(value)

    @classmethod
    def _env_any(cls, names: tuple[str, ...], fallback: str = "") -> str:
        for name in names:
            value = os.getenv(name)
            if value not in (None, ""):
                return str(value)
        return fallback

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        value = os.getenv(name)
        if value in (None, ""):
            return default
        try:
            value_str = str(value)
            return int(value_str)
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
            os.getenv("BOT_DB_CUTOVER_MODE", "shared").strip().lower().replace("-", "_")
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

        self.db_type = self._resolve_db_type()
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
    def _normalize_db_type(db_type: str) -> str:
        value = (db_type or "").strip().lower()
        if value in {"postgres", "postgresql"}:
            return "postgres"
        if value:
            raise ValueError(
                f"Unsupported DB_TYPE '{value}'. Supported: postgres, postgresql."
            )
        return "postgres"

    def _resolve_db_type(self) -> str:
        bot_type_raw = self._env("BOT_DB_TYPE", "")
        shared_type_raw = self._env("DB_TYPE", "")

        bot_type = self._normalize_db_type(bot_type_raw) if bot_type_raw else ""
        shared_type = (
            self._normalize_db_type(shared_type_raw) if shared_type_raw else ""
        )

        if bot_type and shared_type and bot_type != shared_type:
            if self.cutover_mode == "shared":
                raise ValueError(
                    "Conflicting BOT_DB_TYPE and DB_TYPE values are not allowed; use a single database mode"
                )
            # Dedicated bot modes may intentionally diverge from shared DB settings.
            shared_type = ""

        explicit_type = bot_type or shared_type

        inferred_types = {
            self._url_db_type(self._env("BOT_DATABASE_URL", "")),
            self._url_db_type(self._env("DATABASE_URL", "")),
        }
        inferred_types.discard(None)
        if len(inferred_types) > 1:
            raise ValueError(
                "Mixed database URL modes are not supported; BOT_DATABASE_URL and DATABASE_URL must use the same family"
            )

        inferred_type = next(iter(inferred_types), None)
        if explicit_type and inferred_type and explicit_type != inferred_type:
            raise ValueError(
                "Conflicting DB_TYPE and database URL schemes are not allowed"
            )

        return explicit_type or inferred_type or "postgres"

    @staticmethod
    def _url_db_type(raw_url: str) -> Optional[str]:
        candidate = (raw_url or "").strip().lower()
        if not candidate:
            return None
        if candidate.startswith(("postgres://", "postgresql://", "postgresql+")):
            return "postgres"
        raise ValueError(f"Unsupported database URL scheme: {raw_url}")

    def _fields_from_url(
        self, raw_url: str
    ) -> Optional[tuple[str, str, str, str, str]]:
        normalized = self._normalize_database_url(raw_url)
        if not normalized:
            return None
        parsed = urlparse(normalized)
        db_name = parsed.path.lstrip("/") or "dydx_bot"
        host = parsed.hostname or "localhost"
        port = str(parsed.port or 5432)
        user = parsed.username or "dydx_bot"
        password = parsed.password or ""
        return db_name, host, port, user, password

    def _normalize_database_url(self, raw_url: str) -> str:
        """Normalize a PostgreSQL URL for SQLAlchemy."""
        candidate = (raw_url or "").strip()
        if not candidate:
            return ""
        lowered = candidate.lower()
        if lowered.startswith(("postgres://", "postgresql://")):
            return "postgresql+psycopg2://" + candidate.split("://", 1)[1]
        if lowered.startswith(("postgresql+psycopg://", "postgresql+psycopg2://")):
            return candidate
        raise ValueError(
            "Unsupported database URL scheme. Supported: postgres, postgresql."
        )

    def _validate_url_type(self, raw_url: str, url_name: str) -> None:
        url_type = self._url_db_type(raw_url)
        if url_type and url_type != self.db_type:
            raise ValueError(
                f"{url_name} uses {url_type} but the resolved DB type is {self.db_type}"
            )

    def _resolve_database_url(self) -> str:
        """Resolve optional explicit database URL with cutover-mode behavior."""
        bot_raw = os.getenv("BOT_DATABASE_URL", "")
        shared_raw = os.getenv("DATABASE_URL", "")

        self._validate_url_type(bot_raw, "BOT_DATABASE_URL")
        self._validate_url_type(shared_raw, "DATABASE_URL")

        bot_url = self._normalize_database_url(bot_raw)
        shared_url = self._normalize_database_url(shared_raw)

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
        default_port = "5432"
        default_user = "dydx_bot"

        if self.cutover_mode == "shared":
            self.field_source = "shared_db_fields"
            shared_url = self._normalize_database_url(os.getenv("DATABASE_URL", ""))
            if shared_url:
                parsed_fields = self._fields_from_url(shared_url)
                if parsed_fields is not None:
                    self.field_source = "shared_database_url"
                    return parsed_fields
            return (
                self._env_any(("DB_NAME", "POSTGRES_DB"), "dydx_bot"),
                self._env_any(("DB_HOST", "POSTGRES_HOST"), "localhost"),
                self._env_any(("DB_PORT", "POSTGRES_PORT"), default_port),
                self._env_any(("DB_USER", "POSTGRES_USER"), default_user),
                self._env_any(("DB_PASSWORD", "POSTGRES_PASSWORD"), ""),
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
            self._env_any(("DB_NAME", "POSTGRES_DB"), "dydx_bot"),
            self._env_any(("DB_HOST", "POSTGRES_HOST"), "localhost"),
            self._env_any(("DB_PORT", "POSTGRES_PORT"), default_port),
            self._env_any(("DB_USER", "POSTGRES_USER"), default_user),
            self._env_any(("DB_PASSWORD", "POSTGRES_PASSWORD"), ""),
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
            "ownership_guardrail": (
                "enforced" if self.cutover_mode == "dedicated" else "advisory"
            ),
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
            self._env_any(("DB_NAME", "POSTGRES_DB"), ""),
            self._env_any(("DB_HOST", "POSTGRES_HOST"), ""),
            self._env_any(("DB_PORT", "POSTGRES_PORT"), ""),
            self._env_any(("DB_USER", "POSTGRES_USER"), ""),
            self._env_any(("DB_PASSWORD", "POSTGRES_PASSWORD"), ""),
        )
        if any(bool(str(value).strip()) for value in shared_fields):
            return shared_fields
        return None

    def _runtime_matches_shared_target(self) -> bool:
        runtime_target = self._normalized_target_fields(
            (self.db_name, self.db_host, self.db_port, self.db_user, self.db_password)
        )
        shared_target = self._normalized_target_fields(self._shared_target)
        return bool(
            runtime_target and shared_target and runtime_target == shared_target
        )

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
            os.getenv("BOT_DB_USER", "dydx_bot"),
            os.getenv("BOT_DB_PASSWORD", ""),
        )

    def get_connection_string(self) -> str:
        """Generate database connection string"""
        if self.database_url:
            return self.database_url

        driver = "postgresql+psycopg2"
        query = urlencode(
            {
                "sslmode": "require" if self.ssl_mode else "disable",
                "connect_timeout": self.timeout_seconds,
                "options": "-c timezone=UTC",
            }
        )
        return (
            f"{driver}://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?{query}"
        )

    def get_engine_kwargs(self) -> dict:
        """Get SQLAlchemy engine kwargs based on database type."""
        connect_args: dict[str, object] = {
            "connect_timeout": self.timeout_seconds,
            "options": "-c timezone=UTC",
        }

        return {
            "echo": self.echo_sql,
            "future": True,
            "poolclass": QueuePool,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_recycle": self.pool_recycle,
            "pool_timeout": self.timeout_seconds,
            "connect_args": connect_args,
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
        """Ensure child processes never reuse inherited pooled DB sockets.
        
        Note: With 'spawn' start method (used on macOS), child processes start
        fresh with no inherited connections, so this cleanup is primarily for
        'fork' start method compatibility on Linux/Unix systems.
        """
        if self._engine is None:
            return
        try:
            self._engine.dispose()
            logger.info("Disposed inherited SQLAlchemy pool in forked child process")
        except Exception as exc:
            logger.warning(
                "Failed disposing inherited SQLAlchemy pool in child: {}", exc
            )

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
        logger.info(
            f"Connection string: {_redact_connection_string(connection_string)}"
        )

        self._engine = create_engine(connection_string, **engine_kwargs)
        self.config = config

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
        engine = self._engine
        if engine is None:
            raise RuntimeError("Database engine is not initialized")
        return engine

    def get_session(self) -> Session:
        """Get new database session"""
        if self._session_factory is None:
            self._initialize()
        session_factory = self._session_factory
        if session_factory is None:
            raise RuntimeError("Database session factory is not initialized")
        return session_factory()

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
                logger.info(
                    "Applying compatibility fix: normalizing bot_instances.status values"
                )

                connection.execute(text("""
                        UPDATE bot_instances
                        SET status = CASE LOWER(status::text)
                                         WHEN 'failed' THEN 'error'
                                         WHEN 'paused' THEN 'stopped'
                                         ELSE status::text
                                    END::botstatusenum
                        WHERE LOWER(status::text) <> status::text
                           OR LOWER(status::text) IN ('failed', 'paused')
                        """))

            if inspector.has_table("backtest_strategies"):
                columns = {
                    column["name"]
                    for column in inspector.get_columns("backtest_strategies")
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

            if inspector.has_table("positions_realtime"):
                realtime_columns = {
                    column["name"]
                    for column in inspector.get_columns("positions_realtime")
                }
                realtime_compat_columns = {
                    "hedge_ratio": (
                        "ALTER TABLE positions_realtime "
                        "ADD COLUMN hedge_ratio DOUBLE PRECISION NULL"
                    ),
                    "correlation": (
                        "ALTER TABLE positions_realtime "
                        "ADD COLUMN correlation DOUBLE PRECISION NULL"
                    ),
                    "half_life": (
                        "ALTER TABLE positions_realtime "
                        "ADD COLUMN half_life DOUBLE PRECISION NULL"
                    ),
                    "funding_rate": (
                        "ALTER TABLE positions_realtime "
                        "ADD COLUMN funding_rate DOUBLE PRECISION NULL"
                    ),
                    "dydx_order_ids": (
                        "ALTER TABLE positions_realtime "
                        "ADD COLUMN dydx_order_ids JSON NULL"
                    ),
                    "dydx_position_id": (
                        "ALTER TABLE positions_realtime "
                        "ADD COLUMN dydx_position_id VARCHAR(100) NULL"
                    ),
                }
                for column_name, statement in realtime_compat_columns.items():
                    if column_name not in realtime_columns:
                        logger.info(
                            "Applying compatibility fix: adding positions_realtime.{}",
                            column_name,
                        )
                        connection.execute(text(statement))

            if inspector.has_table("jobs"):
                job_columns = {
                    column["name"]: column for column in inspector.get_columns("jobs")
                }
                bot_id_column = job_columns.get("bot_id")
                if bot_id_column is not None and not bool(
                    bot_id_column.get("nullable", True)
                ):
                    logger.info(
                        "Applying compatibility fix: allowing jobs.bot_id to be nullable"
                    )
                    connection.execute(
                        text("ALTER TABLE jobs ALTER COLUMN bot_id DROP NOT NULL")
                    )

            if inspector.has_table("backtest_runtime_runs"):
                run_columns = {
                    column["name"]
                    for column in inspector.get_columns("backtest_runtime_runs")
                }
                add_column_sql = {
                    "started_at": "ALTER TABLE backtest_runtime_runs ADD COLUMN started_at TIMESTAMP NULL",
                    "completed_at": "ALTER TABLE backtest_runtime_runs ADD COLUMN completed_at TIMESTAMP NULL",
                    "deadline_at": "ALTER TABLE backtest_runtime_runs ADD COLUMN deadline_at TIMESTAMP NULL",
                    "timeout_seconds": "ALTER TABLE backtest_runtime_runs ADD COLUMN timeout_seconds FLOAT NULL",
                    "artifact_refs": "ALTER TABLE backtest_runtime_runs ADD COLUMN artifact_refs JSONB NULL",
                    "analytics_rows_written": "ALTER TABLE backtest_runtime_runs ADD COLUMN analytics_rows_written INTEGER NULL DEFAULT 0",
                }
                for column_name, statement in add_column_sql.items():
                    if column_name not in run_columns:
                        logger.info(
                            "Applying compatibility fix: adding backtest_runtime_runs.{}",
                            column_name,
                        )
                        connection.execute(text(statement))

                logger.info(
                    "Applying compatibility fix: normalizing backtest runtime statuses"
                )
                connection.execute(text("""
                        UPDATE backtest_runtime_runs
                        SET status = CASE
                            WHEN status IS NULL THEN 'pending'
                            ELSE CASE LOWER(status)
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
                            ELSE LOWER(status)
                            END
                        END
                        WHERE status IS NULL
                           OR LOWER(status) IN (
                                'created', 'queued', 'scheduled', 'in_progress',
                                'processing', 'active', 'succeeded', 'success',
                                'done', 'error', 'timed_out', 'stalled', 'canceled'
                           )
                        """))

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
                "Bot database schema is missing required tables: " + ", ".join(missing)
            )
        return {"required": sorted(required), "missing": missing}

    def _build_alembic_config(self) -> Optional[Config]:
        config = DatabaseConfig()
        alembic_path = Path(__file__).resolve().parents[1] / "alembic.ini"
        if not alembic_path.exists():
            logger.warning(
                "Alembic config not found at {}; skipping migrations", alembic_path
            )
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

            has_core_schema = inspector.has_table(
                "bot_instances"
            ) and inspector.has_table("backtest_strategies")
            if not has_core_schema:
                logger.info(
                    "Skipping Alembic baseline stamp: core legacy tables not detected"
                )
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
        baseline_status = self.ensure_alembic_baseline(
            baseline_revision=baseline_revision
        )
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

    # --- Admin user seeding logic ---
    import os

    from src.api.auth_utils import PasswordUtils
    from src.infrastructure.domain.models.auth_models import User
    from src.shared.time_utils import utc_now

    admin_username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip() or "admin"
    admin_email = (
        os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@localhost").strip()
        or "admin@localhost"
    )
    admin_password = (
        os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin123").strip() or "admin123"
    )

    if not admin_password:
        logger.warning("Skipping admin user creation: BOOTSTRAP_ADMIN_PASSWORD not set")
        return

    with db.session_scope() as session:
        existing = session.query(User).filter(User.username == admin_username).first()
        if existing:
            logger.info(f"Admin user '{admin_username}' already exists")
            return

        hashed = PasswordUtils.hash_password(admin_password[:72])
        admin_user = User(
            username=admin_username,
            email=admin_email,
            hashed_password=hashed,
            full_name="System Administrator",
            is_active=True,
            is_admin=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(admin_user)
        session.commit()
        logger.info(f"✅ Admin user '{admin_username}' created (email: {admin_email})")
        logger.info("⚠️  IMPORTANT: Change the default password after first login!")


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
