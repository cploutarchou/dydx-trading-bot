# MariaDB Alembic Migrations (Bot)

This directory will contain Alembic migration scripts converted from PostgreSQL to MariaDB.

## Status

🔄 **In Progress**: Phase 1 preparation

## Migration File Naming

MariaDB migration files follow the same Alembic naming convention as PostgreSQL:
- `<revision_id>_<description>.py`

## Key Differences from PostgreSQL

### 1. ENUM Types
PostgreSQL native ENUMs have been converted to MariaDB VARCHAR columns with lookup tables:

**PostgreSQL**:
```python
sa.Enum('CREATED', 'RUNNING', 'STOPPED', name='botstatusenum')
```

**MariaDB**:
```python
sa.String(20)  # with FK to lookup table
```

### 2. SERIAL/BIGSERIAL
Auto-increment columns use different definitions:

**PostgreSQL**:
```python
sa.Column('id', sa.Integer(), autoincrement=True)
```

**MariaDB**:
```python
sa.Column('id', sa.Integer(), autoincrement=True)  # Identical in SQLAlchemy
```

### 3. Numeric Precision
Financial columns use DECIMAL, which is the same across both databases but requires careful testing:

```python
sa.Column('entry_price', sa.Numeric(18, 8))  # Compatible with both
```

### 4. JSON Operations
JSONB operations must use MariaDB's JSON functions instead of PostgreSQL operators:

**PostgreSQL**:
```sql
WHERE selected_markets @> '{"BTC": true}'::jsonb
```

**MariaDB**:
```sql
WHERE JSON_CONTAINS(selected_markets, '{"BTC": true}')
```

### 5. GIN Indexes
Generalized Inverted Indexes are not available in MariaDB:

**PostgreSQL**:
```python
sa.Index('idx_markets_gin', 'selected_markets', postgresql_using='gin')
```

**MariaDB**:
```python
sa.Index('idx_markets_ft', 'selected_markets')  # Use FULLTEXT if appropriate
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

⚠️ **ENUM Conversion**: New lookup tables must be populated before data migration.

⚠️ **Advisory Locks**: PostgreSQL advisory locks have been replaced. Test bot instance concurrency.
