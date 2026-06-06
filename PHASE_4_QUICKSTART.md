# Quick Start: Phase 4 Execution

**Status**: 🚀 Ready to Begin  
**Duration**: ~5-7 days  
**Priority**: HIGH (Blocking Phases 5-6)

---

## What To Do Right Now

### Step 1: Review Phase 3 (5 minutes)
```bash
# Read completion checklist
cat PHASE_3_COMPLETION_CHECKLIST.md

# Key facts:
# ✅ All 60 backend migrations converted (124 files)
# ✅ Critical bot migration converted (1/17)
# ✅ MySQL driver already in go.mod
# ✅ Backend connection already configured for MySQL
```

### Step 2: Review Phase 4 Plan (15 minutes)
```bash
# Read detailed execution plan
cat PHASE_4_EXECUTION_PLAN.md

# Key sections:
# - A. Go Code Changes (30 files)
# - B. Python Code Changes (15 files)
# - Execution Strategy (Day by day breakdown)
# - Success Criteria
```

### Step 3: Understand Current Infrastructure (10 minutes)
```bash
# Check driver status
grep "go-sql-driver" backend/go.mod
# Should show: github.com/go-sql-driver/mysql v1.8.1

# Check connection logic
grep -n "migrations/mysql" backend/internal/db/db.go
# Should show: migrations/mysql is default path

# Understand MySQL already configured
grep -A5 "func runtimeSQLDriver" backend/internal/db/db.go
```

---

## Phase 4 Task Checklist (Priority Order)

### CRITICAL (Do First - Blocks Everything)

#### Task 4.1: Update Go Driver Imports (30 min)
- [ ] Remove `github.com/lib/pq` imports from:
  - [ ] `backend/internal/repository/bot_instance_repository.go`
  - [ ] `backend/internal/repository/bot_instance_repository_test.go`
- [ ] Verify no other PostgreSQL-specific imports exist
  ```bash
  grep -r "lib/pq" backend/internal/
  grep -r "github.com/postgres" backend/
  ```

#### Task 4.2: Create MySQL Error Mapping (1 hour)
- [ ] Create new file: `backend/internal/db/error_codes.go`
- [ ] Implement PostgreSQL → MySQL error code translation
  ```go
  var postgresErrorMap = map[string]uint16{
      "42703": 1054,  // Unknown column
      "23505": 1062,  // Duplicate entry
      "40P01": 1213,  // Deadlock
      "42P07": 1050,  // Table already exists
      // ... 20+ more mappings
  }
  ```
- [ ] Update error handlers to use mapping
- [ ] Add unit tests for error translation

#### Task 4.3: Convert RETURNING Clauses (3 hours)
Start with **critical files first** (highest usage):

1. **backend/internal/repository/settings_repo.go**
   - [ ] Find all INSERT...RETURNING statements
   - [ ] Convert to two-step: INSERT, then SELECT with LAST_INSERT_ID()
   - [ ] Test with all settings operations
   
2. **backend/internal/repository/strategy_repo.go**
   - [ ] Convert RETURNING patterns
   - [ ] Test strategy CRUD operations
   
3. **backend/internal/repository/backtest_repo.go**
   - [ ] Convert RETURNING clauses
   - [ ] Handle advisory lock → GET_LOCK() conversion
   - [ ] Test backtest operations

4. **Remaining 7 repository files** (as time allows)
   - tradelog_repo.go
   - bot_trade_repository.go
   - partner_relationship_repo.go
   - invitation_token_repo.go
   - ib_tier_commission_rate_repo.go
   - role_permission_repo.go
   - user_permission_override_repo.go

**Pattern to Use**:
```go
// OLD (PostgreSQL):
const insertSQL = `
  INSERT INTO settings (key, value) VALUES ($1, $2)
  RETURNING id, created_at
`
var id int64
var createdAt time.Time
err := r.db.QueryRowContext(ctx, insertSQL, key, value).
    Scan(&id, &createdAt)

// NEW (MySQL):
const insertSQL = `
  INSERT INTO settings (key, value) VALUES (?, ?)
`
result, err := r.db.ExecContext(ctx, insertSQL, key, value)
lastID, _ := result.LastInsertId()

const selectSQL = `
  SELECT id, created_at FROM settings WHERE id = ?
`
var id int64
var createdAt time.Time
err = r.db.QueryRowContext(ctx, selectSQL, lastID).
    Scan(&id, &createdAt)
```

### HIGH (Do After Critical)

#### Task 4.4: Convert ON CONFLICT Patterns (2 hours)
- [ ] Review files with ON CONFLICT:
  ```bash
  grep -r "ON CONFLICT" backend/internal/repository/
  ```
- [ ] Convert to ON DUPLICATE KEY UPDATE pattern
  
#### Task 4.5: Fix Advisory Locks (1 hour)
- [ ] File: `backend/internal/repository/backtest_repo.go`
- [ ] Find: `pg_advisory_xact_lock()` calls
- [ ] Replace with GET_LOCK() pattern
  ```go
  // OLD: SELECT pg_advisory_xact_lock($1)
  // NEW: SELECT GET_LOCK('backtest_' || userID, 30)
  ```

