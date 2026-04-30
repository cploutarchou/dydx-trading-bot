-- Index to speed up GET /api/v1/backtests which orders by created_at DESC per user.
-- This replaces a full-table sequential scan with an efficient index scan.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtest_runs_user_created
    ON backtest_runs (user_id, created_at DESC);
