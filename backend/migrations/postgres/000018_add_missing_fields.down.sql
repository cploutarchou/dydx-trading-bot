-- Migration 000018 Down: Revert updated_at column from backtest_results table

-- Drop indexes
DROP INDEX IF EXISTS idx_backtest_results_updated_at;

-- Historical rollback posture: keep the updated_at column and only drop the
-- companion index, because the column presence is non-breaking.

