# Phase 4 Execution Plan — Update Code Patterns (Go & Python)

**Status**: 🚀 **STARTING PHASE 4**  
**Estimated Duration**: 5 days  
**Goal**: Update all repository code to use MariaDB instead of PostgreSQL  

---

## Phase 4 Scope

### A. Go Code Changes (backend/) — ~30 files
#### 1. Driver & Connection Layer (CRITICAL)
- [ ] Update `go.mod`: Replace `lib/pq` with `go-sql-driver/mysql`
- [ ] Update `backend/internal/db/db.go`:
  - [ ] Change PostgreSQL driver import
  - [ ] Update DSN format (postgresql:// → mysql://)
  - [ ] Update migration path logic (migrations/postgres → migrations/mysql)
  - [ ] Update schema validation if exists

#### 2. RETURNING Clause Conversions (25+ occurrences across 10+ files)

**Critical Files**:
- [ ] `backend/internal/repository/settings_repo.go` — INSERT RETURNING → LAST_INSERT_ID()
- [ ] `backend/internal/repository/strategy_repo.go`
- [ ] `backend/internal/repository/tradelog_repo.go`
- [ ] `backend/internal/repository/bot_trade_repository.go`
- [ ] `backend/internal/repository/partner_relationship_repo.go`
- [ ] `backend/internal/repository/invitation_token_repo.go`
- [ ] `backend/internal/repository/ib_tier_commission_rate_repo.go`
- [ ] `backend/internal/repository/role_permission_repo.go`
- [ ] `backend/internal/repository/user_permission_override_repo.go`

**Pattern**:
```go
// PostgreSQL (RETURNING)
const insertSQL = `
  INSERT INTO settings (key, value) VALUES ($1, $2)
  RETURNING id, created_at
`
var id int
var createdAt time.Time
err := r.db.QueryRowContext(ctx, insertSQL, key, value).Scan(&id, &createdAt)

// MySQL/MariaDB (two-step)
const insertSQL = `
  INSERT INTO settings (key, value) VALUES (?, ?)
`
result, err := r.db.ExecContext(ctx, insertSQL, key, value)
lastID, _ := result.LastInsertId()

const selectSQL = `
  SELECT id, created_at FROM settings WHERE id = ?
`
var id int
var createdAt time.Time
err = r.db.QueryRowContext(ctx, selectSQL, lastID).Scan(&id, &createdAt)
```

#### 3. ON CONFLICT Conversions (10+ files)

**Files**:
- [ ] `backend/internal/repository/settings_repo.go`
- [ ] `backend/internal/repository/partner_relationship_repo.go`
- [ ] `backend/internal/repository/role_permission_repo.go`
- [ ] Various seed/bulk operation repositories

**Pattern**:
```go
// PostgreSQL
const upsertSQL = `
  INSERT INTO settings (key, value) VALUES ($1, $2)
  ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
  RETURNING id
`

// MySQL/MariaDB
const upsertSQL = `
  INSERT INTO settings (key, value) VALUES (?, ?)
  ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = NOW()
`
// Note: LastInsertId() returns the updated row ID in MySQL
```

#### 4. Advisory Lock Replacement (backtest_repo.go)

**File**: `backend/internal/repository/backtest_repo.go`

**Pattern**:
```go
// PostgreSQL
func (r *BacktestRepository) withLock(ctx context.Context, userID int64, fn func() error) error {
    const lockSQL = `SELECT pg_advisory_xact_lock($1)`
    _, err := r.db.ExecContext(ctx, lockSQL, userID)
    if err != nil {
        return err
    }
    return fn()  // Lock released on transaction end
}

// MySQL/MariaDB
func (r *BacktestRepository) withLock(ctx context.Context, userID int64, fn func() error) error {
    lockName := fmt.Sprintf("backtest_%d", userID)
    const lockSQL = `SELECT GET_LOCK(?, 30)`  // 30 second timeout
    
    var acquired int
    err := r.db.QueryRowContext(ctx, lockSQL, lockName).Scan(&acquired)
    if err != nil || acquired != 1 {
        return fmt.Errorf("failed to acquire lock: %w", err)
    }
    
    defer func() {
        // Must explicitly release
        r.db.ExecContext(ctx, `SELECT RELEASE_LOCK(?)`, lockName)
    }()
    
    return fn()
}
```

#### 5. Error Code Mapping (50+ assertions in tests + handlers)

**Files**:
- [ ] `backend/internal/handlers/` (all handlers)
- [ ] `backend/internal/repository/` (all repos)
- [ ] `backend/internal/services/` (all services)

**Mapping Required**:
```go
// PostgreSQL → MySQL Error Codes
PostgreSQL 42703 → MySQL 1054  (Unknown column)
PostgreSQL 23505 → MySQL 1062  (Duplicate entry)
PostgreSQL 40P01 → MySQL 1213  (Deadlock)
PostgreSQL 42P07 → MySQL 1050  (Table already exists)
PostgreSQL 42P01 → MySQL 1146  (Table doesn't exist)
PostgreSQL 23502 → MySQL 1048  (NOT NULL violation)
PostgreSQL 23514 → MySQL 3819  (CHECK constraint violation)
PostgreSQL 23503 → MySQL 1452  (Foreign key constraint)
```

**Implementation**:
```go
// Create error mapping in new file: backend/internal/db/errors.go
var postgresErrorMap = map[string]uint16{
    "42703": 1054,  // Unknown column
    "23505": 1062,  // Duplicate entry
    // ... map more codes
}

func TranslatePgErrorCode(pgCode string) uint16 {
    if mysqlCode, exists := postgresErrorMap[pgCode]; exists {
        return mysqlCode
    }
    return 0
}

// Use in error handling:
var mysqlErr *mysql.MySQLError
if errors.As(err, &mysqlErr) {
    switch mysqlErr.Number {
    case 1054:  // Unknown column
        return handleUnknownColumn()
    case 1062:  // Duplicate
        return handleDuplicate()
    // ...
    }
}
```

#### 6. Query Parameter Updates
- [ ] All `$1, $2, $3...` → `?, ?, ?...` (positional to named parameters)
- [ ] Check for any raw SQL queries using PostgreSQL functions
- [ ] Update any CAST() usage that differs between DBs

---

### B. Python Code Changes (bot/) — ~15 files

#### 1. Driver & Connection Layer
- [ ] Update `bot/requirements.txt`:
  - [ ] Remove `psycopg2` or `psycopg2-binary`
  - [ ] Add `asyncmy` or `PyMySQL` (async support needed)
  - [ ] Verify `SQLAlchemy>=2.0` (has MySQL/MariaDB dialect)
  
- [ ] Update `bot/src/infrastructure/database.py`:
  - [ ] Change connection string format (postgresql://... → mysql://...)
  - [ ] Update dialect registration if needed
  - [ ] Handle asyncmy vs psycopg2 differences
  
- [ ] Update `bot/config/config.py`:
  - [ ] Update DATABASE_URL parsing for MySQL format
  - [ ] Update default port if needed (5432 → 3306)

#### 2. SQLAlchemy Type Conversions
- [ ] Verify all column types work with MySQL dialect
  - [ ] ENUM types (need to check how SQLAlchemy handles these)
  - [ ] JSON columns (should work)
  - [ ] Numeric precision (DECIMAL vs FLOAT)
  
- [ ] Check for any PostgreSQL-specific SQL expressions
  - [ ] String concatenation operators
  - [ ] Array operations (if any)
  - [ ] JSON operations (need to use MySQL-compatible functions)

#### 3. Query Pattern Updates
- [ ] No RETURNING clauses in bot code (Alembic handles that)
- [ ] Check for any raw SQL using PostgreSQL functions
- [ ] Update transaction handling if needed

#### 4. Async Driver Configuration
- [ ] Verify asyncmy connection pooling settings
- [ ] Test transaction isolation levels
- [ ] Ensure proper timeout handling

---

## Execution Strategy

### Phase 4A: Backend (Go) — Days 1-2
1. **Day 1**: Driver layer + error mapping setup
   - Update go.mod and db.go
   - Create error code mapping
   - Test basic connection
   
2. **Day 2**: Repository RETURNING conversions
   - Batch convert RETURNING queries (10+ files)
   - Convert ON CONFLICT patterns
   - Update advisory lock logic

### Phase 4B: Backend (Continued) — Days 2-3
3. **Day 2-3**: Testing and validation
   - Run unit tests against MariaDB
   - Fix any SQL dialect issues
   - Validate error handling

### Phase 4C: Bot (Python) — Days 3-4
4. **Day 3**: Driver layer + Alembic config
   - Update requirements.txt
   - Update database.py
   - Verify asyncmy setup
   
5. **Day 4**: Test and integrate
   - Smoke tests with MariaDB
   - Integration tests

### Phase 4D: Final validation — Day 5
6. **Day 5**: Cross-service validation
   - Backend ↔ Bot integration tests
   - End-to-end workflow tests
   - Documentation updates

---

## Key Files to Modify (Priority Order)

### CRITICAL (Do First)
1. `backend/internal/db/db.go` — Connection initialization
2. `go.mod` — Driver dependency
3. `bot/requirements.txt` — Python driver
4. `bot/src/infrastructure/database.py` — Connection setup
5. `backend/internal/db/errors.go` — Error mapping (new file)

### HIGH (Do Second)
6. `backend/internal/repository/settings_repo.go`
7. `backend/internal/repository/backtest_repo.go`
8. `backend/internal/repository/strategy_repo.go`

### MEDIUM (Do Third)
9. All other repository files with RETURNING/ON CONFLICT
10. Handler error handling

### LOW (Do Last)
11. Service layer updates
12. Test file adjustments

---

## Estimated Effort

| Component            | Files  | LOC Changes | Estimated Time |
| -------------------- | ------ | ----------- | -------------- |
| Go driver layer      | 2      | 50-100      | 30 min         |
| Error mapping        | 1      | 100-150     | 1 hour         |
| RETURNING queries    | 10     | 200-300     | 3 hours        |
| ON CONFLICT queries  | 5      | 100-150     | 2 hours        |
| Advisory locks       | 1      | 50-100      | 1 hour         |
| Python driver layer  | 3      | 30-50       | 30 min         |
| Testing & validation | -      | -           | 8 hours        |
| **TOTAL**            | **22** | **530-850** | **~16 hours**  |

---

## Success Criteria

- ✅ All Go code compiles with mysql driver
- ✅ All Python code runs with asyncmy/MySQL
- ✅ Unit tests pass for all modified repositories
- ✅ Integration tests pass (backend + bot)
- ✅ Error handling works correctly for MySQL error codes
- ✅ No deadlocks or timeout issues
- ✅ Financial precision maintained (18,8 decimals)

---

## Rollback Plan

If MariaDB integration reveals critical issues:
1. Revert code to PostgreSQL
2. Keep MySQL migrations in separate branch
3. Re-attempt after deeper analysis

Actual rollback (day of deployment):
1. Maintain PostgreSQL instance alongside MariaDB
2. Keep both sets of migrations available
3. Build dual-DB support as needed

---

## Next Steps

1. ✅ Complete Phase 3 (migrations) — DONE
2. 🚀 **START PHASE 4A** — Backend driver layer
   - Modify go.mod and db.go
   - Create error mapping
3. Continue with repository conversions
4. Move to Phase 5 (testing) and Phase 6 (deployment)

---

