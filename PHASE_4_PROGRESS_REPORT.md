# Phase 4 Progress Report — Code Changes (In Progress)

**Status**: 🚀 **IN PROGRESS**  
**Date Started**: 2026-06-06  
**Estimated Duration**: 5-7 days  

---

## ✅ What's Been Completed

### 1. MySQL Error Code Mapping ✅
**File**: `backend/internal/db/error_codes.go` (NEW)

- ✅ Created comprehensive error code translation system
- ✅ Mapped 25+ PostgreSQL error codes to MySQL equivalents
  - 42703 → 1054 (Unknown column)
  - 23505 → 1062 (Duplicate entry)
  - 40P01 → 1213 (Deadlock)
  - 42P07 → 1050 (Table already exists)
  - 23502 → 1048 (Column cannot be null)
  - Plus 20+ more critical codes
- ✅ Implemented helper functions:
  - `IsDuplicateKeyError()` — Check for duplicate key errors
  - `IsDeadlockError()` — Check for deadlock errors
  - `IsUndefinedColumnError()` — Check for undefined column errors
  - `IsConstraintViolationError()` — Check for constraint violations
  - `WrapSQLError()` — Standardize error handling

### 2. PostgreSQL Driver Removal ✅
**Files Modified**:
- ✅ `backend/internal/repository/bot_instance_repository.go`
  - Removed: `"github.com/lib/pq"` import
  - Updated: `isUndefinedColumnError()` to use `db.IsUndefinedColumnError()`
  
- ✅ `backend/internal/repository/bot_instance_repository_test.go`
  - Removed: `"github.com/lib/pq"` import
  - Converted: Error test cases from `pq.Error{Code: "42703"}` to MySQL error format `fmt.Errorf("Error 1054: Unknown column in field list")`

### 3. RETURNING Clause Conversions ✅ (Partial)
**Completed**:
- ✅ `backend/internal/repository/settings_repo.go`
  - ✅ `CreateBotSetting()`: Converted INSERT...RETURNING to INSERT + LAST_INSERT_ID()
  - ✅ `CreateRedisSetting()`: Converted INSERT...RETURNING to INSERT + LAST_INSERT_ID()
  - Pattern: Use `result.LastInsertId()` to get ID, set timestamps in application code

**Remaining** (13 files, ~18 RETURNING clauses):
- [ ] `auditlog_repo.go` — 1-2 RETURNING clauses
- [ ] `bot_instance_repository.go` — 2-3 RETURNING clauses
- [ ] `bot_position_repository.go` — 1-2 RETURNING clauses
- [ ] `bot_trade_repository.go` — 2-3 RETURNING clauses (HIGH PRIORITY)
- [ ] `ib_tier_commission_rate_repo.go` — 1-2 RETURNING clauses
- [ ] `invitation_token_repo.go` — 1-2 RETURNING clauses
- [ ] `key_repo.go` — 2-3 RETURNING clauses
- [ ] `partner_application_repo.go` — 1-2 RETURNING clauses
- [ ] `partner_commission_metric_repo.go` — 1-2 RETURNING clauses
- [ ] `partner_relationship_repo.go` — 2-3 RETURNING clauses (HIGH PRIORITY)
- [ ] `strategy_repo.go` — 2-3 RETURNING clauses (HIGH PRIORITY)
- [ ] `tradelog_repo.go` — 1-2 RETURNING clauses (HIGH PRIORITY)
- [ ] `user_mfa_repo.go` — 1-2 RETURNING clauses
- [ ] `user_repo.go` — 1-2 RETURNING clauses

---

## 🚀 What's Next (Priority Order)

### CRITICAL (Day 1-2)
1. **Complete RETURNING Clause Conversions** (3 high-priority files)
   - [ ] `strategy_repo.go` — Strategy CRUD operations
   - [ ] `bot_trade_repository.go` — Trading operations
   - [ ] `tradelog_repo.go` — Trade logging
   
2. **Convert ON CONFLICT Patterns** (2-3 files)
   - [ ] Search all repository files for `ON CONFLICT` patterns
   - [ ] Convert to `ON DUPLICATE KEY UPDATE` syntax
   
3. **Update Parameter Placeholders** (All repository files)
   - [ ] Change `$1, $2, $3...` to `?, ?, ?...` for all SQL queries
   - [ ] This is required for MySQL/go-sql-driver compatibility

### HIGH PRIORITY (Day 2-3)
4. **Replace Advisory Locks** (1-2 files)
   - [ ] `backtest_repo.go` — Replace `pg_advisory_xact_lock()` with `GET_LOCK()`
   - [ ] Review lock acquisition/release patterns
   
5. **Complete Remaining RETURNING Conversions** (11 files)
   - Follow the same pattern used in `settings_repo.go`

### MEDIUM PRIORITY (Day 3-4)
6. **Update Query Placeholders Systematically**
   - [ ] Run global find/replace for PostgreSQL placeholders
   - [ ] Verify all `$N` are replaced with `?`
   
7. **Python Code Updates** (bot service)
   - [ ] Update Alembic migration driver configuration
   - [ ] Update asyncmy connection string format
   - [ ] Review and convert Alembic migration patterns

---

## 📋 Conversion Patterns Reference

