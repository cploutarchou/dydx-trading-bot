# Backtest Concurrency Fix (2026-06-21)

## Problem

Backtest execution was failing with MySQL error 1020: "Record has changed since last read in table 'backtest_runtime_runs'".

```
(pymysql.err.OperationalError) (1020, "Record has changed since last read in table 'backtest_runtime_runs'; 
try restarting transaction")
```

## Root Cause

The backtest execution system has **concurrent writers** to the same `backtest_runtime_runs` database row:

1. **Main backtest loop**: Updates progress metrics (progress_pct, current_pair, total_pnl, trades, etc.) via `save_run()`
2. **Heartbeat keepalive thread**: Updates only the `updated_at` timestamp via separate `touch_run()` calls to keep backtest marked as "active"

**The race condition:**
- Session A (main backtest) reads the backtest row to update progress
- Session B (heartbeat thread) reads the same row and updates `updated_at`  
- Session B commits successfully
- Session A tries to commit its progress update but fails with error 1020 because the row was modified after it read it

**Why it happened:**
- Each `touch_run()` call creates a **separate database session** (line 1044-1049 in `service_backtest.py`)
- Both threads update the same row with no optimistic locking or pessimistic row-level locks
- The original retry logic only retried once (2 total attempts), insufficient for sustained concurrent modification pressure

## Solution

Implemented robust retry logic with **exponential backoff** to handle transient concurrency errors:

### Changes to `src/infrastructure/persistence/repository_backtest.py`

1. **Added `time` import** for sleep/backoff between retries

2. **New `_retry_with_backoff()` static method:**
   - Retries operations up to 5 times (was 2)
   - Implements exponential backoff: 10ms → 20ms → 40ms → 80ms → 160ms (capped at 250ms)
   - Detects retryable errors (MySQL codes 1020, 1205, 1213 + "Record has changed" message)
   - Non-retryable errors raise immediately
   - Properly rolls back and expires session state between attempts

3. **Updated `save_run()` method:**
   - Replaced inline retry loop with `_retry_with_backoff(self._save_run_once, max_attempts=5)`
   - Cleaner and more resilient to concurrent modifications

4. **Updated `touch_run()` method:**
   - Wrapped heartbeat update in nested `_touch_once()` closure
   - Uses `_retry_with_backoff(_touch_once, max_attempts=5)`
   - Properly handles session rollback on OperationalError

## Why This Works

1. **Increased attempts**: More time for competing threads to finish and release locks
2. **Exponential backoff**: Prevents thundering herd; gives other sessions time to complete writes
3. **Session state management**: Each retry expires the session and re-fetches fresh data
4. **Non-blocking**: Uses `time.sleep()` (sync code path only; no impact on async event loops)

## Testing

The fix was validated by:
- ✅ Import verification: `BacktestRepository` module loads correctly
- ✅ Syntax validation: No Python syntax errors
- ✅ Type checking: Pre-existing warnings only (unrelated to this change)

## Risk Assessment

**Rollout Risk: Low**

- Isolated to backtest repository layer
- Retry logic only affects error cases (already failing)
- No changes to happy-path behavior
- Exponential backoff prevents runaway retry loops
- Uses standard `time.sleep()` safely (non-async context)

## Rollback Plan

Revert to commit prior to this fix:
```bash
git revert <commit-hash>
```

This returns to the original 2-attempt retry logic. Backtests will fail faster but more often under concurrent modification pressure. The original code was correct but under-provisioned for the concurrent heartbeat update pattern.

## Long-term Improvements

Consider for future optimization:
1. **Pessimistic locking**: Use `select_for_update()` to lock the row during progress updates
2. **Separate heartbeat table**: Move heartbeat updates to a separate table with coarser-grained locking
3. **Async-safe heartbeat**: Use same session as main backtest loop to avoid concurrent modification entirely

