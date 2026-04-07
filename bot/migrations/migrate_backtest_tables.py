"""
Database migration script for backtest tables
Run this to create the necessary tables for backtest functionality
"""

from loguru import logger
from sqlalchemy import create_engine

from database import DatabaseConfig, DatabaseManager
from internal.domain.models_backtest import BacktestRun


def create_backtest_tables():
    """Create backtest tables in the database"""

    try:
        # Get database configuration
        config = DatabaseConfig()
        db_url = config.get_connection_string()
        engine_kwargs = config.get_engine_kwargs()

        # Create engine
        engine = create_engine(db_url, **engine_kwargs)

        # Create all backtest tables - Base is imported through models_backtest
        BacktestRun.metadata.create_all(bind=engine)

        logger.info("Backtest tables created successfully")
        print("✅ Backtest database tables created successfully!")

    except Exception as e:
        logger.error(f"Failed to create backtest tables: {e}")
        print(f"❌ Failed to create backtest tables: {e}")
        raise


def run_migration():
    """Run the database migration for backtest tables"""
    try:
        db_manager = DatabaseManager()
        engine = db_manager.get_engine()

        # Create tables - Base is imported through models_backtest
        BacktestRun.metadata.create_all(engine)
        logger.info("Backtest database tables created successfully")

        print("✅ Backtest tables created/updated successfully!")
        return True

    except Exception as e:
        logger.error(f"Failed to create backtest tables: {e}")
        print(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    # Run the migration when script is executed directly
    success = run_migration()
    if not success:
        exit(1)
