#!/bin/bash

# Reset migrations for PostgreSQL
# This script drops the migrations table to force a clean migration run

set -e

DB_USER="${DB_USER:-${POSTGRES_USER:-dydx_bot}}"
DB_HOST="${DB_HOST:-${POSTGRES_HOST:-localhost}}"
DB_NAME="${DB_NAME:-${POSTGRES_DB:-dydx_bot}}"
DB_PORT="${DB_PORT:-${POSTGRES_PORT:-5432}}"
DB_PASSWORD="${DB_PASSWORD:-${POSTGRES_PASSWORD:-}}"

echo "🔄 Resetting PostgreSQL migrations..."

# Connect using environment variables if available
if command -v psql &> /dev/null; then
    PGPASSWORD="${DB_PASSWORD}" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "DROP TABLE IF EXISTS schema_migrations;" \
        >/dev/null 2>&1 || echo "⚠️  Could not connect directly, skipping drop"
else
    echo "⚠️  psql client not installed. Skipping direct database reset."
    echo "   Please manually run: DROP TABLE IF EXISTS schema_migrations;"
fi

echo "✅ Migration reset complete. You can now run migrations fresh."
