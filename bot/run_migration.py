#!/usr/bin/env python3
"""
Run Database Migration for Backtesting Tables
This script sets up the database tables needed for the backtesting API
"""

import os
import sys

# Add the bot directory to a Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logging_setup import setup_logging
from migrate_backtest_tables import run_migration


def main():
    """Run the database migration"""

    # Setup logging
    setup_logging()

    print("🗄️  dYdX Trading Bot - Database Migration")
    print("=" * 50)
    print("Setting up backtesting database tables...")

    try:
        # Run the migration
        success = run_migration()

        if success:
            print("✅ Database migration completed successfully!")
            print("   - BacktestRun table created/updated")
            print("   - BacktestTrade table created/updated")
            print("   - All relationships and indexes configured")
            print("\n🚀 Backtesting API is now ready to use!")
            print("   Start the API server with: python start_api.py")
            return 0
        else:
            print("❌ Database migration failed!")
            print("   Check the logs for error details")
            return 1

    except Exception as e:
        print(f"❌ Migration error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
