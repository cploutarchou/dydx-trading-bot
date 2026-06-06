# PostgreSQL → MariaDB Migration Plan

**Reason**: Team expertise with MariaDB  
**Scope**: Full monorepo refactor (bot/, backend/, infrastructure)  
**Estimated Effort**: 25-40 days  
**Risk Level**: HIGH (trading bot with state persistence)  
**Status**: Planning Phase

---

## 📋 Executive Summary

This is a **cross-service architectural migration** affecting:
- **Python Bot Layer** (`bot/`): SQLAlchemy ORM + Alembic migrations
- **Go Backend Layer** (`backend/`): Raw SQL queries + migration files
- **Infrastructure**: Docker Compose, environment variables, health checks
- **Production**: Database state, backtest data, trading positions

**Critical constraints:**
- Must maintain financial precision (18-8 decimal accuracy)
- Zero-downtime migration for live trading (if applicable)
- Backtest data integrity (historical results preservation)
- Audit trail (transaction logs, order fills)

---

## 🔴 CRITICAL ISSUES (Must Address)

### 1. **PostgreSQL ENUM Types** (3 critical)
**Current**: Uses PostgreSQL native ENUM types
```sql
CREATE TYPE botstatusenum AS ENUM ('CREATED', 'STARTING', 'RUNNING', 'STOPPED', 'ERROR');
CREATE TYPE jobstatusenum AS ENUM ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED');
CREATE TYPE tradestatusenum AS ENUM ('PENDING', 'OPENED', 'CLOSED');
```

**Problem**: MariaDB has no native ENUM type support

**Solution**: Convert to VARCHAR + CHECK constraints + application-level validation
```sql
CREATE TABLE bot_status_enum (
  value VARCHAR(20) PRIMARY KEY,
  description VARCHAR(255)
);
INSERT INTO bot_status_enum VALUES ('CREATED', 'Bot created'), ('RUNNING', 'Bot running'), ...;

ALTER TABLE bot_instance 
  ADD CONSTRAINT fk_bot_status FOREIGN KEY (status) REFERENCES bot_status_enum(value);
```

**Affected Files**:
- [bot/migrations/versions/66f08c3b1066_initial_database_schema.py](../../bot/migrations/versions/66f08c3b1066_initial_database_schema.py)
- [backend/migrations/postgres/000001_initial_schema.up.sql](../../backend/migrations/postgres/000001_initial_schema.up.sql)

**Effort**: 2-3 days

---

### 2. **RETURNING Clauses** (25+ insert/update queries)
**Current**: PostgreSQL-specific syntax
```go
INSERT INTO bot_settings (name, value) VALUES ($1, $2) RETURNING id, created_at, updated_at
```

**Problem**: MariaDB doesn't support RETURNING

**Solution**: Use `LAST_INSERT_ID()` + separate SELECT, or use `ON DUPLICATE KEY UPDATE`
```go
INSERT INTO bot_settings (name, value) VALUES (?, ?)
SELECT id, created_at, updated_at FROM bot_settings WHERE id = LAST_INSERT_ID()
```

**Affected Files**:
- [backend/internal/repository/settings_repo.go](../../backend/internal/repository/settings_repo.go)
- [backend/internal/repository/strategy_repo.go](../../backend/internal/repository/strategy_repo.go)
- [backend/internal/repository/tradelog_repo.go](../../backend/internal/repository/tradelog_repo.go)
- [backend/internal/repository/bot_trade_repository.go](../../backend/internal/repository/bot_trade_repository.go)
- [backend/internal/repository/partner_relationship_repo.go](../../backend/internal/repository/partner_relationship_repo.go)

**Effort**: 3-4 days

---

### 3. **ON CONFLICT (Upsert) Syntax** (10+ migrations)
**Current**: PostgreSQL-specific
```sql
INSERT INTO partner_relationships (user_id, status) VALUES ($1, $2)
ON CONFLICT (partner_user_id) DO UPDATE SET updated_at = NOW() RETURNING id
```

**Problem**: MariaDB uses completely different syntax

**Solution**: Convert to `ON DUPLICATE KEY UPDATE`
```sql
INSERT INTO partner_relationships (partner_user_id, status) VALUES (?, ?)
ON DUPLICATE KEY UPDATE updated_at = NOW()
```

**Affected Files**:
- [backend/migrations/postgres/000037_create_rbac_permissions.up.sql](../../backend/migrations/postgres/000037_create_rbac_permissions.up.sql)
- [backend/migrations/postgres/000043_seed_portal_bulk_dataset.up.sql](../../backend/migrations/postgres/000043_seed_portal_bulk_dataset.up.sql)
- [backend/migrations/postgres/000005_create_bot_settings.up.sql](../../backend/migrations/postgres/000005_create_bot_settings.up.sql)

