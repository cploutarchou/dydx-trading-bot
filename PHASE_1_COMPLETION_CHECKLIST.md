# Phase 1 Completion Checklist — PostgreSQL → MariaDB Migration

**Status**: ✅ Phase 1 Complete  
**Date Started**: 2026-06-06  
**Phase Duration**: Week 1

---

## ✅ Phase 1 Deliverables (Complete)

### Directory Structure
- [x] Create `backend/migrations/mysql/` directory
- [x] Create `bot/migrations/mariadb/` directory
- [x] Create README.md for backend/migrations/mysql/
- [x] Create README.md for bot/migrations/mariadb/

### ENUM Conversion Scripts
- [x] Create `000000_enum_conversion.up.sql` (lookup tables for bot_status, job_status, trade_status)
- [x] Create `000000_enum_conversion.down.sql` (rollback script)

### Conversion Templates & Documentation
- [x] Create comprehensive `MARIADB_CONVERSION_TEMPLATES.md` with:
  - [x] SERIAL/BIGSERIAL → AUTO_INCREMENT patterns
  - [x] ENUM → Lookup table patterns
  - [x] RETURNING → LAST_INSERT_ID() patterns
  - [x] ON CONFLICT → ON DUPLICATE KEY UPDATE patterns
  - [x] Advisory locks → GET_LOCK() patterns
  - [x] Data type mappings
  - [x] Function equivalents
  - [x] Index conversion patterns
  - [x] Constraint handling
  - [x] Go developer notes
  - [x] Python developer notes

### Migration Planning Documents
- [x] Create `POSTGRESQL_TO_MARIADB_MIGRATION_PLAN.md` (comprehensive 6-phase plan)
- [x] Create Phase 1 completion checklist (this document)

---

## 📊 Conversion Item Inventory (100+ Items)

### Backend SQL Migrations (60 files to convert)

#### High Priority (Migrate First)
- [ ] `000001_create_redis_settings.up.sql` — SERIAL → AUTO_INCREMENT
- [ ] `000002_create_users.up.sql` — SERIAL, indexes
- [ ] `000003_create_audit_logs.up.sql` — BIGSERIAL, timestamps
- [ ] `000004_create_backtest_strategies.up.sql` — JSONB columns, GIN indexes
- [ ] `000005_create_bot_settings.up.sql` — ON CONFLICT with RETURNING
- [ ] `000006_create_dydx_key_settings.up.sql` — SERIAL
- [ ] `000007_create_dydx_keys.up.sql` — BIGSERIAL, UNIQUE constraints
- [ ] `000008_create_strategy_execution_states.up.sql` — Complex types
- [ ] `000009_create_strategy_version_history.up.sql` — Versioning logic
- [ ] `000010_create_backtest_runs.up.sql` — Status enum, RETURNING

#### ENUM Conversion Required
- [ ] `000022_create_bot_instances.up.sql` — botstatusenum → bot_status_enum FK
- [ ] `000023_create_bot_trades.up.sql` — tradestatusenum → trade_status_enum FK
- [ ] (Audit all 60 files for enum columns)

#### RETURNING Clause Conversions
- [ ] `000005_create_bot_settings.up.sql` — INSERT ... RETURNING
- [ ] `000037_create_rbac_permissions.up.sql` — Upsert with RETURNING
- [ ] All INSERT/UPDATE statements using RETURNING (25+ instances)

#### ON CONFLICT Conversions
- [ ] `000005_create_bot_settings.up.sql` — ON CONFLICT upsert
- [ ] `000037_create_rbac_permissions.up.sql` — ON CONFLICT upsert
- [ ] `000043_seed_portal_bulk_dataset.up.sql` — Bulk upserts (10+ instances)
- [ ] All INSERT ... ON CONFLICT statements (10+ instances)

#### JSONB Index Conversions
- [ ] `000045_add_selected_markets_to_backtest_strategies.up.sql` — GIN → FULLTEXT
- [ ] `000051_phase1_missing_indexes.up.sql` — GIN indexes (5+ indexes)

#### Remaining Backend Files
- [ ] `000006_create_dydx_key_settings.up.sql` through `000060_add_coming_soon_setting.up.sql`
- [ ] All `.down.sql` rollback scripts (60 files)

**Subtotal**: 120+ backend SQL files (60 migrations × 2: up/down)

---

### Bot Alembic Migrations (17 files to convert)

