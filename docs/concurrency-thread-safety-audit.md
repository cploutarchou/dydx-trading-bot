# Concurrency & Thread-Safety Audit

Date: 2026-05-02  
Scope: Monorepo (`backend/`, `bot/`, selected integration surfaces)  
Auditor: GitHub Copilot (GPT-5.3-Codex)

## What was executed

> Per user request, broad/full test runs were skipped as no longer relevant for this audit pass.

### Static checks

- `go vet ./...` (from `backend/`)  
  - No emitted findings in this session.
- `golangci-lint run` (from `backend/`)  
  - **Now loads successfully under golangci-lint v2** after config migration (`version: "2"`, output schema updates, deprecated linter cleanup).
  - Emits project lint findings (expected backlog) rather than failing at config-parse stage.
- `golangci-lint run --no-config` (fallback)  
  - 7 issues (mostly style/unused/errcheck, not race-critical).

### Targeted concurrency test run

- `go test ./internal/repository -run WithRunLock -count=1`  
  - Passed (`ok ... 0.066s`)
- `go test ./internal/repository -run 'BacktestSync|WithRunLock' -count=1`  
  - Passed (`ok ... 0.065s`)
- `go test ./internal/repository -run 'WithUserAdmissionLock|BacktestSync|WithRunLock' -count=1`  
  - Passed (`ok ... 0.117s`)
- `go test ./internal/routes -run 'BacktestRun|ContractLock' -count=1`  
  - Passed compile/run gate (`ok ... [no tests to run]`)
- `go test -tags=integration ./internal/services -run 'NewsServiceCoalescesConcurrentCacheMisses|CodexServiceSearchCoalescesConcurrentCacheMisses|NewsServiceParsesCoinDeskRSS|CodexServiceSearchUsesCacheAndNormalizesResults' -count=1`  
  - Passed (`ok ... 0.167s`)
- `go test ./internal/services -run '^$' -count=1`  
  - Passed compile gate (`ok ... [no tests to run]`)

---

## Audit findings (detailed)

- **File:** `backend/internal/repository/backtest_sync_repo.go`  
  **Function/Area:** `UpsertBacktestRun`, `UpsertBacktestTrades`, `UpsertBacktestPositions`, `UpsertBacktestCandles`  
  **Risk:** High  
  **Issue:** Read/modify/write (`UPDATE` then `INSERT`) could interleave under concurrent sync calls for same `run_id`.  
  **Recommended fix:** **Applied** via per-`run_id` in-process mutex serialization (`withRunLock`).  
  **Estimated effort:** S (done)

- **File:** `bot/src/bot_instance_manager.py`  
  **Function/Area:** `delete_instance` lifecycle path  
  **Risk:** High  
  **Issue:** `delete_instance` could run without the per-instance lifecycle lock and race with `start_instance`/`stop_instance`.  
  **Recommended fix:** **Applied** lock-guarded delete path with `_delete_instance_locked` and process/lock cleanup.  
  **Estimated effort:** S (done)

- **File:** `backend/internal/repository/backtest_sync_repo.go` (+ migrations)  
  **Function/Area:** DB-level idempotency for child sync tables  
  **Risk:** High  
  **Issue:** Multi-replica race windows existed when sync used update-then-insert and lacked enforced candle natural-key uniqueness.  
  **Recommended fix:** **Applied** postgres/sqlite idempotency migrations + native UPSERT (`ON CONFLICT`) for trades/positions/candles.  
  **Estimated effort:** M (done)

- **File:** `backend/internal/routes/bot_api_delegate_routes.go`, `backend/internal/repository/backtest_repo.go`  
  **Function/Area:** backtest admission (`CountActiveRunsByUserID` + create)  
  **Risk:** High  
  **Issue:** Check-then-act race could oversubscribe per-user active-run cap under concurrent requests across replicas.  
  **Recommended fix:** **Applied** atomic admission using per-user DB advisory lock (`WithUserAdmissionLock`) around count + create + sync.  
  **Estimated effort:** M (done)

- **File:** `backend/internal/services/news_service.go`  
  **Function/Area:** cache path (`GetLatestCoinDeskNews`)  
  **Risk:** Medium  
  **Issue:** Cache-miss stampede can fan out upstream calls before cache fill.  
  **Recommended fix:** **Applied** keyed in-flight request coalescing for concurrent cache misses.  
  **Estimated effort:** S-M (done)

- **File:** `backend/internal/services/codex_service.go`  
  **Function/Area:** cache map (`getCached`/`setCached`)  
  **Risk:** Medium  
  **Issue:** No request coalescing and no cache pruning can drive bursty upstream load and long-term growth.  
  **Recommended fix:** **Applied (coalescing):** keyed in-flight suppression for overview/search/detail/chart cache-miss paths; cache pruning remains optional follow-up.  
  **Estimated effort:** M (partially done)

