---
name: "Frontend Job Fields Update"
description: "Update React components to display rich DB-backed job metadata from Bot Service. Use when: adding job execution details, progress tracking, error diagnostics, or timing information to job/backtest UI."
---

# Frontend: Consume Rich Bot Service Job Metadata

## Context

The backend now properly preserves and normalizes all DB-backed job fields from the Bot Service API. The `GET /api/v1/bots/{instance_id}/jobs` endpoint now returns comprehensive job data with execution details, timing info, and structured metadata.

## New Fields Available

The backend now forwards these fields from each job object in the response:

### Timing & Lifecycle
- `created_at` — Job creation timestamp (RFC3339)
- `started_at` — When job execution began
- `completed_at` — When job completed/failed
- `updated_at` — Last update timestamp

### Progress & Execution
- `progress_pct` — Job progress as percentage (0-100); aliases: `progress_percent`, `progress`
- `execution_time_ms` — Total milliseconds elapsed
- `process_id` — Operating system process ID (if applicable)

### Error & Cancellation Context
- `error_message` — Human-readable error text (if failed)
- `error_traceback` — Stack trace or execution log (if available)
- `cancellation_reason` — Why the job was cancelled (if cancelled)

### Configuration & Results
- `metadata` — Structured JSON object with extensible job metadata
- `result` — Job output/results (success cases)
- `config` — Job input configuration (for context)

### Retry Information
- `retry_count` — Number of retries attempted
- `max_retries` — Maximum retry attempts allowed

## Status Normalization

Job statuses are now normalized to lowercase canonical values:
- `pending` — Job queued or not yet started
- `running` — Job in progress
- `completed` — Job finished successfully
- `failed` — Job failed (see `error_message`)
- `cancelled` — Job was cancelled (see `cancellation_reason`)

**Legacy compatibility**: Old status values (queued, retry, created, etc.) are safely mapped upstream; you can continue using your existing status handling, but prefer the canonical lowercase forms.

## Priority Updates

### 1. Job List / History View (High Priority)
**File**: `src/pages/BotDashboard.tsx`, `src/components/JobHistory.tsx`

Add columns or detail rows for:
- `started_at`, `completed_at` (with relative time like "2 hours ago")
- `execution_time_ms` formatted as "1h 23m 45s"
- Job status badge matching canonical values
- `progress_pct` progress bar (if running)

### 2. Job Detail Modal / Panel (High Priority)
**File**: `src/components/JobDetailsPanel.tsx` or similar

Display comprehensive job info:
```
Status:           cancelled (lowercase, color-coded)
Progress:         75% (if running)
Created:          2026-04-26T15:30:00Z
Started:          2026-04-26T15:31:00Z
Completed:        2026-04-26T15:45:00Z
Execution Time:   14 minutes 23 seconds
Process ID:       12345
Cancellation Reason: User requested stop
Error Message:    [if status is "failed"]
Error Traceback:  [expandable, code block]
Metadata:         [JSON display]
Result:           [if available]
Retry Info:       3 / 5 retries
```

### 3. Backtest Status Panel (Medium Priority)
**File**: `src/pages/BacktestDetailsV2.tsx`

Update progress display to use:
- `progress_pct` as the primary source (not websocket estimate)
- `started_at` for ETA calculation
- `execution_time_ms` for elapsed display
- Keep HTTP polling as source of truth (don't fail on missing websocket)

### 4. Real-Time Updates (Medium Priority)
**File**: `src/api/hooks.ts` (useJobProgress, useBacktestProgress)

Ensure hooks return all new fields:
```typescript
{
  jobId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progressPct: number;
  startedAt?: string;
  completedAt?: string;
  executionTimeMs?: number;
  errorMessage?: string;
  cancellationReason?: string;
  metadata?: Record<string, any>;
}
```

### 5. Status Badge Styling (Low Priority)
**File**: `src/components/StatusBadge.tsx`

Ensure colors match canonical statuses (update any legacy status checks):
- `pending` → Amber/yellow
- `running` → Blue/cyan
- `completed` → Green/emerald
- `failed` → Red/rose
- `cancelled` → Slate/gray

## Type Definition Updates

Add/update TypeScript interfaces in `src/api/types.ts`:

```typescript
interface BotJob {
  job_id: string;
  job_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress_pct: number;
  progress_percent?: number; // alias
  progress?: number; // alias
  
  // Timing
  created_at: string; // RFC3339
  started_at?: string;
  completed_at?: string;
  updated_at: string;
  
  // Execution
  execution_time_ms?: number;
  process_id?: number;
  
  // Error context
  error_message?: string;
  error_traceback?: string;
  cancellation_reason?: string;
  
  // Configuration & results
  metadata?: Record<string, any>;
  result?: Record<string, any>;
  config?: Record<string, any>;
  
  // Retry tracking
  retry_count?: number;
  max_retries?: number;
}
```

## Testing Checklist

After updating components:

1. ✅ Fetch jobs for a bot and verify all new fields appear in the response
2. ✅ Display job list with `created_at`, `started_at`, `execution_time_ms`
3. ✅ Click a running job and see `progress_pct` displayed accurately
4. ✅ Click a failed job and see `error_message` and `error_traceback`
5. ✅ Click a cancelled job and see `cancellation_reason`
6. ✅ Verify status badges use canonical lowercase values (not uppercase)
7. ✅ Verify old status values (queued, retry, etc.) still display correctly
8. ✅ Backtest progress uses HTTP `/status` endpoint as source of truth, not websocket estimates
9. ✅ Metadata JSON renders nicely (expandable/collapsible or code block)
10. ✅ Relative timestamps update (e.g., "2 hours ago" → "2 hours 1 min ago")

## Backward Compatibility Notes

- Existing code that checks `status === 'QUEUED'` or `status === 'QUEUED'` will continue to work due to upstream normalization
- Prefer `status === 'pending'` (lowercase) in new code
- All new fields are optional; use nullish coalescing or optional chaining to avoid crashes
- `progress_pct` will always be present (0 if not running)

## API Endpoints Reference

**List bot jobs:**
```
GET /api/v1/bots/{instance_id}/jobs?days=7
```

**Get backtest status (HTTP polling source of truth):**
```
GET /api/v1/backtests/{run_id}/status
```

**WebSocket for live updates (best-effort, not authoritative):**
```
WS /api/v1/backtests/{run_id}/live
```

## Related Backend Changes

See backend summary for:
- Job field preservation & normalization logic
- Status mapping rules (legacy → canonical)
- Readiness/health check improvements
- Backtest websocket resilience

---

**Questions?** Refer to the backend changes summary or run test suite:
```bash
cd backend && make test
```
