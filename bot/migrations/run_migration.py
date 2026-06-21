#!/usr/bin/env python3
"""
Run Database Migration for Backtesting Tables
This script sets up the database tables needed for the backtesting API
"""

import sys
from pathlib import Path


def _bootstrap_runtime_dependencies():
    """Resolve runtime dependencies after ensuring repo root is importable."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # ⚠️ CRITICAL: Load environment variables before runtime/config imports.
    from src.shared.env_loader import load_repo_env

    load_repo_env(__file__)

    from src.shared.logging_setup import setup_logging

    try:
        from migrations.migrate_backtest_tables import run_migration
    except ModuleNotFoundError:
        # Fallback for direct script invocation from this folder.
        from migrate_backtest_tables import run_migration

    return setup_logging, run_migration


def main():
    """Run the database migration"""
    setup_logging, run_migration = _bootstrap_runtime_dependencies()

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
            print("   Start the API server with: python src/api/start_api.py")
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
