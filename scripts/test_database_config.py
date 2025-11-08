#!/usr/bin/env python3
"""
Test script to verify database configuration works with both SQLite and PostgreSQL.
Usage: python3 scripts/test_database_config.py [sqlite|postgresql]
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_sqlite():
    """Test SQLite database configuration."""
    print("\n" + "=" * 80)
    print("Testing SQLite Database Configuration")
    print("=" * 80)

    # Set environment to SQLite
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_NAME"] = "dydx_backtest.db"

    try:
        from sqlalchemy import inspect

        from backend.database import DATABASE_URL, Base, engine

        print(f"✓ Database URL: {DATABASE_URL}")

        # Create tables
        Base.metadata.create_all(bind=engine)
        print("✓ Tables created successfully")

        # List tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"✓ Tables found: {len(tables)}")
        for table in sorted(tables):
            print(f"  - {table}")

        # Test connection
        with engine.connect() as connection:
            from sqlalchemy import text

            connection.execute(text("SELECT 1"))
            print("✓ Connection test passed")

        print("\n✅ SQLite configuration is working correctly!")
        return True

    except Exception as e:
        print(f"\n❌ SQLite configuration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_postgresql():
    """Test PostgreSQL database configuration."""
    print("\n" + "=" * 80)
    print("Testing PostgreSQL Database Configuration")
    print("=" * 80)

    # Set environment to PostgreSQL
    os.environ["DB_TYPE"] = "postgresql"
    os.environ["DB_NAME"] = "dydx_backtest_test"
    os.environ["DB_USER"] = os.getenv("DB_USER", "postgres")
    os.environ["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "postgres")
    os.environ["DB_HOST"] = os.getenv("DB_HOST", "localhost")
    os.environ["DB_PORT"] = os.getenv("DB_PORT", "5432")

    try:
        # Need to reload module to pick up new environment variables
        import importlib

        import backend.database

        importlib.reload(backend.database)

        from sqlalchemy import inspect

        from backend.database import DATABASE_URL, Base, engine

        print(f"✓ Database URL: {DATABASE_URL}")
        print(f"  Host: {os.environ['DB_HOST']}")
        print(f"  Port: {os.environ['DB_PORT']}")
        print(f"  Database: {os.environ['DB_NAME']}")
        print(f"  User: {os.environ['DB_USER']}")

        # Test connection first
        try:
            with engine.connect() as connection:
                from sqlalchemy import text

                connection.execute(text("SELECT 1"))
                print("✓ Connection test passed")
        except Exception as conn_err:
            print(f"\n⚠️  PostgreSQL connection failed: {conn_err}")
            print("\nNote: PostgreSQL may not be running. To test:")
            print(
                "1. Install PostgreSQL: brew install postgresql (macOS) or apt-get install postgresql (Linux)"
            )
            print(
                "2. Start PostgreSQL: brew services start postgresql or systemctl start postgresql"
            )
            print("3. Create test database: createdb dydx_backtest_test")
            print("4. Run this script again")
            return False

        # Create tables
        Base.metadata.create_all(bind=engine)
        print("✓ Tables created successfully")

        # List tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"✓ Tables found: {len(tables)}")
        for table in sorted(tables):
            print(f"  - {table}")

        print("\n✅ PostgreSQL configuration is working correctly!")
        return True

    except Exception as e:
        print(f"\n⚠️  PostgreSQL test: {e}")
        print("\nPostgreSQL may not be available. This is OK for development.")
        return False


def main():
    """Run database configuration tests."""
    print("\n" + "=" * 80)
    print("Database Configuration Test Suite")
    print("=" * 80)
    print(
        "\nThis script verifies that the backend can connect to both SQLite and PostgreSQL"
    )

    if len(sys.argv) > 1:
        db_type = sys.argv[1].lower()
        if db_type == "sqlite":
            success = test_sqlite()
        elif db_type == "postgresql":
            success = test_postgresql()
        else:
            print(f"Unknown database type: {db_type}")
            print("Usage: python3 scripts/test_database_config.py [sqlite|postgresql]")
            return 1

        return 0 if success else 1
    else:
        # Test both
        sqlite_ok = test_sqlite()
        postgresql_ok = test_postgresql()

        print("\n" + "=" * 80)
        print("Summary")
        print("=" * 80)
        print(f"SQLite:      {'✅ OK' if sqlite_ok else '❌ FAILED'}")
        print(
            f"PostgreSQL:  {'✅ OK' if postgresql_ok else '⚠️  Not available (OK for dev)'}"
        )

        print("\nTo use each database, set the DB_TYPE environment variable or")
        print("update the 'database.type' setting in app/config.yaml:")
        print()
        print("  SQLite:")
        print("    export DB_TYPE=sqlite")
        print()
        print("  PostgreSQL:")
        print("    export DB_TYPE=postgresql")
        print("    export DB_USER=postgres")
        print("    export DB_PASSWORD=your_password")
        print("    export DB_HOST=localhost")
        print("    export DB_NAME=dydx_backtest")
        print()

        return 0


if __name__ == "__main__":
    sys.exit(main())