**Effort**: 2-3 days

---

### 4. **PostgreSQL Advisory Locks** (Concurrency control)
**Current**: Uses PostgreSQL `pg_advisory_xact_lock()` for backtest admission control
```go
func (r *BacktestRepository) withPostgresAdvisoryAdmissionLock(ctx context.Context, userID int, fn func() error) error {
    query := `SELECT pg_advisory_xact_lock($1)`
    _, err := r.db.ExecContext(ctx, query, userID)
}
```

**Problem**: MariaDB has no equivalent advisory lock mechanism

**Solution**: Use `GET_LOCK()` / `RELEASE_LOCK()` with careful timeout handling
```go
SELECT GET_LOCK(?, 30)  // 30 second timeout
// ... do work ...
SELECT RELEASE_LOCK(?)
```

**Affected Files**:
- [backend/internal/repository/backtest_repo.go](../../backend/internal/repository/backtest_repo.go)

**Effort**: 1-2 days

---

### 5. **Database Driver Dependencies**
**Current**:
- Bot: `psycopg2` (PostgreSQL Python driver)
- Backend: `lib/pq` (PostgreSQL Go driver)

**Changes**:
- Bot: Replace with `PyMySQL` or `asyncmy` (async MySQL driver)
- Backend: Replace with `go-sql-driver/mysql`

**Affected Files**:
- [bot/requirements.txt](../../bot/requirements.txt)
- [bot/src/infrastructure/database.py](../../bot/src/infrastructure/database.py)
- [backend/go.mod](../../backend/go.mod)
- [backend/internal/db/db.go](../../backend/internal/db/db.go)

**Effort**: 2-3 days

---

### 6. **Hardcoded Database Type Validation**
**Current**: Code explicitly rejects non-PostgreSQL databases

**Bot**:
```python
if raw_db_type not in {"postgres", "postgresql"}:
    raise ValueError("Only PostgreSQL is supported.")
```
[bot/src/infrastructure/database.py](../../bot/src/infrastructure/database.py)

**Backend**:
```go
if d != "postgresql" && d != "postgres" {
    return fmt.Errorf("unsupported database type")
}
cfg.MigrationsPath = "migrations/postgres"
```
[backend/internal/db/db.go](../../backend/internal/db/db.go)

**Solution**: Remove database type checks, support `mysql` / `mariadb` dialect

**Effort**: 1 day

---

## 🟠 HIGH PRIORITY ISSUES

### 1. **Financial Precision: Numeric(18,8)** (50+ columns)
All prices, sizes, and PnL values use arbitrary-precision decimals:
```python
sa.Column("entry_price1", sa.Numeric(18, 8), nullable=False),
sa.Column("unrealized_pnl", sa.Numeric(18, 8), nullable=False),
sa.Column("z_score_entry", sa.Numeric(8, 4), nullable=True),
```

**Solution**: MariaDB `DECIMAL(18,8)` is compatible, but test precision handling in queries

**Affected Tables**:
- `live_position` (10+ numeric columns)
- `bot_realtime_stats` (15+ numeric columns)
- `position_snapshot` (8+ numeric columns)

**Effort**: 1-2 days (testing)

---

### 2. **JSONB Columns with GIN Indexes** (5+ columns)
**Current**: PostgreSQL JSONB with GIN indexes
```sql
ADD COLUMN selected_markets JSONB NOT NULL DEFAULT '[]'::jsonb;
CREATE INDEX idx_strategy_selected_markets_gin ON backtest_strategies USING gin (selected_markets);
```

**Problem**: GIN is PostgreSQL-specific; MariaDB uses FULLTEXT

**Solution**: Convert GIN to FULLTEXT index (different query syntax required)
```sql
ALTER TABLE backtest_strategies ADD FULLTEXT INDEX idx_selected_markets_ft (selected_markets);
```

**Note**: Query performance may differ; requires testing

**Affected Files**:
- [backend/migrations/postgres/000045_add_selected_markets_to_backtest_strategies.up.sql](../../backend/migrations/postgres/000045_add_selected_markets_to_backtest_strategies.up.sql)

**Effort**: 2-3 days

---

### 3. **Connection Pooling** (SQLAlchemy QueuePool)
**Current**:
```python
"poolclass": QueuePool,
pool_size = 30,
max_overflow = 60,
pool_recycle = 3600
```

**Solution**: Configure for MySQL/MariaDB driver (may require adjustments for connection timeout)

