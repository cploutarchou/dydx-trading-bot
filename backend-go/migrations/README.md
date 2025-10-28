# Database Migrations

This directory contains all database schema migrations using [golang-migrate](https://github.com/golang-migrate/migrate).

## Migration Files

Migrations are numbered sequentially with both `.up.sql` and `.down.sql` files:

- **`.up.sql`** - Schema changes applied when migrating up
- **`.down.sql`** - Schema changes reverted when migrating down

Current migrations:

1. `000001_create_redis_settings` - Redis configuration settings table
2. `000001_create_users` - User accounts table
3. `000002_create_audit_logs` - Audit trail for user actions
4. `000003_create_backtest_strategies` - Trading strategy definitions
5. `000004_create_bot_settings` - Bot configuration settings
6. `000005_create_dydx_key_settings` - dYdX key settings per user
7. `000006_create_dydx_keys` - Encrypted dYdX API keys
8. `000007_create_strategy_execution_states` - Real-time strategy execution state
9. `000008_create_strategy_version_history` - Version history for strategies
10. `000009_create_backtest_runs` - Backtest execution records
11. `000010_create_backtest_candles` - OHLCV candle data for backtests
12. `000011_create_backtest_results` - Pair-wise backtest results
13. `000012_create_backtest_trades` - Individual trade records
14. `000013_create_backtest_positions` - Open/closed positions in backtests
15. `000014_create_backtest_logs` - Backtest execution logs
16. `000015_create_backtest_comparisons` - Strategy comparison results
17. `000016_create_trade_logs` - Detailed trade logs from backtest results

## Local Development (SQLite)

### Using the Migration CLI

Build the migration tool:
```bash
go build -o bin/migrate ./cmd/migrate
```

Run all pending migrations:
```bash
./bin/migrate -path migrations -direction up
```

Rollback all migrations:
```bash
./bin/migrate -path migrations -direction down
```

Migrate to a specific version:
```bash
./bin/migrate -path migrations -version 5
```

Step forward by N migrations:
```bash
./bin/migrate -path migrations -steps 3
```

### Automatic Migrations on Startup

The server automatically runs migrations on startup if configured. Set `AutoMigrate: true` in `internal/db/db.go`:

```go
database, err := db.New(db.Config{
    Driver:       "sqlite",
    DSN:          "trading_bot.db",
    AutoMigrate:  true,  // Enable automatic migrations
    MaxOpenConns: 25,
    MaxIdleConns: 5,
})
```

## Production (PostgreSQL)

For PostgreSQL, use the migration CLI with environment variables:

```bash
DB_DRIVER=postgres \
DB_DSN="postgres://user:password@localhost:5432/trading_bot?sslmode=disable" \
./bin/migrate -path migrations -direction up
```

Or set `AutoMigrate: true` in the database config and the server will handle migrations automatically on startup.

## Writing New Migrations

When adding new tables or schema changes:

1. **Create a new migration file pair:**
   ```bash
   # Use the next sequential number
   touch migrations/000017_my_migration.up.sql
   touch migrations/000017_my_migration.down.sql
   ```

2. **Write the UP migration** (000017_my_migration.up.sql):
   ```sql
   -- Create my_table
   CREATE TABLE IF NOT EXISTS my_table (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       name VARCHAR(100) NOT NULL,
       created_at DATETIME DEFAULT NULL
   );
   
   CREATE INDEX ix_my_table_name ON my_table(name);
   ```

3. **Write the DOWN migration** (000017_my_migration.down.sql):
   ```sql
   -- Drop my_table
   DROP TABLE IF EXISTS my_table;
   ```

4. **Test locally:**
   ```bash
   ./bin/migrate -path migrations -direction up
   # Verify the schema
   ./bin/migrate -path migrations -direction down
   # Verify rollback works
   ```

## Migration Status

Check current migration version (requires golang-migrate CLI):

```bash
migrate -path migrations -database "sqlite3:trading_bot.db" version
```

## Important Notes

- **SQLite** uses `AUTOINCREMENT` for auto-incrementing primary keys instead of `SERIAL`
- **SQLite** uses `REAL` for floating-point numbers instead of `FLOAT8`
- **SQLite** uses `TEXT` with `UNIQUE` constraints for string uniqueness
- All tables use `DATETIME` for timestamp fields (SQLite doesn't have native TIMESTAMP)
- Foreign keys must be created with `FOREIGN KEY` constraints (SQLite needs PRAGMA foreign_keys = ON at runtime)
- JSON support uses SQLite's native JSON1 extension (ensure it's compiled in)

## Troubleshooting

### Migration fails with "table already exists"

This usually happens if running migrations on an existing database. The `CREATE TABLE IF NOT EXISTS` clauses should handle this, but if you have existing tables, migrations will skip them gracefully.

### SQLite database locked

Ensure no other processes are accessing the database file. Close the connection before running migrations.

### Migration version mismatch

If the schema_migrations table gets out of sync, you may need to manually clean it:

```bash
sqlite3 trading_bot.db "DELETE FROM schema_migrations WHERE version = 5;"
```

Then re-run the migration.

