# Database Initialization & Management Guide

This guide explains how to initialize, verify, and manage the dYdX Trading Bot database.

## Quick Start

### Option 1: Automatic Initialization (Recommended)

The database is **automatically initialized when you start the backend server**:

```bash
# Start backend - automatically initializes database on startup
make backend-run

# Or directly with uvicorn
python -m uvicorn backend.main:app --reload --port 8888
```

**What happens automatically:**

- ✅ All tables are created if they don't exist
- ✅ Default admin user is seeded (username: `admin`, password: `admin123`)
- ✅ Alembic migrations are tracked
- ✅ Full schema verification is logged

### Option 2: Manual Initialization

```bash
# Initialize database manually
make db-init-schema

# Verify schema integrity
make db-verify-schema
```

## Understanding the Database Structure

### Tables Created

The system creates **15 core tables**:

| Table | Purpose |
|-------|---------|
| `users` | User accounts and authentication |
| `backtest_runs` | Backtest execution records |
| `backtest_results` | Per-pair results from backtests |
| `backtest_strategies` | Saved trading strategies |
| `backtest_trades` | Individual trade records |
| `backtest_candles` | OHLCV price data |
| `backtest_positions` | Position history |
| `backtest_logs` | Backtest execution logs |
| `strategy_version_history` | Strategy version tracking |
| `strategy_execution_states` | Strategy execution state snapshots |
| `trade_logs` | Trade execution logs |
| `bot_settings` | Configuration settings |
| `redis_settings` | Redis configuration |
| `audit_logs` | System audit trail |
| `backtest_comparisons` | Backtest comparison results |

### Schema Hierarchy

```
users (1:N) ↓
  ├─ backtest_runs (1:N) → backtest_results (1:N) → trade_logs
  ├─ backtest_strategies (1:N) → strategy_version_history
  └─ audit_logs
```

## Initialization Methods

### Method 1: Automatic (Recommended for Development)

```python
# In backend/main.py lifespan startup
init_db()  # Called automatically on server startup
```

**Advantages:**

- ✅ Automatic on every start
- ✅ Safe - won't recreate existing tables
- ✅ Creates admin user automatically
- ✅ Idempotent - can be called multiple times

### Method 2: Manual Script

```bash
# Full initialization with logging
python scripts/init_database.py

# Or using make target
make db-init-schema

# Example output:
# ✅ Database initialization completed successfully
# ✅ All 15 expected tables present
```

### Method 3: Alembic Migrations

```bash
# Apply all pending migrations
make migration-up

# Or directly
alembic upgrade head
```

## Verification & Troubleshooting

### Verify Schema Integrity

```bash
# Comprehensive schema verification
make db-verify-schema

# Example output:
# ✅ All 15 expected tables exist
# ✅ backtest_runs: 32 columns present
# ✅ backtest_strategies: 36 columns present
# ✅ users: 11 columns present
```

### Check Migration Status

```bash
# View current migration and history
make migration-verify

# Example output:
# 📍 CURRENT MIGRATION: 9f8g7h6i5j4k (add_strategy_version_id_to_backtest_runs)
# 📜 MIGRATION HISTORY:
#   ✓ 7e5d92f3ed96 (increase_hashed_password_column_size)
#   ✓ 8a1b2c3d4e5f (add_missing_strategy_columns)
#   ✓ 9f8g7h6i5j4k (add_strategy_version_id_to_backtest_runs)
```

### Common Issues

#### ❌ "Column does not exist" Error

**Cause:** Database schema out of sync with models

**Solution:**

```bash
# Option 1: Apply missing migrations
make migration-up

# Option 2: Reinitialize schema
make db-verify-schema      # Check what's missing
make db-init-schema        # Create missing tables
```

#### ❌ "Table already exists" Error

**Cause:** Attempting to create existing table

**Solution:**

```bash
# This is normal and safe - just skip the table
# init_db() handles this automatically

# To fully reset:
make db-reset             # ⚠️ CAUTION: Deletes all data
```

#### ❌ Admin User Cannot Login

**Cause:** Admin user not created or password hash corrupted

**Solution:**

```bash
# Reinitialize admin user
python scripts/reset_admin_password.py

# Default credentials after reset:
# Username: admin
# Password: admin123
```

## Database Reset

### ⚠️ WARNING: Destructive Operation

```bash
# Reset database (drop and recreate all tables)
make db-reset

# You will be prompted for confirmation:
# This will drop ALL tables and data!
# Are you sure? Type 'yes' to confirm:
```

