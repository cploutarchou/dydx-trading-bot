# Backtest Concurrency Fix - Implementation Summary

## Issue

Backtest failed with MySQL error 1020: "Record has changed since last read in table 'backtest_runtime_runs'"

This is a **concurrency issue** where two separate database sessions tried to update the same backtest row simultaneously.

## Root Cause Analysis

**Concurrent Writers Problem:**

The backtest execution has two independent threads writing to `backtest_runtime_runs`:

1. **Main Backtest Thread** (progress updates):
   - Updates every ~15 seconds (configurable via `_HEAVY_PROGRESS_PERSIST_EVERY_SECONDS`)
   - Updates: `progress_pct`, `current_pair`, `total_pnl`, `win_rate`, `sharpe_ratio`, `max_drawdown_pct`, `total_trades`, `profit_factor`, `trades_json`, `position_snapshots_json`, `daily_pnl_json`

2. **Heartbeat Keepalive Thread** (session updates):
   - Updates every ~10 seconds (configurable via `BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS`)
   - Updates: `updated_at` timestamp only
   - **Creates a separate database session** to avoid blocking main thread

**Why Concurrency Failed:**

MySQL's "Record has changed since last read" error occurs because:
- Session A reads the row (e.g., version 42)
- Session B modifies and commits (now version 43)
- Session A tries to commit its changes but fails: "You read v42, but v43 exists"

**Why Original Retry Logic Was Insufficient:**

- Only retried once (2 total attempts)
- No delay between retries (immediate retry often fails again)
- Under concurrent pressure, likelihood of success is low

## Solution Implementation

**File Modified:** `src/infrastructure/persistence/repository_backtest.py`

### 1. Added Import
```python
import time
```

### 2. New Retry Helper with Backoff
Created `_retry_with_backoff()` static method:
- **5 retry attempts** (up from 2)
- **Exponential backoff**: 10ms, 20ms, 40ms, 80ms, 160ms (capped at 250ms)
- **Smart error detection**: Retries only MySQL error codes 1020, 1205, 1213 + "Record has changed" message
- **Non-blocking**: Uses safe `time.sleep()` (not in async context)
- **Proper cleanup**: Sessions rolled back and expired between attempts

### 3. Updated `save_run()` Method
Replaced 2-attempt retry loop with:
```python
return self._retry_with_backoff(
    self._save_run_once,
    payload=payload,
    run_id=run_id,
    incoming_request_payload=incoming_request_payload,
    max_attempts=5,
)
```

### 4. Updated `touch_run()` Method
Wrapped heartbeat update in closure and used retry helper:
```python
def _touch_once() -> bool:
    # ... update logic ...
    self.session.commit()
    return True

return self._retry_with_backoff(_touch_once, max_attempts=5)
```

## Why This Fix Works

1. **More Attempts**: 5 attempts vs 2 gives competing threads more time to complete
2. **Backoff Reduces Contention**: The exponential backoff (10→20→40→80→160ms) prevents retry storms
3. **Session State Fresh**: Each retry expires the session and refetches current data
4. **Safe Concurrency Pattern**: Respects MySQL's optimistic locking by transparently retrying

## Testing & Validation

✅ **Import Test**: Module loads without syntax errors
✅ **Unit Test**: `test_save_run_rolls_back_and_retries_mariadb_record_changed` passes
✅ **Integration Tests**: 8 related backtest service tests all pass

```bash
pytest tests/test_backtest_repository.py -v
# PASSED [100%]

pytest tests/test_backtest_service.py -v -k "save or persist or progress"
# 8 passed
```

## Performance Impact

**Minimal:** 
- Only triggered on concurrent modification errors (already failing case)
- Exponential backoff is respectful to system load
- No change to happy-path performance
- Max total wait time on all retries: ~500ms (rare scenario)

## Rollback Plan

If issues arise:
```bash
git revert <commit-hash>
```

This reverts to 2-attempt retry (original behavior). Backtests will fail faster under high concurrency but are already failing, so no regression in successful cases.

## Long-term Improvements to Consider

1. **Pessimistic Locking**: Use `select_for_update()` to lock row during progress updates
2. **Heartbeat Consolidation**: Combine heartbeat + progress updates in single commit
3. **Separate Heartbeat Table**: Move `updated_at` to separate table with finer-grained locking
4. **Async-Safe Pattern**: Use single session for both main + heartbeat operations

## Related Code Locations

- Main fix: `/src/infrastructure/persistence/repository_backtest.py`
- Heartbeat caller: `/src/infrastructure/use_cases/service_backtest.py` lines 1038-1087
- Celery task: `/src/infrastructure/workers/backtest_tasks.py` lines 206-350
- DB model: `/internal/domain/models.py` BacktestRun class

## Configuration

The following environment variables affect concurrency behavior (no changes needed):

- `BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS` (default 10s) — How often heartbeat refreshes
- `BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS` (default 120s) — Stale backtest age threshold