**Effort**: 1-2 days (load testing)

---

### 4. **Migration Files** (60 backend + 17 bot)
**Backend**: 60 PostgreSQL-specific SQL migration files in [backend/migrations/postgres/](../../backend/migrations/postgres/)

**Bot**: 17 Alembic migration files in [bot/migrations/versions/](../../bot/migrations/versions/)

**Task**: Convert all migrations to MariaDB dialect

**Effort**: 6-8 days

---

## 🟡 MEDIUM PRIORITY ISSUES

### 1. **SERIAL & BIGSERIAL Primary Keys**
**Current**:
```sql
id SERIAL PRIMARY KEY,          -- auto-increment
id BIGSERIAL PRIMARY KEY,       -- big auto-increment
```

**MariaDB Equivalent**:
```sql
id INT AUTO_INCREMENT PRIMARY KEY,
id BIGINT AUTO_INCREMENT PRIMARY KEY,
```

**Distribution**: 20+ SERIAL, 6-8 BIGSERIAL tables

**Effort**: Already included in migration rewrites

---

### 2. **PostgreSQL Error Codes in Tests** (50+ references)
**Current**:
```go
err: &pq.Error{Code: "42703"},  // PostgreSQL column doesn't exist
```

**MariaDB Equivalents**:
- `42703` (unknown column) → `1054`
- `23505` (unique violation) → `1062`
- `40P01` (deadlock) → `1213`

**Affected Files**:
- [backend/internal/repository/bot_instance_repository_test.go](../../backend/internal/repository/bot_instance_repository_test.go)
- Other `*_test.go` files

**Effort**: 1-2 days

---

### 3. **Docker Image & Healthcheck**
**Current**: `postgres:16` with `pg_isready`
```yaml
image: postgres:16
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${APP_DB_USER} -d ${APP_DB_NAME}"]
```

**Replacement**: `mariadb:11.4` with `mysqladmin`
```yaml
image: mariadb:11.4
healthcheck:
  test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-u", "root", "-p${MYSQL_ROOT_PASSWORD}"]
```

**Affected Files**:
- [stackforge-deployment.yaml](../../stackforge-deployment.yaml)
- Docker Compose files

**Effort**: 1 day

---

## 📅 PHASE-BY-PHASE ROADMAP

### **Phase 1: Preparation (Week 1)**
**Goal**: Create MariaDB migration infrastructure

- [ ] Create `backend/migrations/mysql/` directory structure
- [ ] Create `bot/migrations/mariadb/` directory structure
- [ ] Copy all PostgreSQL migrations as templates
- [ ] Create ENUM lookup tables for `botstatusenum`, `jobstatusenum`, `tradestatusenum`
- [ ] Document all RETURNING → LAST_INSERT_ID() conversions needed
- [ ] Document all ON CONFLICT → ON DUPLICATE KEY UPDATE conversions

**Deliverables**:
- Empty MySQL migration directories with version templates
- ENUM conversion SQL scripts
- Conversion checklist (100+ items)

---

### **Phase 2: Driver & Connection Layer (Week 1-2)**
**Goal**: Replace database drivers, update connection logic

- [ ] Update [bot/requirements.txt](../../bot/requirements.txt): Replace `psycopg2` with `asyncmy` or `PyMySQL`
- [ ] Update [backend/go.mod](../../backend/go.mod): Replace `lib/pq` with `go-sql-driver/mysql`
- [ ] Update [bot/src/infrastructure/database.py](../../bot/src/infrastructure/database.py): MySQL connection string, dialect validation
- [ ] Update [backend/internal/db/db.go](../../backend/internal/db/db.go): MySQL driver initialization, migration path
- [ ] Test basic connection with MariaDB test instance
- [ ] Update error handling for MySQL error codes

**Deliverables**:
- Working connection to test MariaDB instance
- Error code mapping table
- Updated dependency files

---

### **Phase 3: Migration Rewrites (Week 2-3)**
**Goal**: Convert all PostgreSQL migrations to MariaDB syntax

**Backend Migrations** (Priority order):
1. `000001_initial_schema.up.sql` (base tables, SERIAL → AUTO_INCREMENT)
2. `000005_create_bot_settings.up.sql` (ON CONFLICT → ON DUPLICATE KEY)
3. `000037_create_rbac_permissions.up.sql` (ON CONFLICT upserts)
4. `000043_seed_portal_bulk_dataset.up.sql` (bulk insert upserts)
5. `000045_add_selected_markets_to_backtest_strategies.up.sql` (JSONB → JSON)
6. `000051_phase1_missing_indexes.up.sql` (GIN → FULLTEXT)
7. Remaining 54 files (RETURNING clauses, type casts)