#### Task 4.6: Update Python Driver (30 min)
- [ ] File: `bot/requirements.txt`
  - Remove: psycopg2-binary (or psycopg2)
  - Add: asyncmy (for async MySQL)
  
- [ ] File: `bot/src/infrastructure/database.py`
  - Update connection string: postgresql:// → mysql://
  - Verify SQLAlchemy MySQL dialect
  - Test connection

#### Task 4.7: Convert Bot Alembic Migrations (2 hours) ⏳ Optional
- [ ] Convert remaining 16 migrations
- [ ] Can defer if time-constrained
- [ ] Use same pattern as 66f08c3b1066

### MEDIUM (Do When Tasks 1-3 Done)

#### Task 4.8: Update DSN Parsing (30 min)
- [ ] File: `backend/internal/startup/db_ownership.go`
- [ ] Update PostgreSQL URL parsing
- [ ] Test with MySQL connection strings

#### Task 4.9: Update Comments & Docs (30 min)
- [ ] Search and update PostgreSQL references
  ```bash
  grep -r "PostgreSQL" backend/
  grep -r "postgres" backend/
  ```
- [ ] Update migration planning docs if needed

---

## How To Test Your Work

### Unit Testing
```bash
# From backend/ directory
go test ./internal/repository -v
go test ./internal/db -v

# Run tests against MariaDB test instance
DATABASE_URL=mysql://root:password@localhost:3306/test_db go test ./...
```

### Integration Testing
```bash
# Start test MariaDB instance (if you have Docker)
docker run --name test-mariadb -e MYSQL_ROOT_PASSWORD=test -p 3306:3306 mariadb:10.4

# Run migrations
cd backend
make migrate-up

# Run full test suite
make test
```

### Manual Verification
```bash
# Check connection works
mysql -h localhost -u root -p -D dydx_trading_bot

# Verify tables exist
SHOW TABLES;
SHOW COLUMNS FROM settings;

# Test with Go
DATABASE_URL=mysql://root:password@localhost:3306/dydx_trading_bot go run ./cmd/server/main.go
```

---

## Common Issues & Solutions

### Issue 1: "Unknown column" Errors
**Cause**: Parameter placeholder mismatch (PostgreSQL $1 vs MySQL ?)  
**Solution**: Ensure all queries use ? placeholders in MySQL  
**Test**: `grep '\$[0-9]' backend/internal/repository/*.go` (should be empty)

### Issue 2: "Duplicate entry" Handling
**Cause**: MySQL 1062 error vs PostgreSQL 23505  
**Solution**: Use error mapping layer to translate codes  
**Test**: Run duplicate key test with error mapping

### Issue 3: LAST_INSERT_ID() Returns 0
**Cause**: Query didn't actually insert a row  
**Solution**: Verify WHERE clause, check foreign keys  
**Test**: Print result.RowsAffected() before calling LastInsertId()

### Issue 4: Lock Timeout
**Cause**: GET_LOCK() timeout too short (30 sec default)  
**Solution**: Increase timeout or investigate slow transactions  
**Test**: Check transaction duration, increase timeout if needed

---

## Success Checklist for Phase 4

- [ ] Go driver imports cleaned (no lib/pq)
- [ ] MySQL error mapping created and tested
- [ ] All RETURNING clauses converted (or majority)
- [ ] All ON CONFLICT patterns converted (or majority)
- [ ] Advisory locks converted to GET_LOCK()
- [ ] Python driver updated to asyncmy
- [ ] Database.py updated for MySQL connection
- [ ] Unit tests passing with MySQL
- [ ] No compilation errors
- [ ] No PostgreSQL-specific code in critical paths

**Total Expected Time**: 5-7 days working part-time

---

## What To Do When Done with Phase 4

1. ✅ Complete Phase 4 → Proceed to Phase 5
2. **Phase 5**: Testing & Validation
   - Unit test migrations
   - Integration tests
   - Smoke tests for end-to-end workflow
   
3. **Phase 6**: Infrastructure & Deployment
   - Create MariaDB production instance
   - Deploy migrations
   - Switch connection strings
   - Monitor for errors

---

## Key Reference Files

| File                               | Purpose                | Use When             |
| ---------------------------------- | ---------------------- | -------------------- |
| PHASE_4_EXECUTION_PLAN.md          | Detailed breakdown     | Planning day's work  |
| MARIADB_CONVERSION_TEMPLATES.md    | SQL pattern examples   | Converting queries   |
| MIGRATION_STATUS_REPORT.md         | Current infrastructure | Understanding setup  |
| backend/migrations/mysql/README.md | Migration details      | Deploying migrations |

---

## Questions?

Refer to:
- `PHASE_4_EXECUTION_PLAN.md` → Section "A. Go Code Changes"
- `MARIADB_CONVERSION_TEMPLATES.md` → Pattern reference
- `SESSION_SUMMARY.md` → What's been done so far

---

**Ready?** Start with Task 4.1 (30 min) - Remove lib/pq imports  
**Then** Task 4.2 (1 hour) - Create error mapping  
**Then** Task 4.3 (3 hours) - Convert RETURNING clauses

**Total Day 1**: ~4.5 hours to complete critical tasks 1-3

---

**Good luck! 🚀**

