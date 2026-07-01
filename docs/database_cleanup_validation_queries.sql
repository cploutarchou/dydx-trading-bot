-- PostgreSQL Cleanup Validation Queries
-- Use these queries to validate data before and after migration
-- Part of Phase 3: Data/storage finalization

-- ============================================================================
-- SECTION 1: PRE-MIGRATION VALIDATION
-- ============================================================================

-- Query 1: Count of runs with legacy JSON columns that need migration
SELECT 
    COUNT(*) as total_runs_needing_migration
FROM backtest_runtime_runs
WHERE 
    (jsonb_byte_length(trades_json) > 0 
     OR jsonb_byte_length(position_snapshots_json) > 0
     OR jsonb_byte_length(daily_pnl_json) > 0)
    AND (artifact_reference IS NULL OR artifact_reference = '');

-- Query 2: Total size of data to migrate (in MB)
SELECT 
    SUM(jsonb_byte_length(trades_json) + 
        jsonb_byte_length(position_snapshots_json) + 
        jsonb_byte_length(daily_pnl_json)) / (1024 * 1024) as total_size_mb
FROM backtest_runtime_runs
WHERE 
    (jsonb_byte_length(trades_json) > 0 
     OR jsonb_byte_length(position_snapshots_json) > 0
     OR jsonb_byte_length(daily_pnl_json) > 0)
    AND (artifact_reference IS NULL OR artifact_reference = '');

-- Query 3: Largest runs needing migration (for batch processing)
SELECT 
    run_id,
    jsonb_byte_length(trades_json) / 1024.0 as trades_size_kb,
    jsonb_byte_length(position_snapshots_json) / 1024.0 as snapshots_size_kb,
    jsonb_byte_length(daily_pnl_json) / 1024.0 as pnl_size_kb,
    (jsonb_byte_length(trades_json) + 
     jsonb_byte_length(position_snapshots_json) + 
     jsonb_byte_length(daily_pnl_json)) / 1024.0 as total_size_kb
FROM backtest_runtime_runs
WHERE 
    (jsonb_byte_length(trades_json) > 0 
     OR jsonb_byte_length(position_snapshots_json) > 0
     OR jsonb_byte_length(daily_pnl_json) > 0)
    AND (artifact_reference IS NULL OR artifact_reference = '')
ORDER BY total_size_kb DESC
LIMIT 100;

-- Query 4: Backtest run requests with request_json
SELECT 
    COUNT(*) as total_requests,
    COUNT(CASE WHEN jsonb_byte_length(request_json) > 1000 THEN 1 END) as large_requests
FROM backtest_run_requests
WHERE request_json IS NOT NULL;

-- Query 5: Check task tables health (Phase 2 validation)
SELECT 
    (SELECT COUNT(*) FROM task_commands) as total_commands,
    (SELECT COUNT(*) FROM task_runs) as total_runs,
    (SELECT COUNT(*) FROM task_attempts) as total_attempts,
    (SELECT COUNT(*) FROM worker_heartbeats) as total_heartbeats;

-- ============================================================================
-- SECTION 2: POST-MIGRATION VALIDATION
-- ============================================================================

-- Query 6: Verify all runs with JSON now have artifacts
SELECT 
    COUNT(*) as runs_without_artifacts
FROM backtest_runtime_runs
WHERE 
    (jsonb_byte_length(trades_json) > 0 
     OR jsonb_byte_length(position_snapshots_json) > 0
     OR jsonb_byte_length(daily_pnl_json) > 0)
    AND (artifact_reference IS NULL OR artifact_reference = '');
-- Expected: 0

-- Query 7: Verify artifact references are valid JSON
SELECT 
    run_id,
    artifact_reference
FROM backtest_runtime_runs
WHERE 
    (jsonb_byte_length(trades_json) > 0 
     OR jsonb_byte_length(position_snapshots_json) > 0
     OR jsonb_byte_length(daily_pnl_json) > 0)
    AND artifact_reference IS NOT NULL
    AND artifact_reference != ''
    AND (artifact_reference::json IS NULL OR artifact_reference = 'null');
-- Expected: 0 (no invalid JSON)

-- Query 8: Check that artifact references contain expected keys
SELECT 
    run_id,
    artifact_reference
