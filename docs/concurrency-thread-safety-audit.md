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
  - Failed due to config parse error: `output.formats expected a map, got slice`.
- `golangci-lint run --no-config` (fallback)  
  - 7 issues (mostly style/unused/errcheck, not race-critical).

### Targeted concurrency test run

- `go test ./internal/repository -run WithRunLock -count=1`  
  - Passed (`ok ... 0.066s`)

---

## Audit findings (detailed)

| File                                                         | Function/Area                                                                                   |                  Risk | Issue                                                                                                                                                                                                   | Recommended fix                                                                                                | Est. effort |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- | --------------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------: |
| `backend/internal/repository/backtest_sync_repo.go`          | `UpsertBacktestRun`, `UpsertBacktestTrades`, `UpsertBacktestPositions`, `UpsertBacktestCandles` |              **High** | Read/modify/write pattern (`UPDATE` then `INSERT`) could interleave under concurrent sync calls for same `run_id`, risking duplicate inserts or inconsistent last-write-wins behavior.                  | **Applied:** added per-`run_id` in-process mutex serialization via `withRunLock`.                              |    S (done) |
| `bot/src/bot_instance_manager.py`                            | `delete_instance` lifecycle path                                                                |              **High** | `delete_instance` previously could run without acquiring per-instance lifecycle lock, racing against concurrent `start_instance`/`stop_instance`.                                                       | **Applied:** lock-guarded delete path with `_delete_instance_locked`, plus cleanup of process/lock references. |    S (done) |
| `backend/internal/repository/backtest_sync_repo.go` + schema | candle sync keying                                                                              |            **Medium** | `backtest_candles` has no unique natural key on `(run_id_fk, market, timestamp, resolution)`; concurrent writers across multiple backend processes can still duplicate rows despite in-process locking. | Add DB unique index + convert to native UPSERT (`ON CONFLICT DO UPDATE`) where supported.                      |           M |
| `backend/internal/routes/bot_api_delegate_routes.go`         | backtest admission (`CountActiveRunsByUserID` + create)                                         |            **Medium** | Check-then-act race under concurrent requests can oversubscribe per-user active-run cap.                                                                                                                | Enforce admission atomically in DB (transaction + row/advisory lock or quota table).                           |           M |
| `backend/internal/services/news_service.go`                  | cache path (`GetLatestCoinDeskNews`)                                                            |            **Medium** | Cache miss stampede: multiple simultaneous misses can fan out upstream requests before first writer sets cache.                                                                                         | Add singleflight/once-per-key in-flight suppression.                                                           |         S-M |
| `backend/internal/services/codex_service.go`                 | cache map (`getCached`/`setCached`)                                                             |            **Medium** | Thread-safe map access exists, but no request coalescing and no cache pruning; can create bursty upstream load + unbounded cache growth over long runtimes.                                             | Add singleflight and bounded cache/TTL eviction sweep.                                                         |           M |
| `backend/internal/auth/session_store.go`                     | in-memory fallback sessions                                                                     |               **Low** | Memory session map has no periodic cleanup; expired entries only removed on access. Could grow under traffic patterns with many one-time sessions.                                                      | Add background TTL cleanup ticker or size cap with LRU eviction in fallback mode.                              |           S |
| `bot/src/infrastructure/use_cases/async_job_manager.py`      | `tasks` + done callbacks                                                                        |        **Low/Medium** | Correct under single event loop, but synchronous DB calls in callbacks can block loop under heavy job completions.                                                                                      | Move persistence writes to non-blocking executor/worker queue if throughput rises.                             |           M |
| `bot/src/trading/bot_agents_state.py`                        | dual-write DB + file fallback                                                                   |               **Low** | DB and file writes are serialized in-process, but not transactionally coupled; transient divergence possible if one sink write fails.                                                                   | Add explicit reconciliation marker/version and periodic repair.                                                |           M |
| `backend/.golangci*` config                                  | lint pipeline                                                                                   | **Low (operational)** | Invalid lint config blocks standard static pipeline, reducing early detection of concurrency regressions.                                                                                               | Fix config schema for current `golangci-lint` version.                                                         |           S |

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

---

## Remaining recommendations (prioritized)

1. **Add DB-level uniqueness + UPSERT for candles/trades/positions** (High priority)  
   In-process locks do not protect multi-process/multi-pod deployment.

2. **Make backtest admission cap atomic** (High priority)  
   Move cap enforcement from request-layer check to transactional DB gate.

3. **Add cache stampede protection (`singleflight`)** for News/Codex (Medium)  
   Prevent upstream bursts during concurrent cache misses.

4. **Repair `golangci-lint` config** (Medium)  
   Restore standard CI static analysis coverage.

5. **Session fallback cleanup policy** (Low)  
   Add periodic sweep/cap for long-lived processes without Redis.

---

## Final safety status

The application is **improved but not yet fully concurrency-safe in distributed/high-contention scenarios**.

- ✅ **Fixed now:** key same-process race windows in delegated backtest sync and bot lifecycle deletion.
- ⚠️ **Still open:** DB-level idempotency/uniqueness for some sync writes and atomic admission control under concurrent requests across multiple backend instances.

Given current changes, same-process behavior is safer and more deterministic. For production-grade multi-instance safety, implement the remaining DB-level recommendations above.
