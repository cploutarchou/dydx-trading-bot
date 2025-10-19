#!/usr/bin/env python3
"""
Test script to verify SQLite and PostgreSQL database configuration.
Tests connection, table creation, and basic CRUD operations.

Usage:
    python3 test_dual_database.py                # Test current config
    DB_TYPE=sqlite python3 test_dual_database.py # Force SQLite
    DB_TYPE=postgresql python3 test_dual_database.py # Force PostgreSQL
"""

import logging
import os
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_connection():
    """Test database connection."""
    try:
        from sqlalchemy import inspect, text

        from backend.database import engine, get_database_url, init_db

        url = get_database_url()
        db_type = "SQLite" if "sqlite" in url else "PostgreSQL"

        logger.info(f"\n{'=' * 70}")
        logger.info(f"Testing {db_type} Database Configuration")
        logger.info(f"{'=' * 70}\n")

        # Log URL (sanitize password)
        safe_url = url.replace("@", " at ")
        if ":" in safe_url and "@" in url:
            # Extract password part and hide it
            parts = url.split("@")
            user_pass = parts[0].split("://")[-1]
            if ":" in user_pass:
                user, _ = user_pass.split(":", 1)
                safe_url = url.split("://")[0] + "://" + user + ":***@" + parts[-1]

        logger.info(f"📊 Database Type: {db_type}")
        logger.info(f"📊 Database URL: {safe_url}")

        # Initialize database
        logger.info("\n🔧 Initializing database schema...")
        init_db()
        logger.info("✅ Schema initialized successfully")

        # Test connection
        logger.info("\n🔌 Testing connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("✅ Connection successful")

        # List tables
        logger.info("\n📋 Database Tables:")
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"   Total: {len(tables)} tables")
        for table in sorted(tables):
            cols = len(inspector.get_columns(table))
            logger.info(f"   ✓ {table:<30} ({cols} columns)")

        return True

    except Exception as e:
        logger.error(f"\n❌ Database test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_crud_operations():
    """Test basic CRUD operations."""
    try:
        from backend.auth import hash_password
        from backend.database import SessionLocal, User

        logger.info("\n\n" + "=" * 70)
        logger.info("Testing CRUD Operations")
        logger.info("=" * 70 + "\n")

        db = SessionLocal()

        try:
            # Test CREATE
            logger.info("📝 Testing CREATE...")
            test_user = User(
                username=f"test_user_{datetime.utcnow().timestamp()}",
                email="test@example.com",
                hashed_password=hash_password("test123"),
                is_active=True,
                is_admin=False,
            )
            db.add(test_user)
            db.commit()
            logger.info(f"✅ Created user: {test_user.username}")
            user_id = test_user.id

            # Test READ
            logger.info("\n📖 Testing READ...")
            user = db.query(User).filter(User.id == user_id).first()
            if user is not None:
                logger.info(f"✅ Retrieved user: {user.username} (ID: {user.id})")
            else:
                logger.error("❌ Could not retrieve user")
                return False

            # Test UPDATE
            logger.info("\n✏️ Testing UPDATE...")
            if user is not None:
                user.email = "updated@example.com"
                db.commit()
            updated_user = db.query(User).filter(User.id == user_id).first()
            if updated_user is not None and updated_user.email == "updated@example.com":
                logger.info(f"✅ Updated user email: {updated_user.email}")
            else:
                logger.error("❌ Update failed")
                return False

            # Test DELETE
            logger.info("\n🗑️ Testing DELETE...")
            if user is not None:
                db.delete(user)
                db.commit()
            deleted_user = db.query(User).filter(User.id == user_id).first()
            if deleted_user is None:
                logger.info("✅ Successfully deleted user")
            else:
                logger.error("❌ Delete failed")
                return False

            logger.info("\n✅ All CRUD operations successful")
            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"\n❌ CRUD test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def show_configuration():
    """Show current database configuration."""
    try:
        from backend.config_loader import get_config_loader

        logger.info("\n\n" + "=" * 70)
        logger.info("Current Configuration")
        logger.info("=" * 70 + "\n")

        config_loader = get_config_loader()
        db_config = config_loader.get_database_config()

        logger.info("📋 Database Configuration from config.yaml:")
        logger.info(f"   Type:          {db_config.get('type', 'N/A')}")
        logger.info(f"   Name:          {db_config.get('name', 'N/A')}")
        logger.info(f"   Host:          {db_config.get('host', 'N/A')}")
        logger.info(f"   Port:          {db_config.get('port', 'N/A')}")
        logger.info(f"   Pool Size:     {db_config.get('pool_size', 'N/A')}")
        logger.info(f"   Max Overflow:  {db_config.get('max_overflow', 'N/A')}")
        logger.info(f"   Timeout:       {db_config.get('timeout', 'N/A')} seconds")

        logger.info("\n🌍 Environment Variables:")
        for key in [
            "DB_TYPE",
            "DB_NAME",
            "DB_USER",
            "DB_HOST",
            "DB_PORT",
            "DB_POOL_SIZE",
        ]:
            val = os.getenv(key, "Not set")
            logger.info(f"   {key:<20} {val}")

    except Exception as e:
        logger.warning(f"Could not load configuration: {e}")


def main():
    """Run all tests."""
    try:
        logger.info("\n\n" + "🚀 " * 35)
        logger.info("dYdX Trading Bot - Dual Database Test Suite")
        logger.info("🚀 " * 35 + "\n")

        # Show configuration
        show_configuration()

        # Test connection
        if not test_connection():
            sys.exit(1)

        # Test CRUD
        if not test_crud_operations():
            sys.exit(1)

        logger.info("\n\n" + "=" * 70)
        logger.info("✅ All tests passed successfully!")
        logger.info("=" * 70 + "\n")
        logger.info("📚 Documentation: DATABASE_DUAL_CONFIG.md\n")

        return 0

    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"\n\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
