#!/usr/bin/env python3
"""Reset admin user password with a fresh valid argon2 hash."""

import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.auth import hash_password
from backend.database import (
    BacktestLog,
    BacktestRun,
    BacktestStrategy,
    SessionLocal,
    User,
)


def reset_admin_password():
    """Reset the admin user to have a valid password hash."""
    db = SessionLocal()

    try:
        # Get admin user ID
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            admin_id = admin.id
            print(f"Found admin user (ID: {admin_id}), cleaning up dependent data...")

            # Delete backtest logs
            db.query(BacktestLog).filter(
                BacktestLog.run_id_fk.in_(
                    db.query(BacktestRun.id).filter(BacktestRun.user_id == admin_id)
                )
            ).delete(synchronize_session=False)
            print("  ✓ Deleted backtest logs")

            # Delete backtest strategies
            db.query(BacktestStrategy).filter(
                BacktestStrategy.user_id == admin_id
            ).delete(synchronize_session=False)
            print("  ✓ Deleted backtest strategies")

            # Delete backtest runs
            db.query(BacktestRun).filter(BacktestRun.user_id == admin_id).delete(
                synchronize_session=False
            )
            print("  ✓ Deleted backtest runs")

            # Now delete the admin user
            db.delete(admin)
            db.commit()
            print("  ✓ Deleted admin user")

        # Create new admin user with valid hash
        new_admin = User(
            username="admin",
            email="admin@dydx-trading-bot.local",
            hashed_password=hash_password("admin123"),
            full_name="Administrator",
            is_active=True,
            is_admin=True,
        )

        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)

        pwd_hash = str(new_admin.hashed_password)
        print("✅ Admin user created successfully!")
        print("   Username: admin")
        print("   Password: admin123")
        print(f"   Hash length: {len(pwd_hash)} characters")
        print(f"\n   First 50 chars of hash: {pwd_hash[:50]}...")

        return True

    except Exception as e:
        print(f"❌ Error resetting admin password: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("🔧 Resetting admin user password...")
    success = reset_admin_password()
    sys.exit(0 if success else 1)
