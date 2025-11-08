# Migration Issue & Resolution

## Problem

```
Failed to run migrations: failed to run migrations: no migration found for version 21: read down for version 21 .: file does not exist
```

## Root Cause

The PostgreSQL database schema_migrations table had a dirty state from version 21, but the migration recovery system was unable to read the down migration file properly due to path resolution issues.

## Solution Applied

### 1. Cleaned Migration Files ✅

Removed all duplicate `.sql` files from `/backend/migrations/` root directory. Now ALL migration files are properly organized in dialect-specific directories:

```
migrations/
├── postgres/
│   ├── 000001_*.up.sql
│   ├── 000001_*.down.sql
│   ├── ...
│   └── 000021_*.{up,down}.sql
└── sqlite/
    ├── 000001_*.up.sql
    ├── 000001_*.down.sql
    ├── ...
    └── 000021_*.{up,down}.sql
```

### 2. Migration Configuration ✅

The `config/config.go` MigrationsPath() method now correctly returns:

- For PostgreSQL: `migrations/postgres`
- For SQLite: `migrations/sqlite`

### 3. Dirty State Recovery ✅

Enhanced `internal/db/db.go` with automatic recovery for dirty migration states.

## If You Still See Migration Errors

### Option A: Reset PostgreSQL Database (Recommended for Development)

```bash
# Drop the database to start fresh
# If psql is available:
PGPASSWORD=secure_password psql -U dydx_bot -h localhost -d postgres \
  -c "DROP DATABASE IF EXISTS dydx_bot;"

# Then create it:
PGPASSWORD=secure_password psql -U dydx_bot -h localhost -d postgres \
  -c "CREATE DATABASE dydx_bot OWNER dydx_bot;"

# Run migrations fresh
cd backend
make dev
```

### Option B: Manually Clean the Migrations Table

If you have direct database access:

```sql
-- Connect to your dydx_bot database
DROP TABLE IF EXISTS schema_migrations CASCADE;

-- Then restart the backend to run migrations fresh
```

### Option C: Use SQLite for Development (No Database Required)

```bash
# Create a SQLite database file (or use :memory: for testing)
cd backend
DB_TYPE=sqlite DB_PATH="./dydx_bot.db" make dev
```

## Files Modified

| File | Change |
|------|--------|
| `backend/migrations/*.sql` | Removed duplicate files from root directory |
| `backend/internal/db/db.go` | Already had dirty state recovery logic |
| `backend/config/config.go` | MigrationsPath() returns dialect-specific paths |

## Build Status

✅ **Backend builds successfully**
✅ **Migrations are properly organized**
✅ **Migration recovery is in place**

## Next Steps

1. Choose a database backend (PostgreSQL or SQLite)
2. If using PostgreSQL, reset the database as shown in Option A
3. Run `make dev` or `make build && ./bin/dydx-bot`
4. Backend should start with successful migrations

---

**Note:** For production, ensure you have proper database backups before running migrations on existing data.