- **File:** `backend/internal/auth/session_store.go`  
  **Function/Area:** in-memory fallback sessions  
  **Risk:** Low  
  **Issue:** Expired entries are only removed on access; map can grow in one-shot session patterns.  
  **Recommended fix:** Add background TTL cleanup ticker or size cap/LRU in fallback mode.  
  **Estimated effort:** S

- **File:** `bot/src/infrastructure/use_cases/async_job_manager.py`  
  **Function/Area:** `tasks` + done callbacks  
  **Risk:** Low/Medium  
  **Issue:** DB writes in done callbacks are sync and can block loop under high completion throughput.  
  **Recommended fix:** **Applied** in-process persistence serialization + progress-write throttling to reduce QueuePool pressure in high-concurrency backtest runs.  
  **Estimated effort:** M (done)

- **File:** `bot/src/trading/bot_agents_state.py`  
  **Function/Area:** dual-write DB + file fallback  
  **Risk:** Low  
  **Issue:** Writes are serialized in-process but not transactionally coupled across sinks.  
  **Recommended fix:** Add reconciliation marker/version and periodic repair pass.  
  **Estimated effort:** M

- **File:** `backend/.golangci*` config  
  **Function/Area:** lint pipeline  
  **Risk:** Low (operational)  
  **Issue:** Invalid lint config blocks standard static pipeline coverage.  
  **Recommended fix:** **Applied** config migration for `golangci-lint` v2 (`version` header, `output.formats` map schema, deprecated linter removals).  
  **Estimated effort:** S (done)

---

## Fixes applied in this audit

### 1) Per-run synchronization in backtest sync repository

**File:** `backend/internal/repository/backtest_sync_repo.go`

- Added `runLocks sync.Map` to `BacktestSyncRepository`.
- Added helper `withRunLock(runID string, fn func() error) error`.
- Wrapped all run-scoped upsert methods with `withRunLock`:
  - `UpsertBacktestRun`
  - `UpsertBacktestTrades`
  - `UpsertBacktestPositions`
  - `UpsertBacktestCandles`

**Effect:** Prevents same-process concurrent sync interleaving for a given `run_id`, reducing race window for duplicate/inconsistent writes.

### 2) Lock-guarded instance deletion in bot lifecycle manager

**File:** `bot/src/bot_instance_manager.py`

- `delete_instance` now acquires per-instance lifecycle lock before mutating state.
- Added `_delete_instance_locked` for lock-held delete flow.
- Cleanup now explicitly removes:
  - `self.processes[instance_id]`
  - `self.instance_locks[instance_id]`

**Effect:** Eliminates start/stop/delete race windows for same instance in concurrent API operations.

### 3) New concurrency regression tests

**File:** `backend/internal/repository/backtest_sync_repo_concurrency_test.go`

- `TestBacktestSyncRepository_WithRunLockSerializesSameRunID`
- `TestBacktestSyncRepository_WithRunLockAllowsDifferentRunIDs`

**Effect:** Guards intended lock semantics and remains compatible with race-detector style execution.

### 4) Phase-2 DB-level idempotency hardening (multi-replica safe path)

**Files:**

- `backend/internal/repository/backtest_sync_repo.go`
- `backend/migrations/postgres/000054_backtest_sync_idempotency_indexes.up.sql`
- `backend/migrations/postgres/000054_backtest_sync_idempotency_indexes.down.sql`
- `backend/migrations/sqlite/000046_backtest_sync_idempotency_indexes.up.sql`
- `backend/migrations/sqlite/000046_backtest_sync_idempotency_indexes.down.sql`

**Changes:**

- Converted child sync writes to atomic UPSERTs:
  - `UpsertBacktestTrades` → `INSERT ... ON CONFLICT (trade_id) DO UPDATE`
  - `UpsertBacktestPositions` → `INSERT ... ON CONFLICT (position_id) DO UPDATE`
  - `UpsertBacktestCandles` → `INSERT ... ON CONFLICT (<fk>, market, timestamp, resolution) DO UPDATE`
- Added migration-backed unique indexes for UPSERT conflict targets.
- Added migration-time deduplication for existing duplicate rows.
- Normalized candle `resolution` and enforced not-null semantics (Postgres) for deterministic uniqueness.

**Effect:** Prevents duplicate child-row creation and non-deterministic write races across concurrent backend replicas.

### 5) Phase-3 atomic per-user admission hardening (multi-replica safe path)

**Files:**

- `backend/internal/repository/backtest_repo.go`
- `backend/internal/repository/backtest_repo_admission_lock_test.go`
- `backend/internal/routes/bot_api_delegate_routes.go`

**Changes:**

- Added `BacktestRepository.WithUserAdmissionLock(ctx, userID, fn)`:
  - PostgreSQL path uses `pg_try_advisory_lock` / `pg_advisory_unlock` on a pinned DB connection.
  - Non-Postgres/test fallback uses per-user in-process mutex map.
