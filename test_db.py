#!/usr/bin/env python3
"""Test the database and profile endpoints"""

import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

# Initialize database
from backend.auth import hash_password
from backend.database import SessionLocal, User, init_db

print("🔧 Initializing database...")
init_db()

print("✅ Database initialized!")

# Create test user
db = SessionLocal()
try:
    # Check admin user
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        print("✅ Admin user exists:")
        print(f"   - Username: {admin.username}")
        print(f"   - Email: {admin.email}")
        print(f"   - Full Name: {admin.full_name}")
        avatar_status = "Yes" if admin.avatar is not None else "No"
        print(f"   - Avatar: {avatar_status}")

    # Create test user with profile
    test_user = db.query(User).filter(User.username == "testuser").first()
    if not test_user:
        print("\n📝 Creating test user with profile...")
        hashed = hash_password("test123")
        test_user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=hashed,
            full_name="Test User",
            avatar=None,
            is_active=True,
            is_admin=False,
        )
        db.add(test_user)
        db.commit()
        print("✅ Test user created:")
        print(f"   - Username: {test_user.username}")
        print(f"   - Email: {test_user.email}")
        print(f"   - Full Name: {test_user.full_name}")

    # List all users
    users = db.query(User).all()
    print(f"\n📋 Total users in database: {len(users)}")
    for user in users:
        print(f"   - {user.username} ({user.email})")

    print("\n✅ Database test successful!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
finally:
    db.close()
