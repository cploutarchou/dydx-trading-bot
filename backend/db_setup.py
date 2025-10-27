"""
Database initialization and setup module.
Provides convenient functions for database setup, initialization, and utility operations.
"""

import logging
from typing import Optional
import os

from config.config import DatabaseSettings
from database import Database
from models.sqlmodel_models import SQLModel

logger = logging.getLogger(__name__)


class DatabaseSetup:
    """Database setup and initialization utilities."""
    
    @staticmethod
    def initialize_from_config(config: DatabaseSettings, echo: bool = False) -> Database:
        """
        Initialize database from config object.
        
        Args:
            config: DatabaseSettings object
            echo: Whether to echo SQL queries
            
        Returns:
            Database instance (singleton)
        """
        logger.info(f"Initializing database from config: {config.type}")
        return Database.initialize(config, echo=echo)
    
    @staticmethod
    def initialize_from_env(echo: bool = False) -> Database:
        """
        Initialize database from environment variables.
        
        Environment variables:
            DB_TYPE: "sqlite" or "postgresql" (default: "sqlite")
            DB_NAME: Database name or file path (default: "dydx_bot.db")
            DB_HOST: PostgreSQL host (default: "localhost")
            DB_PORT: PostgreSQL port (default: "5432")
            DB_USER: PostgreSQL user (default: "postgres")
            DB_PASSWORD: PostgreSQL password
            DB_SSL: Enable SSL for PostgreSQL (default: "false")
            
        Args:
            echo: Whether to echo SQL queries
            
        Returns:
            Database instance (singleton)
        """
        logger.info("Initializing database from environment variables")
        return Database.initialize(echo=echo)
    
    @staticmethod
    def initialize_sqlite_local(db_path: str = "dydx_bot.db", echo: bool = False) -> Database:
        """
        Initialize local SQLite database for development/testing.
        
        Args:
            db_path: Path to SQLite database file
            echo: Whether to echo SQL queries
            
        Returns:
            Database instance
        """
        logger.info(f"Initializing local SQLite database: {db_path}")
        config = DatabaseSettings(type="sqlite", dbname=db_path)
        return Database.initialize(config, echo=echo)
    
    @staticmethod
    def initialize_sqlite_memory(echo: bool = False) -> Database:
        """
        Initialize in-memory SQLite database for testing.
        
        Args:
            echo: Whether to echo SQL queries
            
        Returns:
            Database instance
        """
        logger.info("Initializing in-memory SQLite database")
        config = DatabaseSettings(type="sqlite", dbname=":memory:")
        return Database.initialize(config, echo=echo)
    
    @staticmethod
    def initialize_postgresql(
        host: str = "localhost",
        port: int = 5432,
        database: str = "dydx_bot",
        user: str = "postgres",
        password: str = "",
        ssl: bool = False,
        echo: bool = False
    ) -> Database:
        """
        Initialize PostgreSQL database.
        
        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
            ssl: Enable SSL
            echo: Whether to echo SQL queries
            
        Returns:
            Database instance
        """
        logger.info(f"Initializing PostgreSQL database: {host}:{port}/{database}")
        config = DatabaseSettings(
            type="postgresql",
            host=host,
            port=port,
            dbname=database,
            user=user,
            password=password,
            ssl=ssl
        )
        return Database.initialize(config, echo=echo)


# ========== Utility Functions ==========

def init_db(config: Optional[DatabaseSettings] = None, echo: bool = False) -> Database:
    """
    Initialize database (convenience function).
    
    Args:
        config: DatabaseSettings object or None to use environment
        echo: Whether to echo SQL queries
        
    Returns:
        Database instance
    """
    if config:
        return DatabaseSetup.initialize_from_config(config, echo=echo)
    else:
        return DatabaseSetup.initialize_from_env(echo=echo)


def reset_db() -> None:
    """Reset database by dropping and recreating all tables."""
    logger.warning("Resetting database!")
    db = Database()
    db.reset_database()
    logger.info("Database reset complete")