- Moved create-backtest admission flow into lock scope:
  - active-run count check
  - upstream backtest create call
  - local sync persistence (`syncRun`)
- Added focused repository lock tests:
  - same user serializes
  - different users can proceed concurrently

**Effect:** Removes check-then-act oversubscription race for per-user active-run limits across concurrent backend replicas.

### 6) Phase-4 cache-miss coalescing hardening (upstream burst control)

**Files:**

- `backend/internal/services/news_service.go`
- `backend/internal/services/codex_service.go`
- `backend/internal/services/news_service_test.go`
- `backend/internal/services/codex_service_test.go`

**Changes:**

- Added keyed in-flight request coalescing in `NewsService`:
  - New in-flight call map guarded by mutex.
  - Concurrent misses for the same key now wait for a single upstream fetch.
- Added keyed in-flight request coalescing in `CodexService`:
  - Shared helper wrapping cache-miss fetches for overview/search/detail/chart paths.
  - Double-check cache within coalesced callback to avoid redundant fetch after wait.
- Added focused integration tests validating coalescing behavior:
  - `TestNewsServiceCoalescesConcurrentCacheMisses`
  - `TestCodexServiceSearchCoalescesConcurrentCacheMisses`

**Effect:** Reduces upstream fan-out under concurrent cache misses, lowering burst load and improving consistency of cached responses.

### 7) Phase-5 lint pipeline compatibility hardening (tooling safety)

**Files:**

- `backend/.golangci.yml`
- `backend/.golangci.release.yml`

**Changes:**

- Migrated configs to `golangci-lint` v2 schema:
  - Added `version: "2"`.
  - Converted `output.formats` from list to map style.
  - Removed deprecated/unsupported linter entries (`typecheck`, `gosimple`, `stylecheck`, formatter linters in `enable`).
  - Removed legacy incompatible severity block.
- Verified both standard and release profiles execute (now reporting lint findings instead of parse failures).

**Effect:** Restores lint pipeline operability so concurrency regressions can be caught again by normal static checks.

### 8) Phase-6 async job DB-pressure hardening (QueuePool exhaustion mitigation)

**Files:**

- `bot/src/infrastructure/use_cases/async_job_manager.py`
- `bot/tests/test_async_job_manager.py`

**Changes:**

- Added in-process persistence serialization lock in `AsyncJobManager._with_uow` to avoid bursty concurrent DB checkout pressure from job-state writes.
- Added progress write-throttling in `mark_progress`:
  - minimum time interval gate (`JOB_PROGRESS_MIN_INTERVAL_SECONDS`, default `1.5`)
  - minimum delta gate (`JOB_PROGRESS_MIN_DELTA_PCT`, default `1.0`)
  - always persists terminal progress (`0%` / `100%`) and clears per-job checkpoints on terminal state transitions.
- Improved `mark_failed` fallback error messaging for empty exception strings (stores exception class name instead of blank error).
- Added focused tests:
  - `test_mark_progress_is_throttled`
  - `test_mark_failed_uses_fallback_message_for_empty_error`

**Effect:** Significantly reduces job-persistence write amplification and DB pool contention during concurrent backtest execution while preserving terminal status durability.

---

## Remaining recommendations (prioritized)

1. **Session fallback cleanup policy** (Low)  
   Add periodic sweep/cap for long-lived processes without Redis.

2. **Optional Codex cache hygiene sweep** (Low/Medium)  
  Add bounded cache pruning/periodic eviction for long-lived backends with high key churn.

3. **Lint backlog burn-down (non-blocking)** (Low/Medium operational)  
  The config layer is now fixed, but repository-wide lint findings remain and can be reduced incrementally.

---

## Final safety status

The application is **materially improved with DB-idempotent child sync and atomic per-user admission for delegated backtest creation**, with a smaller set of remaining hardening opportunities.

- ✅ **Fixed now:** key same-process race windows, DB-level idempotent child-sync writes (trades/positions/candles), and atomic per-user run admission across concurrent backend replicas.
- ✅ **Fixed now (added):** cache-miss coalescing for News/Codex to suppress concurrent upstream fan-out.
- ✅ **Fixed now (added):** backend golangci-lint v2 config compatibility; lint pipeline no longer fails at parse/config stage.
- ✅ **Fixed now (added):** bot async-job persistence pressure controls (serialized persistence + throttled progress writes) to mitigate QueuePool exhaustion.
- ⚠️ **Still open:** fallback-session lifecycle hygiene, optional Codex cache-pruning policy, and non-blocking lint backlog reduction.

Given current changes, both same-process and multi-replica sync behavior are more deterministic for backtest child data. Complete the remaining recommendations for full platform-level concurrency robustness.