**Bot Migrations** (Alembic):
1. `66f08c3b1066_initial_database_schema.py` (ENUM types)
2. `64bafb411810_add_real_time_data_tables.py` (Numeric precision)
3. `c9f4a7b2d1e3_harden_runtime_jobs.py` (ALTER TYPE)
4. Remaining 14 files

**Tasks**:
- [ ] Rewrite 60 backend SQL migrations for MariaDB dialect
- [ ] Rewrite 17 bot Alembic migration files
- [ ] Test each migration independently: `migrate up 1`, verify schema, `migrate down`
- [ ] Validate numeric precision preserved
- [ ] Validate ENUM lookup data inserted

**Deliverables**:
- All 60 backend migrations converted & tested
- All 17 bot migrations converted & tested
- Migration test suite (verify schema matches expected output)

---

### **Phase 4: Code Changes (Week 3-4)**
**Goal**: Update application code for MariaDB-specific patterns

**Backend Changes**:
- [ ] Convert 25+ RETURNING clauses to LAST_INSERT_ID() + SELECT
- [ ] Replace advisory lock implementation with GET_LOCK() / RELEASE_LOCK()
- [ ] Update 50+ error code assertions in tests
- [ ] Update query timeout handling for MariaDB

**Bot Changes**:
- [ ] Update SQLAlchemy query builders for MySQL dialect
- [ ] Update connection pool configuration
- [ ] Update async query handling (asyncmy vs psycopg2)

**Files to Update**:
- [backend/internal/repository/*.go](../../backend/internal/repository/) (25+ files)
- [backend/internal/repository/*_test.go](../../backend/internal/repository/) (50+ test assertions)
- [bot/src/**/*.py](../../bot/src/) (ORM dialect, connection handling)

**Deliverables**:
- All RETURNING queries converted
- All advisory locks replaced
- All error codes mapped to MariaDB equivalents
- All tests passing with MariaDB driver

---

### **Phase 5: Integration Testing (Week 4-5)**
**Goal**: Validate full stack operation against MariaDB

- [ ] Full integration test suite: frontend → backend → bot → MariaDB
- [ ] Backtest execution: Run existing backtest, verify result precision
- [ ] Load test: 100+ concurrent trades, verify transaction integrity
- [ ] Failover test: Kill MariaDB, verify graceful degradation, restart
- [ ] Data precision test: Compare float vs decimal arithmetic
- [ ] Concurrency test: Simultaneous updates to shared resources (positions, orders)

**Deliverables**:
- Integration test report (all tests passing)
- Load test results (throughput, latency, connection pool utilization)
- Data precision validation (no rounding errors)

---

### **Phase 6: Infrastructure & Deployment (Week 5-6)**
**Goal**: Update infrastructure for production MariaDB

- [ ] Update [stackforge-deployment.yaml](../../stackforge-deployment.yaml): postgres → mariadb image
- [ ] Update Docker Compose files (if any)
- [ ] Update health check configuration
- [ ] Update environment variables (default port 3306 vs 5432)
- [ ] Document backup/restore procedures for MariaDB
- [ ] Plan zero-downtime cutover (if required)
- [ ] Production smoke tests

**Deliverables**:
- Updated deployment manifests
- Backup/restore runbooks
- Deployment validation checklist
- Production readiness assessment

---

## ⚠️ RISK ASSESSMENT

| Risk                           | Severity   | Mitigation                                                                 |
| ------------------------------ | ---------- | -------------------------------------------------------------------------- |
| **Data Loss**                  | 🔴 CRITICAL | Backup PostgreSQL before migration; validate data integrity post-migration |
| **Numeric Precision**          | 🔴 CRITICAL | Test decimal operations extensively; compare results with PostgreSQL       |
| **Backtest Invalidation**      | 🔴 CRITICAL | Rebuild all backtest results in MariaDB; compare performance metrics       |
| **Live Trading Downtime**      | 🟠 HIGH     | If trading during migration: plan cutover window; dual-write period        |
| **Transaction Isolation**      | 🟠 HIGH     | Test concurrent trades; verify no deadlocks; compare lock behavior         |
| **Performance Regression**     | 🟠 HIGH     | Load test; compare query plans; index strategy may differ                  |
| **Connection Pool Exhaustion** | 🟡 MEDIUM   | Monitor connection usage during load test; adjust pool size                |
| **Audit Trail Integrity**      | 🟡 MEDIUM   | Validate all audit log entries migrated; verify timestamps                 |

