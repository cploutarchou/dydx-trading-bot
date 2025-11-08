#!/usr/bin/env python3
"""
Create a test user for development/testing purposes.
Usage: python scripts/create_test_user.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import Base, SessionLocal, engine
from backend.services import UserService


def create_test_user():
    """Create default test user."""
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Get database session
    db = SessionLocal()

    try:
        # Create test user
        UserService.create_user(
            db, username="admin", email="admin@dydx.local", password="admin123"
        )

        print("✅ Test user created successfully!")
        print("   Username: admin")
        print("   Password: admin123")
        print("   Email: admin@dydx.local")
        print()
        print("You can now log in with these credentials at http://localhost:5173")

    except ValueError as e:
        print(f"❌ Error: {e}")
        print("   User may already exist. Try logging in with existing credentials.")
    except Exception as e:
        print(f"❌ Database error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_test_user()
