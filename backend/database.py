"""
Database connection and session management module.
Handles both SQLite (local/testing) and PostgreSQL (production) databases.
Uses configuration from config/config.py for database settings.
"""

from typing import Optional, Type, TypeVar, List, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, Engine, text, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool, QueuePool, StaticPool
import logging
import os

from config.config import DatabaseSettings
from models.sqlmodel_models import SQLModel

logger = logging.getLogger(__name__)

# Type variable for generic CRUD operations
T = TypeVar('T', bound=SQLModel)


class Database:
    """
    Database connection manager supporting both SQLite and PostgreSQL.
    Provides session management, connection pooling, and query utilities.
    """

    _instance: Optional['Database'] = None
    _engine: Optional[Engine] = None
    _session_maker: Optional[sessionmaker] = None
    _config: Optional[DatabaseSettings] = None

    def __new__(cls) -> 'Database':
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, config: Optional[DatabaseSettings] = None, echo: bool = False) -> 'Database':
        """
        Initialize database connection with configuration.
        
        Args:
            config: DatabaseSettings object. If None, uses environment variables.
            echo: Whether to echo SQL queries to logger.
            
        Returns:
            Database instance (singleton)
        """
        instance = cls()
        
        # Use provided config or create from environment
        if config is None:
            config = cls._load_config_from_env()
        
        cls._config = config
        
        logger.info(f"Initializing database: {config.type} at {config.host}:{config.port}/{config.dbname}")
        
        # Create engine based on database type
        if config.type == "sqlite":
            cls._engine = cls._create_sqlite_engine(config.dbname, echo)
        elif config.type == "postgresql":
            cls._engine = cls._create_postgresql_engine(config, echo)
        else:
            raise ValueError(f"Unsupported database type: {config.type}")
        
        # Create session factory
        cls._session_maker = sessionmaker(bind=cls._engine, expire_on_commit=False)
        
        # Create all tables
        cls._create_tables()
        
        logger.info(f"Database initialized successfully: {config.type}")
        return instance

    @staticmethod
    def _load_config_from_env() -> DatabaseSettings:
        """Load database configuration from environment variables."""
        db_type = os.getenv("DB_TYPE", "sqlite")
        
        if db_type == "sqlite":
            db_name = os.getenv("DB_NAME", "dydx_bot.db")
            return DatabaseSettings(type="sqlite", dbname=db_name)
        else:
            # PostgreSQL settings
            return DatabaseSettings(
                type="postgresql",
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                dbname=os.getenv("DB_NAME", "dydx_bot"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", ""),
                ssl=os.getenv("DB_SSL", "false").lower() == "true",
                timeout=int(os.getenv("DB_TIMEOUT", "5")),
                max_connections=int(os.getenv("DB_MAX_CONNECTIONS", "10")),
                pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
                max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            )

    @staticmethod
    def _create_sqlite_engine(db_path: str, echo: bool = False) -> Engine:
        """Create SQLite engine with connection pooling."""
        # Ensure database directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        # SQLite connection string
        connection_string = f"sqlite:///{db_path}"
        
        # Create engine with thread-safe settings for SQLite
        engine = create_engine(
            connection_string,
            echo=echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if db_path == ":memory:" else QueuePool,
            pool_size=1,
            max_overflow=0,
        )
        
        # Enable foreign keys for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        logger.info(f"SQLite engine created: {db_path}")
        return engine

    @staticmethod
    def _create_postgresql_engine(config: DatabaseSettings, echo: bool = False) -> Engine:
        """Create PostgreSQL engine with connection pooling."""
        # Add SSL settings if enabled
        connect_args = {"connect_timeout": config.timeout}
        if config.ssl:
            connect_args["sslmode"] = "require"
        
        engine = create_engine(
            config.dsn,
            echo=echo,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_pre_ping=True,  # Verify connections before using them
            connect_args=connect_args,
        )
        
        logger.info(f"PostgreSQL engine created: {config.host}:{config.port}/{config.dbname}")
        return engine

    @classmethod
    def _create_tables(cls) -> None:
        """Create all database tables from SQLModel models."""
        if cls._engine is None:
            raise RuntimeError("Database engine not initialized. Call Database.initialize() first.")
        
        try:
            SQLModel.metadata.create_all(cls._engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise

    @classmethod
    def get_session(cls) -> Session:
        """
        Get a new database session.
        
        Returns:
            SQLAlchemy Session instance
        """
        if cls._session_maker is None:
            raise RuntimeError("Database not initialized. Call Database.initialize() first.")
        
        return cls._session_maker()

    @classmethod
    @contextmanager
    def session_context(cls):
        """
        Context manager for session handling with automatic commit/rollback.
        
        Usage:
            with Database.session_context() as session:
                user = session.query(User).first()
        """
        session = cls.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def get_engine(cls) -> Engine:
        """Get the SQLAlchemy engine."""
        if cls._engine is None:
            raise RuntimeError("Database engine not initialized.")
        return cls._engine

    @classmethod
    def get_config(cls) -> DatabaseSettings:
        """Get the database configuration."""
        if cls._config is None:
            raise RuntimeError("Database not configured.")
        return cls._config

    @classmethod
    def is_postgresql(cls) -> bool:
        """Check if using PostgreSQL."""
        return cls._config and cls._config.type == "postgresql"

    @classmethod
    def is_sqlite(cls) -> bool:
        """Check if using SQLite."""
        return cls._config and cls._config.type == "sqlite"

    @classmethod
    def health_check(cls) -> bool:
        """
        Perform a health check on the database connection.
        
        Returns:
            True if database is healthy, False otherwise
        """
        try:
            with cls.session_context() as session:
                session.execute(text("SELECT 1"))
            logger.info("Database health check passed")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    @classmethod
    def drop_all_tables(cls) -> None:
        """
        Drop all tables from the database.
        WARNING: This will delete all data!
        """
        if cls._engine is None:
            raise RuntimeError("Database engine not initialized.")
        
        logger.warning("Dropping all database tables!")
        SQLModel.metadata.drop_all(cls._engine)
        logger.info("All tables dropped")

    @classmethod
    def reset_database(cls) -> None:
        """Reset database by dropping and recreating all tables."""
        logger.warning("Resetting database - this will delete all data!")
        cls.drop_all_tables()
        cls._create_tables()
        logger.info("Database reset complete")


# ========== CRUD Operations Helper ==========

class CRUDBase:
    """Base class for CRUD operations on SQLModel models."""

    @staticmethod
    def create(session: Session, db_model: Type[T], **kwargs) -> T:
        """
        Create a new record.
        
        Args:
            session: Database session
            db_model: SQLModel class
            **kwargs: Field values
            
        Returns:
            Created model instance
        """
        db_obj = db_model(**kwargs)
        session.add(db_obj)
        session.flush()
        return db_obj

    @staticmethod
    def get_by_id(session: Session, db_model: Type[T], obj_id: int) -> Optional[T]:
        """Get record by ID."""
        return session.query(db_model).filter(db_model.id == obj_id).first()

    @staticmethod
    def get_all(
        session: Session,
        db_model: Type[T],
        skip: int = 0,
        limit: int = 100,
        **filters
    ) -> List[T]:
        """
        Get multiple records with pagination and filters.
        
        Args:
            session: Database session
            db_model: SQLModel class
            skip: Number of records to skip
            limit: Maximum records to return
            **filters: Filter conditions (field=value)
            
        Returns:
            List of model instances
        """
        query = session.query(db_model)
        for key, value in filters.items():
            if hasattr(db_model, key):
                query = query.filter(getattr(db_model, key) == value)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def update(session: Session, db_model: Type[T], obj_id: int, **kwargs) -> Optional[T]:
        """
        Update a record.
        
        Args:
            session: Database session
            db_model: SQLModel class
            obj_id: Record ID
            **kwargs: Fields to update
            
        Returns:
            Updated model instance or None if not found
        """
        db_obj = session.query(db_model).filter(db_model.id == obj_id).first()
        if not db_obj:
            return None
        
        for key, value in kwargs.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)
        
        session.flush()
        return db_obj

    @staticmethod
    def delete(session: Session, db_model: Type[T], obj_id: int) -> bool:
        """
        Delete a record.
        
        Args:
            session: Database session
            db_model: SQLModel class
            obj_id: Record ID
            
        Returns:
            True if deleted, False if not found
        """
        db_obj = session.query(db_model).filter(db_model.id == obj_id).first()
        if not db_obj:
            return False
        
        session.delete(db_obj)
        session.flush()
        return True

    @staticmethod
    def delete_all(session: Session, db_model: Type[T], **filters) -> int:
        """
        Delete all records matching filters.
        
        Args:
            session: Database session
            db_model: SQLModel class
            **filters: Filter conditions
            
        Returns:
            Number of deleted records
        """
        query = session.query(db_model)
        for key, value in filters.items():
            if hasattr(db_model, key):
                query = query.filter(getattr(db_model, key) == value)
        
        count = query.count()
        query.delete()
        session.flush()
        return count

    @staticmethod
    def count(session: Session, db_model: Type[T], **filters) -> int:
        """Count records with optional filters."""
        query = session.query(db_model)
        for key, value in filters.items():
            if hasattr(db_model, key):
                query = query.filter(getattr(db_model, key) == value)
        return query.count()

    @staticmethod
    def exists(session: Session, db_model: Type[T], **filters) -> bool:
        """Check if a record exists."""
        return CRUDBase.count(session, db_model, **filters) > 0


# ========== Convenience Functions ==========

def get_db() -> Session:
    """Dependency injection function for FastAPI."""
    db = Database.get_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


__all__ = [
    "Database",
    "CRUDBase",
    "get_db",
]