---

## 🛠️ TOOLS & SKILLS NEEDED

| Tool                                    | Used For                                         | Owner         |
| --------------------------------------- | ------------------------------------------------ | ------------- |
| **Senior PostgreSQL Expert agent**      | Validate migration strategy, audit performance   | Database team |
| **Senior DeFi Monorepo Platform agent** | Cross-service coordination, trading logic review | Platform team |
| **Migration testing framework**         | Verify schema equivalence before/after           | DevOps        |
| **Load testing tool** (k6, JMeter)      | Concurrent trade simulation                      | QA            |
| **Data validation script**              | Compare PostgreSQL vs MariaDB results            | Analytics     |

---

## 📊 SUCCESS CRITERIA

✅ All 6 CRITICAL issues resolved  
✅ All 60 backend + 17 bot migrations passing  
✅ Full integration test suite passing (100% pass rate)  
✅ Load test: ≥1000 concurrent operations without deadlock  
✅ Data precision: ±0 error on decimal arithmetic  
✅ Backtest results: Match PostgreSQL baseline (within floating-point tolerance)  
✅ Production healthcheck: All services running on MariaDB  
✅ Zero data loss migration  

---

## 📞 NEXT STEPS

1. **Confirm timeline**: Can you afford 4-6 weeks of intensive migration work?
2. **Allocate resources**: Need dedicated backend engineer + DevOps + QA
3. **Set up test environment**: Spin up test MariaDB instance for Phase 2
4. **Review & approve migration plan**: Share this doc with team
5. **Start Phase 1**: Create migration directories & ENUM lookup tables

---

## 📎 APPENDIX

### A. ENUM Type Conversion Template
```sql
-- PostgreSQL
CREATE TYPE botstatusenum AS ENUM ('CREATED', 'STARTING', 'RUNNING', 'STOPPED', 'ERROR');

-- MariaDB
CREATE TABLE bot_status_enum (
  value VARCHAR(20) PRIMARY KEY,
  description VARCHAR(255) NOT NULL
);
INSERT INTO bot_status_enum VALUES 
  ('CREATED', 'Bot created'),
  ('STARTING', 'Bot starting'),
  ('RUNNING', 'Bot running'),
  ('STOPPED', 'Bot stopped'),
  ('ERROR', 'Bot error');

-- Add constraint to bot_instance table
ALTER TABLE bot_instance 
  ADD CONSTRAINT fk_bot_instance_status FOREIGN KEY (status) REFERENCES bot_status_enum(value);
```

### B. RETURNING → LAST_INSERT_ID() Pattern
```go
// PostgreSQL
INSERT INTO bot_settings (name, value, user_id) VALUES ($1, $2, $3) 
RETURNING id, created_at, updated_at

// MariaDB
INSERT INTO bot_settings (name, value, user_id) VALUES (?, ?, ?)
SELECT id, created_at, updated_at FROM bot_settings WHERE id = LAST_INSERT_ID()
```

### C. ON CONFLICT → ON DUPLICATE KEY UPDATE Pattern
```sql
-- PostgreSQL
INSERT INTO partner_relationships (partner_user_id, status) VALUES ($1, $2)
ON CONFLICT (partner_user_id) DO UPDATE SET updated_at = NOW(), status = $2
RETURNING id, partner_user_id, status, updated_at

-- MariaDB
INSERT INTO partner_relationships (partner_user_id, status) VALUES (?, ?)
ON DUPLICATE KEY UPDATE status = VALUES(status), updated_at = NOW()
```

### D. Advisory Lock → GET_LOCK() Pattern
```go
// PostgreSQL
SELECT pg_advisory_xact_lock($1)

// MariaDB
SELECT GET_LOCK(CONCAT('backtest_', ?), 30)  // 30 second timeout
// ... do work ...
SELECT RELEASE_LOCK(CONCAT('backtest_', ?))
```

### E. Docker Compose PostgreSQL → MariaDB
```yaml
# PostgreSQL
postgres:
  image: postgres:16
  environment:
    POSTGRES_DB: app
    POSTGRES_USER: app_user
    POSTGRES_PASSWORD: secure_password
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U app_user -d app"]

# MariaDB
mariadb:
  image: mariadb:11.4
  environment:
    MYSQL_DATABASE: app
    MYSQL_USER: app_user
    MYSQL_PASSWORD: secure_password
    MYSQL_ROOT_PASSWORD: root_secure_password
  healthcheck:
    test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1"]
```

---

**Last Updated**: 2026-06-06  
**Status**: Planning Phase — Awaiting team approval to proceed to Phase 1