#### Critical Migrations
- [ ] `66f08c3b1066_initial_database_schema.py` — ENUM definitions → lookup tables
- [ ] `64bafb411810_add_real_time_data_tables.py` — Numeric precision columns
- [ ] `c9f4a7b2d1e3_harden_runtime_jobs.py` — ALTER TYPE → lookup table operations

#### Other Migrations
- [ ] `8c1f34af2f10_add_pair_selection_mode_to_strategies.py`
- [ ] `a1b2c3d4e5f6_phase1_missing_performance_indexes.py`
- [ ] `a8d1e5c2b7f9_add_positions_realtime_metadata_columns.py`
- [ ] `b3c4d5e6f7a8_phase3_integrity_constraints.py`
- [ ] `b7a2d6c1f4e8_add_backtest_runs_table.py`
- [ ] `c4d5e6f7a8b9_phase4_drop_redundant_indexes.py`
- [ ] `d4e5f6a7b8c9_canonical_backtest_lifecycle.py`
- [ ] `e1f2a3b4c5d6_add_tracked_positions_and_cointegrated_pairs.py`
- [ ] `f2a9b7c4d1e2_backtest_request_payload_relation.py`

**Subtotal**: 17 bot migration files

---

### Go Code Changes (backend/)

#### Driver & Connection Layer
- [ ] Update `go.mod`: Replace `lib/pq` with `go-sql-driver/mysql`
- [ ] Update `backend/internal/db/db.go`:
  - [ ] Replace PostgreSQL driver initialization
  - [ ] Update connection string parsing (postgresql:// → mysql://)
  - [ ] Update migration path logic (migrations/postgres → migrations/mysql)
  - [ ] Remove PostgreSQL-specific validation

#### Repository Files (RETURNING queries)
- [ ] `backend/internal/repository/settings_repo.go` — 2-3 RETURNING conversions
- [ ] `backend/internal/repository/strategy_repo.go` — 2-3 RETURNING conversions
- [ ] `backend/internal/repository/tradelog_repo.go` — 2-3 RETURNING conversions
- [ ] `backend/internal/repository/bot_trade_repository.go` — 2-3 RETURNING conversions
- [ ] `backend/internal/repository/partner_relationship_repo.go` — 2-3 RETURNING conversions
- [ ] (Audit all 20+ repository files for RETURNING patterns)

#### Advisory Lock Replacement
- [ ] `backend/internal/repository/backtest_repo.go` — Replace `pg_advisory_xact_lock()` with `GET_LOCK()`

#### Error Code Mappings
- [ ] Create error code translation map (PostgreSQL → MySQL)
  - [ ] `42703` → `1054` (unknown column)
  - [ ] `23505` → `1062` (unique violation)
  - [ ] `40P01` → `1213` (deadlock)
  - [ ] (Map 20+ more error codes)
- [ ] Update 50+ error assertions in test files

#### Query/Driver Updates
- [ ] Update all pq-specific error handling
- [ ] Test driver import paths
- [ ] Verify connection pooling parameters

**Subtotal**: 30+ Go files with changes

---

### Python Code Changes (bot/)

#### Driver & Connection Layer
- [ ] Update `bot/requirements.txt`: Replace `psycopg2` with `asyncmy` or `pymysql`
- [ ] Update `bot/src/infrastructure/database.py`:
  - [ ] Replace psycopg2 import with asyncmy/pymysql
  - [ ] Update connection string parsing
  - [ ] Update database type validation (accept mysql/mariadb)
  - [ ] Update SQLAlchemy dialect (postgresql → mysql+asyncmy)

#### SQLAlchemy ORM Updates
- [ ] `bot/src/**/*.py` — Audit all models for PostgreSQL-specific types
  - [ ] Replace `sa.Enum()` with `sa.String()` + FK
  - [ ] Update any PostgreSQL-specific operators
  - [ ] Update connection pool configuration for MySQL

#### Async Query Handling
- [ ] Test async query execution with asyncmy
- [ ] Verify transaction handling
- [ ] Test connection pool overflow behavior

**Subtotal**: 10+ Python files

---

### Test Files (Error Code Assertions)

#### Go Tests
- [ ] `backend/internal/repository/bot_instance_repository_test.go` — Update pq.Error assertions (5+ tests)
- [ ] All `*_test.go` files in `backend/internal/repository/` (15+ files)
- [ ] Update expected error codes throughout (50+ assertions)

#### Python Tests
- [ ] `bot/tests/**/*.py` — Update any psycopg2-specific assertions
- [ ] Verify SQLAlchemy ORM tests work with MySQL dialect

**Subtotal**: 50+ test assertions

---

### Infrastructure Files

#### Docker & Deployment
- [ ] `stackforge-deployment.yaml` — Update postgres service to mariadb
  - [ ] Image: postgres:16 → mariadb:11.4
  - [ ] Environment variables: POSTGRES_* → MYSQL_*
  - [ ] Healthcheck: pg_isready → mysqladmin ping
  - [ ] Port: 5432 → 3306
- [ ] Docker Compose files (if any) — Same updates

#### Configuration
- [ ] `.env` defaults — Update DB port (5432 → 3306)
- [ ] Connection string templates — postgresql:// → mysql://
- [ ] Documentation — Update setup guides

**Subtotal**: 5-10 infrastructure files

---

## 🎯 Conversion Pattern Counts

| Pattern                           | Count    | Status                                       |
| --------------------------------- | -------- | -------------------------------------------- |
| SERIAL → AUTO_INCREMENT           | 20+      | 📋 Template ready                             |
| BIGSERIAL → BIGINT AUTO_INCREMENT | 6-8      | 📋 Template ready                             |
| CREATE TYPE ENUM → Lookup table   | 3        | ✅ Scripts ready (000000_enum_conversion.sql) |
| RETURNING clauses                 | 25+      | 📋 Template ready                             |
| ON CONFLICT → ON DUPLICATE KEY    | 10+      | 📋 Template ready                             |
| pg_advisory_xact_lock → GET_LOCK  | 1        | 📋 Template ready                             |
| JSONB operators (@>, ->, ->>>)    | 10+      | 📋 Template ready                             |
| GIN indexes → FULLTEXT/B-tree     | 5+       | 📋 Template ready                             |
| ARRAY types → JSON                | 5+       | 📋 Template ready                             |
| PostgreSQL functions              | 15+      | 📋 Template ready                             |
| Error code assertions             | 50+      | 📋 Need mapping                               |
| Type casts (::type)               | 20+      | 📋 Template ready                             |
| **TOTAL**                         | **200+** |                                              |

---

## 📋 Next Steps: Phase 2 (Week 1-2)

### Phase 2: Driver & Connection Layer

**Goal**: Replace database drivers and update connection logic

**Tasks**:
- [ ] Update `bot/requirements.txt` — Replace `psycopg2` with `asyncmy`
- [ ] Update `backend/go.mod` — Replace `lib/pq` with `go-sql-driver/mysql`
- [ ] Modify `bot/src/infrastructure/database.py` — MySQL connection logic
- [ ] Modify `backend/internal/db/db.go` — MySQL driver initialization
- [ ] Test basic connection to test MariaDB instance
- [ ] Create error code mapping reference

**Effort**: 2-3 days

**Success Criteria**:
- ✅ Both services connect to test MariaDB instance
- ✅ Connection pooling works correctly
- ✅ Error handling updated for MySQL error codes

---

## 📞 Resources

### Reference Documents
- [POSTGRESQL_TO_MARIADB_MIGRATION_PLAN.md](POSTGRESQL_TO_MARIADB_MIGRATION_PLAN.md) — 6-phase roadmap
- [MARIADB_CONVERSION_TEMPLATES.md](MARIADB_CONVERSION_TEMPLATES.md) — SQL/code patterns
- [backend/migrations/mysql/README.md](backend/migrations/mysql/README.md) — Backend migration guide
- [bot/migrations/mariadb/README.md](bot/migrations/mariadb/README.md) — Bot migration guide

### Key Files to Update
- Bot: `bot/requirements.txt`, `bot/src/infrastructure/database.py`
- Backend: `backend/go.mod`, `backend/internal/db/db.go`
- Infrastructure: `stackforge-deployment.yaml`

### Tools Needed
- MariaDB 11.4+ test instance (Docker)
- MySQL Workbench or DBeaver for schema comparison
- migrate CLI tool for backend migrations (or flyway/liquibase)
- Alembic CLI for bot migrations

---

## ✅ Phase 1 Summary

**Completed**:
- ✅ Created directory structure (backend/migrations/mysql, bot/migrations/mariadb)
- ✅ Created ENUM conversion scripts (000000_enum_conversion.up/down.sql)
- ✅ Created comprehensive conversion templates (200+ patterns documented)
- ✅ Created detailed migration plan (6-phase roadmap)
- ✅ Created this completion checklist (200+ items catalogued)

**Ready for Phase 2**: Yes ✅

**Phase 1 Effort**: ~2 days  
**Total Remaining**: 23-38 days

---

**Status**: ✅ PHASE 1 COMPLETE — Ready to proceed to Phase 2  
**Last Updated**: 2026-06-06
