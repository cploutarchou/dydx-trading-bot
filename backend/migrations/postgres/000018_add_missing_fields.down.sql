-- Migration 000018 Down: Revert updated_at column from backtest_results table

-- Drop indexes
DROP INDEX IF EXISTS idx_backtest_results_updated_at;

-- Note: SQLite doesn't support dropping columns easily
-- The updated_at column would need manual table recreation if full rollback is required
-- For now, just drop the index as the column presence won't cause issues

