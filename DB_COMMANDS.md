# 🚀 Alembic Make Commands - Quick Reference

## Commands Added to Makefile

All commands use `.venv` virtual environment automatically.

### Apply Migrations

```bash
make db-upgrade              # Apply all pending migrations to database
```

### Create Migrations

```bash
make db-revision MESSAGE='your description'    # Create new migration
```

Example:

```bash
make db-revision MESSAGE='add user avatar column'
```

### Rollback Migrations

```bash
make db-downgrade STEPS=1    # Rollback 1 migration
make db-downgrade STEPS=2    # Rollback 2 migrations
```

### View Status

```bash
make db-current              # Show current migration version
make db-history              # Show all migrations history
make db-branches             # Check for migration conflicts
```

### Advanced / Maintenance

```bash
make db-merge MESSAGE='description'      # Merge migration branches
make db-migrate-legacy                   # Run old SQLite migration
```

---

## Common Workflows

### ✅ First Time Setup

```bash
source .venv/bin/activate
make db-upgrade
make db-current
```

### ✅ Add Database Column

```bash
# Update your model in backend/models/
make db-revision MESSAGE='add new_column to users table'
# Review the generated file in alembic/versions/
make db-upgrade
```

### ✅ Check What's Pending

```bash
make db-history
```

### ✅ Rollback Last Migration

```bash
make db-downgrade STEPS=1
```

### ✅ Merge Conflicting Migrations (Multiple Developers)

```bash
make db-branches
make db-merge MESSAGE='merge concurrent migrations'
make db-upgrade
```

---

## Under the Hood

Each command maps to:

| Command | Maps To |
|---------|---------|
| `make db-upgrade` | `.venv/bin/alembic upgrade head` |
| `make db-revision MESSAGE='x'` | `.venv/bin/alembic revision --autogenerate -m "x"` |
| `make db-downgrade STEPS=N` | `.venv/bin/alembic downgrade -N` |
| `make db-current` | `.venv/bin/alembic current` |
| `make db-history` | `.venv/bin/alembic history --verbose` |
| `make db-branches` | `.venv/bin/alembic branches` |
| `make db-merge MESSAGE='x'` | `.venv/bin/alembic merge -m "x"` |
| `make db-migrate-legacy` | `.venv/bin/python migrate_db.py` |

---

## Files

- **Makefile**: Added 8 new `db-*` commands
- **ALEMBIC_GUIDE.md**: Detailed guide with examples (in repo)
- **alembic/**: Migration configuration already in place
- **alembic/versions/**: Your migration files live here

---

## Get Help

```bash
make help | grep db-     # Show all database commands
```