FROM backtest_runtime_runs
WHERE 
    artifact_reference IS NOT NULL
    AND artifact_reference != ''
    AND (artifact_reference::json->>'trades' IS NULL 
         AND artifact_reference::json->>'position_snapshots' IS NULL
         AND artifact_reference::json->>'daily_pnl' IS NULL);
-- Expected: 0 (all artifacts have at least one expected key)

-- ============================================================================
-- SECTION 3: SCHEMA VALIDATION
-- ============================================================================

-- Query 9: Check if legacy columns can be safely dropped
SELECT 
    COUNT(*) as non_empty_trades,
    COUNT(*) as non_empty_snapshots,
    COUNT(*) as non_empty_pnl
FROM backtest_runtime_runs
WHERE jsonb_byte_length(trades_json) > 0
   OR jsonb_byte_length(position_snapshots_json) > 0
   OR jsonb_byte_length(daily_pnl_json) > 0;
-- Expected: 0 for all counts before dropping columns

-- Query 10: Check column usage in backtest_run_requests
SELECT 
    COUNT(*) as non_empty_request_json
FROM backtest_run_requests
WHERE jsonb_byte_length(request_json) > 0;
-- Note: This may be > 0; request_json is small and may be kept

-- ============================================================================
-- SECTION 4: INTEGRITY CHECKS
-- ============================================================================

-- Query 11: Verify artifact files exist in MinIO (sample check)
-- This requires application-level validation, not just SQL
-- Use: SELECT run_id, artifact_reference FROM backtest_runtime_runs 
--      WHERE artifact_reference IS NOT NULL LIMIT 100;
-- Then verify each artifact_reference exists in MinIO

-- Query 12: Check for orphaned artifacts (artifacts without DB reference)
-- This requires querying MinIO and comparing with DB
-- Not a SQL query, but a validation step

-- Query 13: Verify task_commands can be joined with task_runs
SELECT 
    tc.id as command_id,
    tc.idempotency_key,
    tc.status as command_status,
    tr.id as run_id,
    tr.status as run_status,
    tr.command_id as run_command_id
FROM task_commands tc
LEFT JOIN task_runs tr ON tc.id = tr.command_id
WHERE tc.idempotency_key LIKE 'backtest-%'
ORDER BY tc.created_at DESC
LIMIT 100;

-- Query 14: Check for duplicate idempotency keys
SELECT 
    idempotency_key,
    COUNT(*) as count,
    MIN(created_at) as first_created,
    MAX(created_at) as last_created
FROM task_commands
GROUP BY idempotency_key
HAVING COUNT(*) > 1
ORDER BY count DESC;
-- Expected: 0 duplicates (idempotency should prevent this)

-- ============================================================================
-- SECTION 5: PERFORMANCE MONITORING
-- ============================================================================

-- Query 15: Average JSON size per run
SELECT 
    AVG(jsonb_byte_length(trades_json) + 
        jsonb_byte_length(position_snapshots_json) + 
        jsonb_byte_length(daily_pnl_json)) / 1024.0 as avg_size_kb
FROM backtest_runtime_runs
WHERE jsonb_byte_length(trades_json) > 0 
   OR jsonb_byte_length(position_snapshots_json) > 0
   OR jsonb_byte_length(daily_pnl_json) > 0;

-- Query 16: Table size before/after migration
SELECT 
    pg_size_pretty(pg_total_relation_size('backtest_runtime_runs')) as table_size,
    pg_size_pretty(pg_total_relation_size('backtest_run_requests')) as requests_size;

-- Query 17: Index sizes for JSON columns
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes
WHERE tablename = 'backtest_runtime_runs'
  AND indexdef LIKE '%json%';

-- ============================================================================
-- SECTION 6: CLEANUP VERIFICATION (After Dropping Columns)
-- ============================================================================

-- Query 18: Verify columns are dropped
SELECT 
    column_name
FROM information_schema.columns
WHERE table_name = 'backtest_runtime_runs'
  AND column_name IN ('trades_json', 'position_snapshots_json', 'daily_pnl_json');
-- Expected: 0 rows (columns no longer exist)

-- Query 19: Verify read paths still work
-- Run application-level tests to ensure:
-- 1. Backtest runs can be read
-- 2. Trades can be accessed (from artifacts)
-- 3. Position snapshots can be accessed (from artifacts)
-- 4. Daily PnL can be accessed (from artifacts)
