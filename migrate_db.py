#!/usr/bin/env python3
"""
Database migration script to add new profile columns to existing users table.
Run this to migrate existing databases to the new schema.
"""

import os
import sqlite3
import sys

# Get database path
db_path = os.path.join(os.path.dirname(__file__), "app", "dydx_backtest.db")

print(f"📦 Migrating database: {db_path}")

if not os.path.exists(db_path):
    print("ℹ️  Database does not exist yet - fresh database will be created on startup")
    sys.exit(0)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if full_name column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = {col[1] for col in cursor.fetchall()}

    if "full_name" not in columns:
        print("⚙️  Adding full_name column...")
        cursor.execute(
            "ALTER TABLE users ADD COLUMN full_name VARCHAR(100) DEFAULT NULL"
        )
        print("✅ Added full_name column")
    else:
        print("✓ full_name column already exists")

    if "avatar" not in columns:
        print("⚙️  Adding avatar column...")
        cursor.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT NULL")
        print("✅ Added avatar column")
    else:
        print("✓ avatar column already exists")

    conn.commit()
    print("\n✅ Database migration completed successfully!")

except sqlite3.Error as e:
    print(f"❌ Database error: {e}")
    sys.exit(1)
finally:
    if conn:
        conn.close()