def create_db_tables() -> None:
    """Create all database tables."""
    logger.info("Creating database tables")
    db = Database()
    db._create_tables()
    logger.info("Database tables created")


def drop_db_tables() -> None:
    """Drop all database tables (WARNING: Destructive!)."""
    logger.warning("Dropping all database tables!")
    db = Database()
    db.drop_all_tables()
    logger.info("All tables dropped")


def check_db_health() -> bool:
    """Check database connection health."""
    db = Database()
    is_healthy = db.health_check()
    if is_healthy:
        logger.info("✓ Database health check passed")
    else:
        logger.error("✗ Database health check failed")
    return is_healthy


def get_db_config() -> DatabaseSettings:
    """Get current database configuration."""
    db = Database()
    config = db.get_config()
    logger.info(f"Database config: {config.type} ({config.host}:{config.port}/{config.dbname})")
    return config


def print_db_info() -> None:
    """Print database information."""
    try:
        db = Database()
        config = db.get_config()
        is_postgres = db.is_postgresql()
        is_sqlite = db.is_sqlite()
        
        print("\n" + "="*60)
        print("DATABASE INFORMATION")
        print("="*60)
        print(f"Type:              {config.type}")
        if is_postgres:
            print(f"Host:              {config.host}:{config.port}")
            print(f"Database:          {config.dbname}")
            print(f"User:              {config.user}")
            print(f"Connection String: {config.dsn}")
        elif is_sqlite:
            print(f"File:              {config.dbname}")
            print(f"Connection String: {config.dsn}")
        print("="*60 + "\n")
    except RuntimeError as e:
        print(f"Database not initialized: {e}")


# ========== CLI Commands ==========

if __name__ == "__main__":
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python db_setup.py [command]")
        print("\nAvailable commands:")
        print("  init-local      - Initialize local SQLite database")
        print("  init-memory     - Initialize in-memory SQLite database")
        print("  init-postgres   - Initialize PostgreSQL database (uses env vars)")
        print("  health          - Check database health")
        print("  info            - Print database information")
        print("  create-tables   - Create database tables")
        print("  drop-tables     - Drop all database tables")
        print("  reset           - Reset database (drop and recreate)")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "init-local":
        db_path = sys.argv[2] if len(sys.argv) > 2 else "dydx_bot.db"
        db = DatabaseSetup.initialize_sqlite_local(db_path, echo=True)
        print_db_info()
    
    elif command == "init-memory":
        db = DatabaseSetup.initialize_sqlite_memory(echo=True)
        print_db_info()
    
    elif command == "init-postgres":
        db = DatabaseSetup.initialize_from_env(echo=True)
        print_db_info()
    
    elif command == "health":
        try:
            db = Database()
            if check_db_health():
                print("✓ Database is healthy")
                sys.exit(0)
            else:
                print("✗ Database check failed")
                sys.exit(1)
        except RuntimeError:
            print("Database not initialized. Run 'init-local' or 'init-postgres' first.")
            sys.exit(1)
    
    elif command == "info":
        try:
            print_db_info()
        except RuntimeError:
            print("Database not initialized.")
            sys.exit(1)
    
    elif command == "create-tables":
        try:
            create_db_tables()
            print("✓ Tables created successfully")
        except RuntimeError as e:
            print(f"✗ Failed to create tables: {e}")
            sys.exit(1)
    
    elif command == "drop-tables":
        try:
            response = input("WARNING: This will delete all data! Continue? (yes/no): ")
            if response.lower() == "yes":
                drop_db_tables()
                print("✓ Tables dropped")
            else:
                print("Operation cancelled")
        except RuntimeError as e:
            print(f"✗ Failed to drop tables: {e}")
            sys.exit(1)
    
    elif command == "reset":
        try:
            response = input("WARNING: This will delete all data! Continue? (yes/no): ")
            if response.lower() == "yes":
                reset_db()
                print("✓ Database reset complete")
            else:
                print("Operation cancelled")
        except RuntimeError as e:
            print(f"✗ Failed to reset database: {e}")
            sys.exit(1)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
