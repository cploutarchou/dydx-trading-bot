# Database Migrations

This directory contains all database schema migrations
using [golang-migrate](https://github.com/golang-migrate/migrate).

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

## Local Development (PostgreSQL)

### Using the Migration CLI

Build the migration tool:

```bash
go build -o bin/migrate ./cmd/migrate
```

Run all pending PostgreSQL migrations:

```bash
./bin/migrate -path migrations/postgres -direction up
```

Rollback all migrations:

```bash
./bin/migrate -path migrations/postgres -direction down
```

Migrate to a specific version:

```bash
./bin/migrate -path migrations/postgres -version 5
```

Step forward by N migrations:

```bash
./bin/migrate -path migrations/postgres -steps 3
```

### Automatic Migrations on Startup

The server automatically runs PostgreSQL migrations on startup if configured. Set `AutoMigrate: true` in `internal/db/db.go`:

```go
database, err := db.New(db.Config{
    Driver:       "postgres",
    DSN:          "postgres://user:password@localhost:5432/trading_bot?sslmode=disable",
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
./bin/migrate -path migrations/postgres -direction up
```

Or set `AutoMigrate: true` in the database config and the server will handle migrations automatically on startup.

## Writing New Migrations

When adding new tables or schema changes:

1. **Create a new migration file pair:**
   ```bash
   # Use the next sequential number
   touch migrations/postgres/000017_my_migration.up.sql
   touch migrations/postgres/000017_my_migration.down.sql
   ```

2. **Write the UP migration** (`migrations/postgres/000017_my_migration.up.sql`):
   ```sql
   -- Create my_table
   CREATE TABLE IF NOT EXISTS my_table (
       id BIGSERIAL PRIMARY KEY,
       name VARCHAR(100) NOT NULL,
       created_at TIMESTAMP DEFAULT NULL
   );
   
   CREATE INDEX ix_my_table_name ON my_table(name);
   ```

3. **Write the DOWN migration** (`migrations/postgres/000017_my_migration.down.sql`):
   ```sql
   -- Drop my_table
   DROP TABLE IF EXISTS my_table;
   ```

4. **Test locally:**
   ```bash
   ./bin/migrate -path migrations/postgres -direction up
   # Verify the schema
   ./bin/migrate -path migrations/postgres -direction down
   # Verify rollback works
   ```

## Migration Status

Check current migration version (requires golang-migrate CLI):

```bash
migrate -path migrations/postgres -database "postgres://user:password@localhost:5432/trading_bot?sslmode=disable" version
```

## Important Notes

- PostgreSQL is the only supported SQL database in this repository.
- Use PostgreSQL-native column types and defaults in new migrations.
- Keep new migration files under `migrations/postgres`.

## Troubleshooting

### Migration fails with "table already exists"

This usually happens if running migrations on an existing database. The `CREATE TABLE IF NOT EXISTS` clauses should
handle this, but if you have existing tables, migrations will skip them gracefully.

### Migration version mismatch

If the schema_migrations table gets out of sync, you may need to manually clean it:

Use `psql` to inspect and repair migration metadata if necessary, for example:

```bash
psql "postgres://user:password@localhost:5432/trading_bot?sslmode=disable" \
  -c "DELETE FROM schema_migrations WHERE version = 5;"
```

Then re-run the migration.

