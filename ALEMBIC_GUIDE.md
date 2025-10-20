# Alembic Database Migration Guide

## Overview

This project uses **Alembic** for database schema migrations with SQLite (development) and PostgreSQL (production). All migration commands are integrated into the Makefile for easy access via `.venv`.

## Quick Start

```bash
# Activate virtual environment (if not already active)
source .venv/bin/activate

# Apply all pending migrations
make db-upgrade

# View current migration status
make db-current

# View migration history
make db-history
```

## Make Commands Reference

### 🔧 Core Migration Commands

#### `make db-upgrade` - Apply Migrations

Apply all pending migrations to the database (upgrade to latest version).

```bash
make db-upgrade
```

**Use when:**

- Setting up a new environment
- Deploying database schema changes
- Syncing local database with latest migrations

**Output:**

```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> abc123def456, Add backteststrategy table
✅ Database upgraded to latest migration
```

---

#### `make db-revision MESSAGE='your description'` - Create Migration

Generate a new Alembic migration file from model changes.

```bash
# Create migration with description
make db-revision MESSAGE='add user profile columns'
```

**Use when:**

- Adding new database tables or columns
- Modifying existing schema
- Removing obsolete fields

**Output:**

```
  Generating /home/chris/workspace/dydx-trading-bot/alembic/versions/abc123def456_add_user_profile_columns.py
✅ Migration created
📌 Review the new file in alembic/versions/ before upgrading
```

**Next steps:**

1. Review the generated file in `alembic/versions/`
2. Edit if needed to fix auto-generated migration
3. Run `make db-upgrade` to apply it

---

#### `make db-downgrade STEPS=1` - Rollback Migrations

Rollback one or more migrations to previous database state.

```bash
# Rollback one migration
make db-downgrade STEPS=1

# Rollback two migrations
make db-downgrade STEPS=2
```

**Use when:**

- Reverting breaking schema changes
- Testing migration reversibility
- Recovering from migration errors

**Output:**

```
INFO  [alembic.runtime.migration] Running downgrade abc123def456 -> xyz789, Remove unused columns
✅ Rolled back 1 migration(s)
```

⚠️ **Warning:** Downgrade may lose data if migration involves deletions. Test in dev first!

---

### 📊 Status & History Commands

#### `make db-current` - Show Current Version

Display the current database migration version.

```bash
make db-current
```

**Output:**

```
abc123def456 (head)
```

This shows you're on migration `abc123def456` which is the latest (head).

---

#### `make db-history` - View Migration History

Show all applied and pending migrations with details.

```bash
make db-history
```

**Output:**

```
<base> -> abc123def456 (head), Add backteststrategy table
    -> def456abc123, Create initial schema
    -> xyz789abc123, Add dydx keys secure storage
```

**Read this as:** "From base state → abc123 → def456 → xyz789"

---

#### `make db-branches` - Check for Conflicting Branches

Show migration branches (occurs when multiple developers create migrations simultaneously).

```bash
make db-branches
```

**Normal output (no branches):**

```
Branch points:
  at alembic/versions/abc123def456_add_backteststrategy_table.py
```

**If branches exist:** You'll need to merge them with `make db-merge`.

---

### 🔗 Advanced Commands

#### `make db-merge MESSAGE='description'` - Merge Migration Branches

Resolve conflicting migrations when multiple developers work on schema simultaneously.

```bash
make db-merge MESSAGE='merge concurrent migrations'
```

**When needed:**

- Two developers create migrations on different branches
- Alembic detects multiple "heads" (branch points)
- You need to reconcile the migrations

**Manual fix (if merge fails):**

```bash
# View all migration versions
ls alembic/versions/

# Edit the merge migration file to include both migration operations
# Then run upgrade
make db-upgrade
```

---

#### `make db-migrate-legacy` - Run Legacy SQLite Migration

Execute the old `migrate_db.py` script for pre-Alembic databases.

```bash
make db-migrate-legacy
```

**Use when:**

- Migrating from old SQLite database without Alembic
- Adding columns like `full_name`, `avatar` to existing users table
- One-time setup for legacy databases

---

#### `make db-init` - Initialize Alembic (One-time Setup)

Initialize Alembic in a fresh project (already done in this repo).

```bash
make db-init
```

**Only run if:**

- Starting Alembic from scratch in a new project
- `alembic/` directory doesn't exist

⚠️ This is a **one-time operation** and already completed in this repo.

---

## Workflow Examples

### 📋 Scenario 1: Add a New Database Column

You added a new field to a model:

```python
# In backend/models/users.py
class User:
    id: int
    username: str
    email: str
    full_name: str  # ← New field
    created_at: datetime
```

**Steps:**

```bash
# 1. Create migration from model changes
make db-revision MESSAGE='add full_name column to users'

# 2. Review the generated migration
cat alembic/versions/abc123def456_add_full_name_column_to_users.py

# 3. Apply migration to your local database
make db-upgrade

# 4. Verify new column exists
make db-current
```

