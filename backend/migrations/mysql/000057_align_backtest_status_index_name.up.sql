-- Migration 000057: ensure canonical backtest status index exists.
-- MariaDB does not support transactional procedural DDL in this migration flow.
CREATE INDEX IF NOT EXISTS idx_backtest_runs_user_status_created
  ON backtest_runs (user_id, status, created_at DESC);
