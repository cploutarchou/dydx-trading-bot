#!/bin/bash
# Fix dirty migration state for SQLite

DB_FILE="trading_bot.db"

if [ ! -f "$DB_FILE" ]; then
    echo "❌ Database file not found: $DB_FILE"
    exit 1
fi

echo "🔧 Fixing dirty migration state..."

# Check current migration version
echo "Current schema migrations:"
sqlite3 "$DB_FILE" "SELECT version, dirty FROM schema_migrations ORDER BY version DESC LIMIT 1;" 2>/dev/null || echo "No migration table found"

# Set migration 18 as clean (dirty=false)
echo "Marking migration version 18 as clean..."
sqlite3 "$DB_FILE" "UPDATE schema_migrations SET dirty = 0 WHERE version = 18;" 2>/dev/null

# Verify the fix
echo "Updated schema migrations:"
sqlite3 "$DB_FILE" "SELECT version, dirty FROM schema_migrations ORDER BY version DESC LIMIT 1;"

echo "✅ Done! Try running the server again."