---

### 🔄 Scenario 2: Revert a Breaking Migration

You deployed a migration that broke production:

```bash
# 1. Check current state
make db-history

# 2. Rollback one migration
make db-downgrade STEPS=1

# 3. Verify rollback
make db-current

# 4. Fix the migration file and redeploy
make db-upgrade
```

---

### 🌿 Scenario 3: Merge Migration Branches (Multiple Developers)

Two developers created migrations simultaneously:

```bash
# 1. Check status
make db-branches
# Output: Branch points detected

# 2. Merge branches
make db-merge MESSAGE='merge user_profiles and backtest_results migrations'

# 3. Review merged migration
ls -la alembic/versions/ | tail -3

# 4. Apply merged migration
make db-upgrade
```

---

### 🚀 Scenario 4: Deploy to Production

Your migrations are ready for production (PostgreSQL):

```bash
# On production server:

# 1. Activate venv
source .venv/bin/activate

# 2. Verify migrations pending
make db-history

# 3. Apply migrations
make db-upgrade

# 4. Confirm all applied
make db-current
```

---

## Directory Structure

```
project_root/
├── alembic/                           # Alembic configuration
│   ├── env.py                        # Environment config (database URL setup)
│   ├── script.py.mako                # Migration template
│   ├── versions/                     # Migration scripts
│   │   ├── abc123def456_initial.py
│   │   ├── def456abc123_add_users.py
│   │   └── xyz789abc123_add_audit.py
│   └── README
├── alembic.ini                        # Alembic main config
├── migrate_db.py                      # Legacy SQLite migration script
├── app/
│   ├── dydx_backtest.db              # SQLite database (dev)
│   └── ...
└── Makefile                           # Database commands here
```

---

## Configuration

### Database Connection

Alembic reads the database URL from `backend/database.py`:

```python
# backend/database.py
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./app/dydx_backtest.db"  # Default: SQLite
)
```

**For PostgreSQL (production):**

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/dydx_bot"
make db-upgrade
```

**For SQLite (development):**

```bash
export DATABASE_URL="sqlite:///./app/dydx_backtest.db"
make db-upgrade
```

---

## Troubleshooting

### ❌ Error: "Target database is not up to date"

**Problem:** You have pending migrations not yet applied.

**Solution:**

```bash
make db-upgrade
```

---

### ❌ Error: "Multiple heads detected"

**Problem:** Conflicting migrations from multiple developers.

**Solution:**

```bash
make db-merge MESSAGE='reconcile migrations'
make db-upgrade
```

---

### ❌ Error: "Invalid migration file"

**Problem:** Syntax error in a migration Python file.

**Solution:**

1. Edit the migration file in `alembic/versions/`
2. Fix the Python syntax
3. Run again:

```bash
make db-upgrade
```

---

### ❌ Error: "Database is locked" (SQLite)

**Problem:** Another process is using the SQLite database.

**Solution:**

```bash
# Kill any other processes using the database
ps aux | grep python

# Remove SQLite lock files
rm -f app/dydx_backtest.db-journal
rm -f app/dydx_backtest.db-wal

# Retry
make db-upgrade
```

---

## Best Practices

### ✅ DO

- ✅ Create migrations for **every schema change**
- ✅ Review auto-generated migrations **before applying**
- ✅ Test migrations in **dev environment first**
- ✅ Use clear, descriptive migration messages
- ✅ Commit migration files to **version control**
- ✅ Include migration files in **code reviews**

### ❌ DON'T

- ❌ Manually edit database tables (create migrations instead)
- ❌ Skip migration files (always check them in)
- ❌ Apply migrations directly without review
- ❌ Use `downgrade` in production without testing
- ❌ Create migration files manually (use `make db-revision`)

---

## Environment Variables

Set these to configure Alembic behavior:

```bash
# Database connection URL
export DATABASE_URL="sqlite:///./app/dydx_backtest.db"

# Or PostgreSQL
export DATABASE_URL="postgresql://user:password@host:5432/dbname"
```

These are read by `alembic/env.py` and `backend/database.py`.

---

## Related Documentation

- **Alembic Official**: <https://alembic.sqlalchemy.org/>
- **Database Setup**: See `docs/DATABASE_API_INTEGRATION.md`
- **Backend Config**: See `backend/database.py`
- **Models**: See `backend/models/`

---

## Quick Command Reference

```bash
# Check status
make db-current          # Current migration version
make db-history          # All migrations
make db-branches         # Check for conflicts

# Create & apply
make db-revision MESSAGE='description'  # Create new migration
make db-upgrade                          # Apply migrations
make db-downgrade STEPS=1                # Rollback

# Advanced
make db-merge MESSAGE='merge'    # Resolve conflicts
make db-migrate-legacy           # Old SQLite migration

# Help
make help | grep db-             # Show all db commands
```
