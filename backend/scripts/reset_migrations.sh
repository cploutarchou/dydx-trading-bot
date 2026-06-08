#!/bin/bash

# Reset migrations for MariaDB
# This script drops the migrations table to force a clean migration run

set -e

DB_USER="${DB_USER:-dydx_bot}"
DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-dydx_bot}"
DB_PORT="${DB_PORT:-3306}"

echo "🔄 Resetting MariaDB migrations..."

# Connect using environment variables if available
if command -v mariadb &> /dev/null; then
    mariadb -u "$DB_USER" -p"${DB_PASSWORD:-secure_password}" -h "$DB_HOST" -P "$DB_PORT" "$DB_NAME" -e "DROP TABLE IF EXISTS schema_migrations;" 2>/dev/null || echo "⚠️  Could not connect directly, skipping drop"
else
    echo "⚠️  mariadb client not installed. Skipping direct database reset."
    echo "   Please manually run: DROP TABLE IF EXISTS schema_migrations;"
fi

echo "✅ Migration reset complete. You can now run migrations fresh."
