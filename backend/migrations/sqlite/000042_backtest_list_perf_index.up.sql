-- Index to speed up GET /api/v1/backtests which orders by created_at DESC per user.
-- SQLite does not support CONCURRENTLY; the index is created synchronously.
CREATE INDEX IF NOT EXISTS idx_backtest_runs_user_created
    ON backtest_runs (user_id, created_at DESC);