**What happens:**

1. ✅ All tables are dropped
2. ✅ All tables are recreated
3. ✅ Admin user is reseeded
4. ✅ Schema is verified

## Configuration

### Database Connection

Database URL is configured in `.env`:

```bash
# .env file
DATABASE_URL=postgresql://postgres:password@localhost:5432/dydx_backtest
# OR for SQLite (development):
DATABASE_URL=sqlite:///./dydx_backtest.db
```

Or via environment variables:

```bash
export DB_TYPE=postgresql          # postgresql or sqlite
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=dydx_backtest
export DB_USER=postgres
export DB_PASSWORD=your_password
```

### Connection Pooling (PostgreSQL)

```bash
export DB_POOL_SIZE=5              # Connection pool size
export DB_MAX_OVERFLOW=10          # Max overflow connections
export DB_TIMEOUT=30               # Query timeout in seconds
```

## Development Workflow

### Fresh Start (New Environment)

```bash
# 1. Setup virtual environment
make setup

# 2. Install dependencies
make install

# 3. Configure environment
make config
cp .env.example .env
# Edit .env with your database URL

# 4. Initialize database
make backend-run    # Automatically initializes on startup
# or manually:
make db-init-schema

# 5. Verify setup
make db-verify-schema
```

### Adding New Tables

```bash
# 1. Create model in backend/database.py
class MyModel(Base):
    __tablename__ = "my_table"
    # ... columns ...

# 2. Create migration
make create-migration MSG="add my_table"

# 3. Apply migration
make migration-up

# 4. Verify
make db-verify-schema
```

### Troubleshooting Schema Drift

```bash
# If models and database don't match:

# 1. Check what's missing
make db-verify-schema

# 2. Create migration for changes
make create-migration MSG="fix schema drift"

# 3. Verify the generated migration in alembic/versions/
# 4. Apply it
make migration-up

# 5. Confirm
make db-verify-schema
```

## Production Considerations

### Migration Strategy

For production, always:

1. **Backup database first**

   ```bash
   pg_dump dydx_backtest > backup_$(date +%Y%m%d).sql
   ```

2. **Test migrations in staging**

   ```bash
   # Apply on staging database first
   alembic upgrade head
   ```

3. **Apply with zero downtime**

   ```bash
   # Run migrations before restarting app
   make migration-up
   
   # Then restart app
   make backend-run
   ```

### Monitoring

```bash
# Check database status
make migration-verify

# Monitor connections
psql dydx_backtest -c "SELECT count(*) FROM pg_stat_activity;"

# View active queries
psql dydx_backtest -c "SELECT * FROM pg_stat_statements;"
```

## Scripts Reference

### `scripts/init_database.py`

Comprehensive database initialization and verification tool:

```bash
# Initialize database
python scripts/init_database.py

# Verify schema
python scripts/init_database.py --verify

# Reset database
python scripts/init_database.py --reset

# Check specific table
python scripts/init_database.py --verify | grep backtest_runs
```

### `scripts/reset_admin_password.py`

Reset admin user credentials:

```bash
python scripts/reset_admin_password.py
# Username: admin
# Password: admin123
```

## Monitoring Commands

```bash
# View all database commands
make help | grep "db-\|migration\|database"

# List available tables
psql dydx_backtest -c "\dt"

# Count records in each table
psql dydx_backtest -c "SELECT tablename, count(*) FROM pg_tables LEFT JOIN pg_stat_user_tables ON tablename = relname WHERE schi
name = 'public' GROUP BY tablename;"

# Check migrations
make migration-verify
```

## FAQ

**Q: Do I need to manually initialize the database?**
A: No! The backend automatically initializes on startup. Just run `make backend-run`.

**Q: Can I use SQLite for development?**
A: Yes! Set `DB_TYPE=sqlite` in your `.env`. It's convenient for development but PostgreSQL is recommended for production.

**Q: How do I add new columns to existing tables?**
A: Create a migration: `make create-migration MSG="add column description"`, edit the migration file, then `make migration-up`.

**Q: What if I need to rollback?**
A: Use `make migration-down N=1` to rollback the last migration.

**Q: How often should I reset the database?**
A: Only in development when the schema changes. **Never in production!**

**Q: Can I have multiple database schemas?**
A: The tool currently supports one database. For multiple schemas, modify `alembic.ini` and database configuration.