### Pattern 1: Simple INSERT with RETURNING
```go
// BEFORE (PostgreSQL)
const insertSQL = `
  INSERT INTO users (name, email) VALUES ($1, $2)
  RETURNING id, created_at
`
var id int64
var createdAt time.Time
err := r.db.QueryRow(insertSQL, name, email).Scan(&id, &createdAt)

// AFTER (MySQL)
const insertSQL = `
  INSERT INTO users (name, email) VALUES (?, ?)
`
result, err := r.db.Exec(insertSQL, name, email)
if err != nil { return err }

lastID, err := result.LastInsertId()
if err != nil { return err }

createdAt := time.Now()
id := lastID
```

### Pattern 2: UPDATE with RETURNING
```go
// BEFORE (PostgreSQL)
const updateSQL = `
  UPDATE users SET name = $1, updated_at = $2 WHERE id = $3
  RETURNING id, name, updated_at
`
err := r.db.QueryRow(updateSQL, newName, now, userID).Scan(&id, &name, &updatedAt)

// AFTER (MySQL)
const updateSQL = `
  UPDATE users SET name = ?, updated_at = ? WHERE id = ?
`
_, err := r.db.Exec(updateSQL, newName, now, userID)
if err != nil { return err }

// Query back if needed
const selectSQL = `SELECT id, name, updated_at FROM users WHERE id = ?`
err = r.db.QueryRow(selectSQL, userID).Scan(&id, &name, &updatedAt)
```

### Pattern 3: Parameter Placeholders
```go
// Change from:
query := `WHERE user_id = $1 AND status = $2`

// To:
query := `WHERE user_id = ? AND status = ?`
```

---

## 📊 Progress Metrics

| Task                   | Status        | Files    | RETURNING | Notes                    |
| ---------------------- | ------------- | -------- | --------- | ------------------------ |
| Error mapping          | ✅ Complete    | 1        | N/A       | error_codes.go created   |
| Driver removal         | ✅ Complete    | 2        | N/A       | lib/pq imports removed   |
| RETURNING conversion   | 🚀 In Progress | 14 total | 20 total  | 2 complete, 18 remaining |
| ON CONFLICT conversion | ⏳ Not Started | TBD      | TBD       | Search needed            |
| Parameter placeholders | ⏳ Not Started | 30+      | N/A       | Global find/replace      |
| Advisory locks         | ⏳ Not Started | 1-2      | N/A       | backtest_repo.go         |
| Python updates         | ⏳ Not Started | 5+       | N/A       | bot service changes      |

---

## 🔧 How to Continue Phase 4

### Quick Start for Next Developer
```bash
# 1. Start with bot_trade_repository.go (high priority)
grep -n "RETURNING" backend/internal/repository/bot_trade_repository.go

# 2. Follow the pattern from settings_repo.go:
#    - Change INSERT...RETURNING to INSERT + Exec + LastInsertId
#    - Change UPDATE...RETURNING to UPDATE + Exec + SELECT
#    - Change parameter placeholders $1 → ?

# 3. Test each file:
go test ./backend/internal/repository/...

# 4. Commit when done
git add backend/internal/repository/bot_trade_repository.go
git commit -m "Phase 4: Convert RETURNING clauses in bot_trade_repository"
```

### Testing Each Change
```bash
# Run repository tests
cd backend/
go test -run TestBotTrade ./internal/repository/... -v

# Run full test suite
go test ./...

# Check for MySQL compatibility
grep -r "\$[0-9]" backend/internal/repository/ | grep -v "test" | wc -l
# Should return 0 when complete
```

---

## ⚠️ Known Issues & Considerations

### 1. Timestamp Handling
When converting RETURNING with timestamp fields:
- ✅ Can use application-set timestamps if we control the NOW() value
- ⚠️ If database calculates timestamps, need separate SELECT query
- Solution: Use `time.Now()` in application and set in query

### 2. LAST_INSERT_ID() Scope
- ✅ Valid for single-connection operations
- ⚠️ May lose ID in concurrent scenarios
- Solution: Use transactions and ensure ID retrieval within same connection

### 3. ON CONFLICT vs ON DUPLICATE KEY UPDATE
- PostgreSQL: `INSERT ... ON CONFLICT (col) DO UPDATE SET ...`
- MySQL: `INSERT ... ON DUPLICATE KEY UPDATE col = VALUES(col)`
- **ACTION**: Search repository files for `ON CONFLICT` pattern

---

## 📝 Next Milestone

**Target**: Complete all RETURNING conversions + ON CONFLICT conversions by end of Day 2  
**Success Criteria**:
- ✅ All 20 RETURNING clauses converted
- ✅ All ON CONFLICT patterns converted
- ✅ Parameter placeholders updated
- ✅ Unit tests passing
- ✅ Error handling verified

---

## 🎯 Session Summary

**Phase 4 Progress**: 20% complete  
- ✅ Error handling system ready
- ✅ Driver removal started
- ✅ RETURNING pattern established
- 🚀 Ready for high-velocity conversion of remaining files

**Effort Used**: ~2 hours  
**Effort Remaining**: ~3-5 days for full Phase 4 + Phase 5 testing

---

**Status**: 🚀 READY TO CONTINUE  
**Last Updated**: 2026-06-06 20:30 UTC
