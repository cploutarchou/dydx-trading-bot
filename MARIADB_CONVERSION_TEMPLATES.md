# PostgreSQL → MariaDB Conversion Templates

Complete reference guide for converting PostgreSQL-specific SQL patterns to MariaDB equivalents.

---

## 📋 Table of Contents

1. [SERIAL/BIGSERIAL → AUTO_INCREMENT](#serialbigserial--auto_increment)
2. [ENUM Types → Lookup Tables](#enum-types--lookup-tables)
3. [RETURNING Clauses → LAST_INSERT_ID()](#returning-clauses--last_insert_id)
4. [ON CONFLICT → ON DUPLICATE KEY UPDATE](#on-conflict--on-duplicate-key-update)
5. [Advisory Locks → GET_LOCK()](#advisory-locks--get_lock)
6. [Data Types](#data-types)
7. [Functions](#functions)
8. [Indexes](#indexes)
9. [Constraints](#constraints)

---

## SERIAL/BIGSERIAL → AUTO_INCREMENT

### Pattern 1: CREATE TABLE with SERIAL
```sql
-- PostgreSQL
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL
);

-- MariaDB
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL
);
```

### Pattern 2: CREATE TABLE with BIGSERIAL
```sql
-- PostgreSQL
CREATE TABLE orders (
  id BIGSERIAL PRIMARY KEY,
  user_id INT NOT NULL
);

-- MariaDB
CREATE TABLE orders (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL
);
```

### Pattern 3: Add SERIAL to existing table
```sql
-- PostgreSQL
ALTER TABLE logs ADD COLUMN id SERIAL PRIMARY KEY;

-- MariaDB
ALTER TABLE logs ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY;
```

---

## ENUM Types → Lookup Tables

### Pattern: Convert PostgreSQL ENUM to MariaDB Lookup Table

```sql
-- PostgreSQL
CREATE TYPE botstatusenum AS ENUM ('CREATED', 'RUNNING', 'STOPPED', 'ERROR');

CREATE TABLE bot_instance (
  id SERIAL PRIMARY KEY,
  status botstatusenum NOT NULL DEFAULT 'CREATED'
);

-- MariaDB
-- 1. Create lookup table
CREATE TABLE bot_status_enum (
  value VARCHAR(20) PRIMARY KEY,
  description VARCHAR(255)
);

-- 2. Insert enum values
INSERT INTO bot_status_enum VALUES 
  ('CREATED', 'Bot created'),
  ('RUNNING', 'Bot running'),
  ('STOPPED', 'Bot stopped'),
  ('ERROR', 'Bot error');

-- 3. Create main table with VARCHAR
CREATE TABLE bot_instance (
  id INT AUTO_INCREMENT PRIMARY KEY,
  status VARCHAR(20) NOT NULL DEFAULT 'CREATED',
  FOREIGN KEY (status) REFERENCES bot_status_enum(value)
);

-- 4. Add CHECK constraint for additional safety (optional)
ALTER TABLE bot_instance 
  ADD CONSTRAINT chk_bot_status 
  CHECK (status IN ('CREATED', 'RUNNING', 'STOPPED', 'ERROR'));
```

### Pattern: ALTER TYPE to add new enum value
```sql
-- PostgreSQL
ALTER TYPE botstatusenum ADD VALUE 'PAUSED' AFTER 'RUNNING';

-- MariaDB
-- 1. Remove foreign key constraint (if exists)
ALTER TABLE bot_instance DROP FOREIGN KEY fk_bot_instance_status;

-- 2. Insert new value
INSERT INTO bot_status_enum VALUES ('PAUSED', 'Bot paused');

-- 3. Re-add constraint
ALTER TABLE bot_instance 
  ADD CONSTRAINT fk_bot_instance_status 
  FOREIGN KEY (status) REFERENCES bot_status_enum(value);
```

---

## RETURNING Clauses → LAST_INSERT_ID()

### Pattern 1: INSERT with RETURNING
```sql
-- PostgreSQL
INSERT INTO bot_settings (name, value) VALUES ('key1', 'value1')
RETURNING id, created_at;

-- MariaDB (using stored procedure)
INSERT INTO bot_settings (name, value) VALUES ('key1', 'value1');
SELECT id, created_at FROM bot_settings WHERE id = LAST_INSERT_ID();

-- Or in Go code:
-- 1. Execute INSERT
-- 2. Get lastID := result.LastInsertedID()
-- 3. Query SELECT to get returned fields
```

### Pattern 2: UPDATE with RETURNING
```sql
-- PostgreSQL
UPDATE bot_settings SET value = 'new_value' WHERE id = 1
RETURNING id, name, value, updated_at;

-- MariaDB
UPDATE bot_settings SET value = 'new_value' WHERE id = 1;
SELECT id, name, value, updated_at FROM bot_settings WHERE id = 1;
```

### Pattern 3: DELETE with RETURNING
```sql
-- PostgreSQL
DELETE FROM bot_alerts WHERE id = 1
RETURNING id, title, severity;

-- MariaDB
-- First, select the data to return
SELECT id, title, severity INTO @id, @title, @severity FROM bot_alerts WHERE id = 1;
-- Then delete
DELETE FROM bot_alerts WHERE id = 1;
-- Return the selected values (in application code)
SELECT @id, @title, @severity;
```

### Pattern 4: In Go repositories (RETURNING)
```go
// PostgreSQL
const insertSQL = `
  INSERT INTO bot_settings (name, value) VALUES ($1, $2)
  RETURNING id, created_at
`
var id int
var createdAt time.Time
err := r.db.QueryRowContext(ctx, insertSQL, name, value).Scan(&id, &createdAt)

// MariaDB (Two-step approach)
const insertSQL = `
  INSERT INTO bot_settings (name, value) VALUES (?, ?)
`
result, err := r.db.ExecContext(ctx, insertSQL, name, value)
lastID, _ := result.LastInsertId()

const selectSQL = `
  SELECT id, created_at FROM bot_settings WHERE id = ?
`
var id int
var createdAt time.Time
err = r.db.QueryRowContext(ctx, selectSQL, lastID).Scan(&id, &createdAt)
```

---

## ON CONFLICT → ON DUPLICATE KEY UPDATE

### Pattern 1: Simple upsert with ON CONFLICT
```sql
-- PostgreSQL
INSERT INTO partner_relationships (partner_user_id, status) VALUES (123, 'ACTIVE')
ON CONFLICT (partner_user_id) DO UPDATE SET status = 'ACTIVE', updated_at = NOW()
RETURNING id, partner_user_id, status;

-- MariaDB
INSERT INTO partner_relationships (partner_user_id, status) VALUES (123, 'ACTIVE')
ON DUPLICATE KEY UPDATE 
  status = VALUES(status), 
  updated_at = NOW();

SELECT id, partner_user_id, status FROM partner_relationships 
WHERE partner_user_id = 123;
```

### Pattern 2: ON CONFLICT with multiple columns
```sql
-- PostgreSQL
INSERT INTO backtest_runs (strategy_id, user_id, status) VALUES (1, 2, 'QUEUED')
ON CONFLICT (strategy_id, user_id) DO UPDATE SET status = 'QUEUED'
RETURNING id;

-- MariaDB
-- Create UNIQUE constraint on (strategy_id, user_id) if not exists
INSERT INTO backtest_runs (strategy_id, user_id, status) VALUES (1, 2, 'QUEUED')
ON DUPLICATE KEY UPDATE status = VALUES(status);

SELECT id FROM backtest_runs WHERE strategy_id = 1 AND user_id = 2;
```

### Pattern 3: ON CONFLICT with constant values
```sql
-- PostgreSQL
INSERT INTO user_settings (user_id, key, value) VALUES (1, 'theme', 'dark')
ON CONFLICT (user_id, key) DO UPDATE SET value = 'dark', updated_at = NOW()
RETURNING id, updated_at;

-- MariaDB
INSERT INTO user_settings (user_id, key, value) VALUES (1, 'theme', 'dark')
ON DUPLICATE KEY UPDATE 
  value = VALUES(value), 
  updated_at = NOW();

SELECT id, updated_at FROM user_settings WHERE user_id = 1 AND key = 'theme';
```

---

## Advisory Locks → GET_LOCK()

### Pattern 1: Transaction-scoped advisory lock
```sql
-- PostgreSQL
BEGIN;
SELECT pg_advisory_xact_lock(123);
-- ... do work ...
COMMIT;  -- Lock released automatically

-- MariaDB
-- In application code:
BEGIN;
SELECT GET_LOCK('backtest_123', 30);  -- 30 second timeout
-- ... do work ...
SELECT RELEASE_LOCK('backtest_123');
COMMIT;
```

### Pattern 2: Session-scoped advisory lock
```sql
-- PostgreSQL
SELECT pg_advisory_lock(456);
-- ... do work ...
SELECT pg_advisory_unlock(456);

-- MariaDB
SELECT GET_LOCK('resource_456', 30);  -- 30 second timeout
-- ... do work ...
SELECT RELEASE_LOCK('resource_456');
```

### Pattern 3: In Go code (backtest admission control)
```go
// PostgreSQL
func (r *BacktestRepository) withAdvisoryLock(ctx context.Context, userID int, fn func() error) error {
    query := `SELECT pg_advisory_xact_lock($1)`
    _, err := r.db.ExecContext(ctx, query, userID)
    if err != nil {
        return err
    }
    return fn()
}

// MariaDB
func (r *BacktestRepository) withAdvisoryLock(ctx context.Context, userID int, fn func() error) error {
    lockName := fmt.Sprintf("backtest_%d", userID)
    query := `SELECT GET_LOCK(?, 30)`  // 30 second timeout
    var acquired int
    err := r.db.QueryRowContext(ctx, query, lockName).Scan(&acquired)
    if err != nil || acquired != 1 {
        return fmt.Errorf("failed to acquire lock: %w", err)
    }
    defer r.db.QueryRowContext(ctx, `SELECT RELEASE_LOCK(?)`, lockName)
    return fn()
}
```

---

## Data Types

### NUMERIC/DECIMAL
```sql
-- Both PostgreSQL and MariaDB support DECIMAL
-- No conversion needed, but test precision handling
DECIMAL(18, 8)    -- 18 total digits, 8 decimal places (financial data)
DECIMAL(8, 4)     -- 8 total digits, 4 decimal places (percentages)

-- Verify precision in application code - MariaDB may differ slightly
```

### VARCHAR
```sql
-- No conversion needed
VARCHAR(255)
VARCHAR(MAX)      -- PostgreSQL TEXT in MariaDB should be LONGTEXT for compatibility
```

### TEXT → LONGTEXT
```sql
-- PostgreSQL
CREATE TABLE documents (
  id SERIAL PRIMARY KEY,
  content TEXT NOT NULL
);

-- MariaDB (if content > 65KB)
CREATE TABLE documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  content LONGTEXT NOT NULL
);
```

### TIMESTAMP/DATETIME
```sql
-- Both support similar timestamp handling
TIMESTAMP DEFAULT CURRENT_TIMESTAMP
DATETIME DEFAULT CURRENT_TIMESTAMP

-- MariaDB tip: Use DATETIME for better precision, TIMESTAMP for automatic UTC conversion
```

### UUID Type
```sql
-- PostgreSQL
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid()
);

-- MariaDB (use CHAR(36) for UUID strings)
CREATE TABLE users (
  id CHAR(36) PRIMARY KEY,
  -- Generate UUIDs in application code using UUID() or UUID_TO_BIN()
);
```

### JSON/JSONB
```sql
-- PostgreSQL
CREATE TABLE strategies (
  id SERIAL PRIMARY KEY,
  selected_markets JSONB NOT NULL DEFAULT '[]'::jsonb
);

-- MariaDB
CREATE TABLE strategies (
  id INT AUTO_INCREMENT PRIMARY KEY,
  selected_markets JSON NOT NULL DEFAULT '[]'
);
```

---

## Functions

### NOW() / CURRENT_TIMESTAMP
```sql
-- Both work identically
NOW()                  -- Returns current timestamp
CURRENT_TIMESTAMP      -- Alias for NOW()

-- Equivalent:
TIMESTAMP DEFAULT CURRENT_TIMESTAMP
TIMESTAMP DEFAULT NOW()
```

### EXTRACT() - Date/Time Extraction
```sql
-- PostgreSQL
SELECT EXTRACT(YEAR FROM created_at) as year;
SELECT EXTRACT(MONTH FROM created_at) as month;

-- MariaDB (identical)
SELECT EXTRACT(YEAR FROM created_at) as year;
SELECT EXTRACT(MONTH FROM created_at) as month;

-- MariaDB alternatives:
SELECT YEAR(created_at) as year;
SELECT MONTH(created_at) as month;
```

### JSON Operations
```sql
-- PostgreSQL
SELECT * FROM strategies 
WHERE selected_markets @> '{"BTC": true}'::jsonb;

-- MariaDB
SELECT * FROM strategies 
WHERE JSON_CONTAINS(selected_markets, '{"BTC": true}');

-- MariaDB also supports:
WHERE JSON_EXTRACT(selected_markets, '$.BTC') = true
```

### String Concatenation
```sql
-- PostgreSQL
SELECT name || ' ' || email FROM users;

-- MariaDB
SELECT CONCAT(name, ' ', email) FROM users;
```

### ARRAY Functions
```sql
-- PostgreSQL
SELECT ARRAY_AGG(market_name) FROM markets;
SELECT markets[0] FROM strategies;

-- MariaDB (use JSON array functions)
SELECT JSON_ARRAYAGG(market_name) FROM markets;
SELECT JSON_EXTRACT(markets, '$[0]') FROM strategies;
```

---

## Indexes

### B-Tree Indexes (Standard)
```sql
-- PostgreSQL
CREATE INDEX idx_user_email ON users(email);

-- MariaDB (identical)
CREATE INDEX idx_user_email ON users(email);
```

### GIN Indexes (Full-Text Search)
```sql
-- PostgreSQL
CREATE INDEX idx_strategy_markets_gin ON backtest_strategies 
  USING gin (selected_markets);

-- MariaDB - Use FULLTEXT for JSON search
CREATE FULLTEXT INDEX idx_strategy_markets_ft ON backtest_strategies(selected_markets);

-- Or use regular B-tree with JSON extraction:
CREATE INDEX idx_strategy_markets ON backtest_strategies(
  (JSON_EXTRACT(selected_markets, '$.BTC'))
);
```

### Partial/Conditional Indexes
```sql
-- PostgreSQL
CREATE INDEX idx_active_users ON users(id) WHERE active = true;

-- MariaDB (not directly supported, use generated column)
ALTER TABLE users ADD COLUMN active_flag TINYINT GENERATED ALWAYS AS (active) STORED;
CREATE INDEX idx_active_users ON users(id, active_flag);
```

### Composite Indexes
```sql
-- PostgreSQL & MariaDB (identical)
CREATE INDEX idx_user_strategy ON backtest_runs(user_id, strategy_id);
```

### UNIQUE Index
```sql
-- PostgreSQL
CREATE UNIQUE INDEX idx_unique_email ON users(email);
OR
ALTER TABLE users ADD CONSTRAINT uq_email UNIQUE (email);

-- MariaDB (identical)
CREATE UNIQUE INDEX idx_unique_email ON users(email);
OR
ALTER TABLE users ADD CONSTRAINT uq_email UNIQUE (email);
```

---

## Constraints

### PRIMARY KEY
```sql
-- PostgreSQL
ALTER TABLE users ADD PRIMARY KEY (id);

-- MariaDB (identical)
ALTER TABLE users ADD PRIMARY KEY (id);
```

### FOREIGN KEY
```sql
-- PostgreSQL
ALTER TABLE bot_instance 
  ADD CONSTRAINT fk_bot_user 
  FOREIGN KEY (user_id) REFERENCES users(id);

-- MariaDB (identical, but requires InnoDB)
ALTER TABLE bot_instance 
  ADD CONSTRAINT fk_bot_user 
  FOREIGN KEY (user_id) REFERENCES users(id);
```

### CHECK Constraint
```sql
-- PostgreSQL
ALTER TABLE users 
  ADD CONSTRAINT chk_age CHECK (age >= 18);

-- MariaDB (added in 10.2+)
ALTER TABLE users 
  ADD CONSTRAINT chk_age CHECK (age >= 18);
```

### UNIQUE Constraint
```sql
-- PostgreSQL
ALTER TABLE users ADD CONSTRAINT uq_email UNIQUE (email);

-- MariaDB (identical)
ALTER TABLE users ADD CONSTRAINT uq_email UNIQUE (email);
```

### NOT NULL Constraint
```sql
-- PostgreSQL
ALTER TABLE users ADD CONSTRAINT users_email_not_null CHECK (email IS NOT NULL);
OR
ALTER TABLE users MODIFY COLUMN email VARCHAR(255) NOT NULL;

-- MariaDB (identical)
ALTER TABLE users MODIFY COLUMN email VARCHAR(255) NOT NULL;
```

---

## Conversion Checklist

Use this checklist when converting a PostgreSQL migration file:

- [ ] Replace `SERIAL` with `INT AUTO_INCREMENT`
- [ ] Replace `BIGSERIAL` with `BIGINT AUTO_INCREMENT`
- [ ] Replace `CREATE TYPE ... AS ENUM` with lookup table pattern
- [ ] Remove `RETURNING` clauses (will be handled in application code)
- [ ] Replace `ON CONFLICT` with `ON DUPLICATE KEY UPDATE`
- [ ] Replace PostgreSQL function calls with MariaDB equivalents
- [ ] Replace `::type` casts with MariaDB syntax
- [ ] Update TEXT columns to LONGTEXT if > 65KB
- [ ] Replace JSON operators (@>, ->, ->>>) with JSON functions
- [ ] Replace GIN indexes with FULLTEXT or B-tree alternatives
- [ ] Replace ARRAY types with JSON
- [ ] Verify DECIMAL precision handling
- [ ] Test all constraints work correctly
- [ ] Verify FOREIGN KEY constraints use correct table/column names
- [ ] Test migration: `migrate up 1` → verify schema → `migrate down 1` → verify clean

---

## Notes for Go Developers

When updating Go repository code:

1. **RETURNING queries**: Use `LAST_INSERT_ID()` + separate SELECT
   ```go
   result, _ := db.ExecContext(ctx, "INSERT INTO ...", ...)
   lastID, _ := result.LastInsertId()
   db.QueryRowContext(ctx, "SELECT ... WHERE id = ?", lastID)
   ```

2. **Error handling**: Update error code checks
   - PostgreSQL `42703` (unknown column) → MySQL `1054`
   - PostgreSQL `23505` (unique violation) → MySQL `1062`
   - PostgreSQL `40P01` (deadlock) → MySQL `1213`

3. **Connection strings**: Change from `postgresql://` to `mysql://`
   ```go
   // Old: postgresql://user:pass@localhost/dbname
   // New: mysql://user:pass@localhost/dbname
   ```

4. **Driver**: Change from `lib/pq` to `go-sql-driver/mysql`
   ```go
   import _ "github.com/go-sql-driver/mysql"
   ```

---

## Notes for Python Developers

When updating Python bot code:

1. **SQLAlchemy dialect**: Change from `postgresql` to `mysql+pymysql`
   ```python
   # Old: postgresql://user:pass@localhost/dbname
   # New: mysql+pymysql://user:pass@localhost/dbname
   ```

2. **Driver**: Change from `psycopg2` to `pymysql` or `asyncmy`
   ```python
   # requirements.txt
   # Old: psycopg2-binary==2.9.x
   # New: pymysql==1.0.x  (or asyncmy==0.0.x for async)
   ```

3. **ENUM columns**: SQLAlchemy `sa.Enum()` → `sa.String(20)` with FK
   ```python
   # Old: sa.Enum('CREATED', 'RUNNING', name='botstatusenum')
   # New: sa.String(20)  # with foreign key to lookup table
   ```

4. **Connection pooling**: Adjust QueuePool settings for MySQL
   ```python
   # The same pool parameters work, but test under load
   ```

---

## Testing Patterns

### Numeric Precision Test
```sql
-- Verify DECIMAL precision is maintained
INSERT INTO positions (entry_price) VALUES (12345.6789123456);
SELECT entry_price FROM positions WHERE id = LAST_INSERT_ID();
-- Should return 12345.67891235 (8 decimal places)
```

### ENUM Lookup Test
```sql
-- Verify enum values are properly constrained
INSERT INTO bot_instance (status) VALUES ('INVALID');  -- Should fail with FK error
INSERT INTO bot_instance (status) VALUES ('RUNNING');   -- Should succeed
```

### Transaction Isolation Test
```sql
-- Verify locks work correctly
BEGIN;
SELECT GET_LOCK('test_lock', 30);
-- From another session, try to acquire same lock (should block for 30s)
SELECT GET_LOCK('test_lock', 30);
```

---

**Last Updated**: 2026-06-06  
**Status**: Phase 1 preparation template complete
