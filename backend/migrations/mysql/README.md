# MariaDB/MySQL Migrations

This directory contains database migrations for MariaDB 11.4+ (converted from PostgreSQL).

## Structure

- `000N_*.up.sql` — Migration to apply
- `000N_*.down.sql` — Migration to rollback

## Key Changes from PostgreSQL

### 1. ENUM Types → Lookup Tables
PostgreSQL ENUM types have been converted to VARCHAR columns with FOREIGN KEY constraints to lookup tables.

**Example**:
```sql
-- Create lookup table
CREATE TABLE bot_status_enum (
  value VARCHAR(20) PRIMARY KEY,
  description VARCHAR(255) NOT NULL
);

-- Foreign key constraint
ALTER TABLE bot_instance 
  ADD CONSTRAINT fk_bot_status FOREIGN KEY (status) REFERENCES bot_status_enum(value);
```

### 2. SERIAL/BIGSERIAL → AUTO_INCREMENT
All auto-increment columns have been updated:
```sql
-- PostgreSQL
id SERIAL PRIMARY KEY

-- MariaDB
id INT AUTO_INCREMENT PRIMARY KEY
```

### 3. RETURNING Clauses Removed
PostgreSQL's `RETURNING` clause is not supported in MariaDB. Applications must use `LAST_INSERT_ID()` instead.

### 4. ON CONFLICT → ON DUPLICATE KEY UPDATE
Upsert operations have been converted:
```sql
-- PostgreSQL
ON CONFLICT (column) DO UPDATE SET ...

-- MariaDB
ON DUPLICATE KEY UPDATE ...
```

### 5. JSONB → JSON
JSON operations remain similar but some operators and indexes differ.

### 6. GIN Indexes → FULLTEXT Indexes
PostgreSQL's GIN (Generalized Inverted Index) has been converted to FULLTEXT where applicable.

## Running Migrations

Use your migration tool (migrate, flyway, etc.) to apply migrations in order:

```bash
migrate -path backend/migrations/mysql -database "mysql://user:pass@localhost/dbname" up
```

## Rollback

To rollback a migration:

```bash
migrate -path backend/migrations/mysql -database "mysql://user:pass@localhost/dbname" down 1
```

## Testing

Each migration should be tested independently:
1. Apply migration: `migrate up 1`
2. Verify schema matches expected output
3. Run application tests
4. Rollback: `migrate down 1`
5. Verify schema is clean

## CRITICAL NOTES

⚠️ **Financial Precision**: All DECIMAL(18,8) columns must be tested thoroughly. MariaDB decimal handling differs slightly from PostgreSQL.

⚠️ **Transaction Isolation**: MariaDB uses different isolation levels by default. Verify backtest concurrency behavior.

⚠️ **Concurrency**: Advisory locks have been replaced with GET_LOCK()/RELEASE_LOCK(). Test under load.
