#!/usr/bin/env python3
"""
Database initialization and verification script.
Ensures all tables are created and properly initialized.

Usage:
    python scripts/init_database.py              # Create all tables
    python scripts/init_database.py --verify     # Verify schema
    python scripts/init_database.py --reset      # Reset and reinitialize
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

# Load environment variables FIRST
from dotenv import load_dotenv

load_dotenv()

import logging

from sqlalchemy import inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from backend.database import (
    Base,
    engine,
    get_database_url,
    init_db,
)


def get_all_model_tables():
    """Get all table names from SQLAlchemy models."""
    return {table.name for table in Base.metadata.tables.values()}


def get_existing_tables():
    """Get all existing table names in database."""
    inspector = inspect(engine)
    return set(inspector.get_table_names())


def verify_schema():
    """Verify that all model tables exist in database."""
    logger.info("=" * 70)
    logger.info("VERIFYING DATABASE SCHEMA")
    logger.info("=" * 70)

    expected_tables = get_all_model_tables()
    existing_tables = get_existing_tables()

    logger.info(f"\nExpected tables ({len(expected_tables)}):")
    for table in sorted(expected_tables):
        status = "✅" if table in existing_tables else "❌"
        logger.info(f"  {status} {table}")

    missing_tables = expected_tables - existing_tables
    extra_tables = existing_tables - expected_tables

    logger.info(f"\n{'=' * 70}")

    if missing_tables:
        logger.error(f"❌ MISSING TABLES ({len(missing_tables)}):")
        for table in sorted(missing_tables):
            logger.error(f"   - {table}")
    else:
        logger.info(f"✅ All {len(expected_tables)} expected tables exist")

    if extra_tables:
        logger.warning(f"⚠️  EXTRA TABLES ({len(extra_tables)}):")
        for table in sorted(extra_tables):
            logger.warning(f"   - {table}")

    logger.info(f"\n{'=' * 70}")

    # Detailed column verification for key tables
    key_tables = [
        "backtest_runs",
        "backtest_strategies",
        "users",
        "backtest_results",
    ]

    inspector = inspect(engine)

    for table_name in key_tables:
        if table_name in existing_tables:
            logger.info(f"\nTable: {table_name}")
            columns = inspector.get_columns(table_name)
            logger.info(f"  Columns ({len(columns)}):")
            for col in columns:
                logger.info(f"    - {col['name']}: {col['type']}")

    logger.info(f"\n{'=' * 70}\n")
    return len(missing_tables) == 0


def initialize_database():
    """Initialize database and create all tables."""
    logger.info("=" * 70)
    logger.info("INITIALIZING DATABASE")
    logger.info("=" * 70)

    db_url = get_database_url()
    logger.info(f"\nDatabase URL: {db_url[:60]}...")

    try:
        # Call init_db which creates tables and seeds admin user
        init_db()
        logger.info("\n✅ Database initialization completed successfully")
        return True
    except Exception as e:
        logger.error(f"\n❌ Database initialization failed: {e}", exc_info=True)
        return False


def reset_database():
    """Reset database - drop all tables and recreate."""
    logger.info("=" * 70)
    logger.info("RESETTING DATABASE")
    logger.info("=" * 70)
    logger.warning("⚠️  This will drop ALL tables and data!")

    response = input("\nAre you sure? Type 'yes' to confirm: ")
    if response.lower() != "yes":
        logger.info("Reset cancelled")
        return False

    try:
        logger.info("\nDropping all tables...")
        Base.metadata.drop_all(bind=engine)
        logger.info("✅ Tables dropped")

        logger.info("\nRecreating tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tables recreated")

        # Seed admin user
        from backend.database import _seed_admin_user

        _seed_admin_user()

        logger.info("\n✅ Database reset completed successfully")
        return True
    except Exception as e:
        logger.error(f"\n❌ Database reset failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Database initialization and verification utility"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify schema without making changes"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (drop and recreate all tables)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize database (create missing tables only) - default action",
    )

    args = parser.parse_args()

    # Default action is initialization
    if not (args.verify or args.reset or args.init):
        args.init = True

    try:
        if args.init:
            success = initialize_database()
            success = verify_schema() and success
            sys.exit(0 if success else 1)

        elif args.verify:
            success = verify_schema()
            sys.exit(0 if success else 1)

        elif args.reset:
            success = reset_database()
            if success:
                success = verify_schema()
            sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)
