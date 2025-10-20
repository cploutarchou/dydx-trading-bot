# 🚀 Migration Quick Reference

Simple Make commands for database migrations.

## Commands

### `make create-migration MSG='description'`

Create a new migration file

```bash
# Example
make create-migration MSG='add user email verification'
make create-migration MSG='add backtest filters'

# Output
✅ Migration created in alembic/versions/
```

---

### `make migration-up`

Apply all pending migrations to the database

```bash
make migration-up

# Output
✅ Database upgraded to latest migration
```

---

### `make migration-down N=1`

Rollback N migrations

```bash
# Rollback 1 migration
make migration-down N=1

# Rollback 3 migrations
make migration-down N=3

# Output
✅ Rolled back X migration(s)
```

---

### `make migration-verify`

Show current migration version and full history

```bash
make migration-verify

# Output
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 CURRENT MIGRATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
add_dydx_keys_table (head)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📜 MIGRATION HISTORY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Shows full migration chain]
✅ Verification complete
```

---

## Typical Workflow

### Step 1: Create a new migration

```bash
make create-migration MSG='add payment tracking table'
```

### Step 2: Review the generated file

```bash
# Check alembic/versions/<new_migration_name>.py
cat alembic/versions/*.py | tail -50
```

### Step 3: Apply the migration

```bash
make migration-up
```

### Step 4: Verify it worked

```bash
make migration-verify
```

---

## Examples

### Add a new table

```bash
make create-migration MSG='create orders table'
make migration-up
make migration-verify
```

### Modify existing table

```bash
make create-migration MSG='add status column to orders'
make migration-up
```

### Rollback the last migration

```bash
make migration-down N=1
make migration-verify
```

### Rollback 3 migrations

```bash
make migration-down N=3
```

---

## Advanced Commands (Legacy)

For advanced scenarios, the old db-* commands are still available:

- `make db-branches` - Show migration branches
- `make db-merge MESSAGE='x'` - Merge conflicting branches
- `make db-migrate-legacy` - Run legacy migrations

---

## 📌 Important Notes

✅ Always use `MSG=` parameter with `create-migration`  
✅ Always use `N=` parameter with `migration-down`  
✅ Review generated migrations before applying with `migration-up`  
✅ Use `migration-verify` to check the current state  
✅ Run from project root: `/home/chris/workspace/dydx-trading-bot/`
