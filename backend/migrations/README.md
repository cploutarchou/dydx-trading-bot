# Database Migrations

This directory contains all database schema migrations
using [golang-migrate](https://github.com/golang-migrate/migrate).

## Migration Files

Migrations are numbered sequentially with both `.up.sql` and `.down.sql` files:

- **`.up.sql`** - Schema changes applied when migrating up
- **`.down.sql`** - Schema changes reverted when migrating down

Current migrations:

| #      | File                                                        | Description                                                                                                                                             |
| ------ | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 000001 | `create_redis_settings`                                     | Redis configuration settings table                                                                                                                      |
| 000002 | `create_users`                                              | User accounts table with roles, MFA, and subscription fields                                                                                            |
| 000003 | `create_audit_logs`                                         | Audit trail for user actions                                                                                                                            |
| 000004 | `create_backtest_strategies`                                | Trading strategy definitions                                                                                                                            |
| 000005 | `create_bot_settings`                                       | Bot configuration key-value settings                                                                                                                    |
| 000006 | `create_dydx_key_settings`                                  | dYdX key settings per user *(dropped in 000044)*                                                                                                        |
| 000007 | `create_dydx_keys`                                          | Encrypted dYdX API keys per user and network                                                                                                            |
| 000008 | `create_strategy_execution_states`                          | Real-time execution state for strategies                                                                                                                |
| 000009 | `create_strategy_version_history`                           | Immutable version history for strategy configs                                                                                                          |
| 000010 | `create_backtest_runs`                                      | Backtest execution run records                                                                                                                          |
| 000011 | `create_backtest_candles`                                   | OHLCV candle data linked to backtest runs                                                                                                               |
| 000012 | `create_backtest_results`                                   | Pair-wise performance results per run                                                                                                                   |
| 000013 | `create_backtest_trades`                                    | Individual simulated trades per run                                                                                                                     |
| 000014 | `create_backtest_positions`                                 | Open/closed positions per run                                                                                                                           |
| 000015 | `create_backtest_logs`                                      | Execution log events per run                                                                                                                            |
| 000016 | `create_backtest_comparisons`                               | Strategy comparison records *(dropped in 000044)*                                                                                                       |
| 000017 | `create_trade_logs`                                         | Detailed trade logs from backtest results                                                                                                               |
| 000018 | `create_user_mfa`                                           | TOTP MFA secrets and backup codes per user                                                                                                              |
| 000019 | `add_strategy_fields_and_metrics`                           | Adds strategy columns to `backtest_trades`; creates `backtest_metrics` *(dropped in 000044)*                                                            |
| 000020 | `create_cointegration_results`                              | Cointegration analysis results *(dropped in 000044; service uses file storage)*                                                                         |
| 000021 | `create_external_api_credentials`                           | Encrypted external API credentials per user                                                                                                             |
| 000022 | `create_bot_instances`                                      | Live bot runtime instance records                                                                                                                       |
| 000023 | `create_bot_trades`                                         | Real-money trade records per bot instance                                                                                                               |
| 000024 | `create_bot_positions`                                      | Real-money position records per bot instance                                                                                                            |
| 000025 | `create_bot_alerts`                                         | Bot runtime alert tracking *(dropped in 000044)*                                                                                                        |
| 000026 | `align_strategy_execution_state_runtime_schema`             | Adds `is_running`, `last_run_at`, `next_run_at`, `state` to execution states                                                                            |
| 000027 | `add_subscription_fields_to_users`                          | Adds subscription plan/status/expiry fields to `users`                                                                                                  |
| 000028 | `create_subscriptions`                                      | Subscription records with trial and billing periods                                                                                                     |
| 000029 | `create_subscription_features`                              | Feature flag definitions per subscription tier                                                                                                          |
| 000030 | `create_partner_tables`                                     | `invitation_tokens`, `partner_applications`, `partner_relationships`, `partner_commission_metrics`                                                      |
| 000031 | `add_runtime_strategy_to_backtest_strategies`               | Adds `runtime_strategy` column with default `cointegration`                                                                                             |
| 000032 | `add_pair_selection_mode_to_backtest_strategies`            | Adds `pair_selection_mode` column with default `liquidity`                                                                                              |
| 000033 | `add_ib_tier_commission_rates`                              | IB pyramid tier commission and rebate rate table                                                                                                        |
| 000034 | `add_portal_fields_to_users`                                | Adds portal-specific fields to `users`                                                                                                                  |
| 000035 | `add_password_change_required_to_users`                     | Adds `password_change_required` boolean to `users`                                                                                                      |
| 000036 | `add_runtime_network_and_subaccount_to_backtest_strategies` | Adds `runtime_network` and `runtime_subaccount` columns                                                                                                 |
| 000037 | `add_ib_tier_rates_extra_columns`                           | Extends `ib_tier_commission_rates` with description and audit fields                                                                                    |
| 000038 | `create_rbac_tables`                                        | RBAC roles, permissions, and user-role assignment tables                                                                                                |
| 000039 | `add_portal_settings_sections`                              | Seeds initial portal-specific bot_settings rows                                                                                                         |
| 000040 | `create_ib_tier_commission_rates`                           | Consolidates IB tier rate schema (idempotent guard)                                                                                                     |
| 000041 | `add_portal_subdomain_platform_settings`                    | Adds subdomain and platform branding settings rows                                                                                                      |
| 000042 | `seed_portal_test_clients_and_ibs`                          | **Small QA seed** — CRM/IB fixture set (see below)                                                                                                      |
| 000043 | `seed_portal_bulk_dataset`                                  | **Bulk stress seed** — large CRM/IB dataset (see below)                                                                                                 |
| 000044 | `drop_unused_tables`                                        | Drops 5 tables with no backend query references: `dydx_key_settings`, `backtest_comparisons`, `backtest_metrics`, `cointegration_results`, `bot_alerts` |

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

### Portal seed datasets (CRM/IB)

Both seed migrations are **non-production fixtures** for development and QA.
They are fully reversible — their `.down.sql` files use marker-prefix `DELETE`s
that only remove rows inserted by that migration and leave non-seed data intact.

#### `000042_seed_portal_test_clients_and_ibs` — small QA fixture set

**Purpose:** Compact smoke-check dataset for CRM and IB portal flows.
**Marker prefix:** `seed_portal_20260411_`
**Reversible:** yes — down migration deletes by marker prefix.

Inserts:

- **8 users** — 2 IBs (`ib_atlas`, `ib_nova`), 2 sub-IBs, 4 clients
- **6 partner relationships** — IB → sub-IB and IB/sub-IB → client edges
- **4 commission metric rows** — one 30-day period per IB/sub-IB account
- **4 partner applications** — mix of `pending`, `reviewing`, `approved`, and `rejected`

Suitable for: login smoke tests, IB hierarchy rendering, basic CRM list checks.

#### `000043_seed_portal_bulk_dataset` — large stress/pagination dataset

**Purpose:** High-volume dataset for search, filter, pagination, and deep IB hierarchy testing.
**Marker prefix:** `seed_portal_bulk_20260411_`
**Reversible:** yes — down migration deletes by marker prefix.

Inserts:

- **72 users** — 3 IBs (`ib_atlas`, `ib_nova`, `ib_orion`), 9 sub-IBs (3 per IB), 60 clients (`client_001`–`client_060`) via `generate_series`
- **69 partner relationships** — IB → sub-IB edges, then 60 clients round-robin distributed across 12 sponsor slots (9 sub-IBs + 3 direct-IB slots)
- **12 commission metric rows** — monthly period for every IB and sub-IB
- **6 partner applications** — mix of `pending`, `reviewing`, `approved`, and `rejected` states across IBs/sub-IBs/clients
- **6 invitation tokens** — per-IB tokens covering active, expired, and revoked scenarios
- **3 extra IB tier commission rate rows** — tiers 4, 5, 6 for UI stress and tier-table pagination

Suitable for: pagination/search/filter stress tests, multi-level IB pyramid rendering,
application workflow testing, token lifecycle validation, and tier rate table edge cases.

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

