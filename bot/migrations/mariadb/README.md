# MariaDB Alembic Migrations (Bot)

This directory contains the active Alembic migration scripts for the bot MariaDB schema.

## Status

Active. Alembic is configured to read this directory through `version_locations`.

## Migration File Naming

MariaDB migration files follow the existing Alembic naming convention:
- `<revision_id>_<description>.py`

## MariaDB Rules

### 1. Status Values
Prefer reviewable string columns or explicit lookup tables:

```python
sa.String(20)  # with FK to lookup table
```

### 2. Auto-Increment IDs
Use SQLAlchemy auto-increment columns for generated integer IDs:

```python
sa.Column('id', sa.Integer(), autoincrement=True)  # Identical in SQLAlchemy
```

### 3. Numeric Precision
Financial columns use DECIMAL, which is the same across both databases but requires careful testing:

```python
sa.Column('entry_price', sa.Numeric(18, 8))  # Compatible with both
```

### 4. JSON Operations
Use MariaDB JSON functions:

```sql
WHERE JSON_CONTAINS(selected_markets, '{"BTC": true}')
```

### 5. JSON Indexing
Review generated columns or normal relational tables before adding JSON indexes:

```python
sa.Index('idx_market_symbol', 'market_symbol')
```

## Running Migrations

```bash
cd bot/
alembic upgrade head  # Apply all migrations
alembic downgrade -1  # Rollback last migration
```

## Testing

Each migration should be tested:
1. Create fresh MariaDB database
2. Run Alembic upgrade: `alembic upgrade head`
3. Verify schema with `DESCRIBE table_name`
4. Rollback: `alembic downgrade base`
5. Verify tables are cleaned up

## CRITICAL NOTES

⚠️ **Numeric Precision Testing**: All Numeric(18,8) columns must preserve financial precision.

⚠️ **Status Value Changes**: New lookup rows or allowed values must be populated before data migration.

⚠️ **Migration Locks**: Test bot instance concurrency against MariaDB before production rollout.
