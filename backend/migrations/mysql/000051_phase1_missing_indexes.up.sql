-- Migration 000051: Phase 1 — Add missing performance indexes (MySQL/MariaDB version)

-- ─────────────────────────────────────────────────────────────────────────────
-- bot_trades: composite covering index for trade history queries per bot
-- Replaces full-table sequential scan on: SELECT ... WHERE bot_instance_id = ? ORDER BY entry_timestamp DESC
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bot_trades_bot_time
    ON bot_trades (bot_instance_id, entry_timestamp DESC);

-- Composite for exit-time queries (closed trade analysis, PnL reporting)
-- Note: MariaDB doesn't support DESC in multi-column indexes, so we use ASC
-- Application layer should handle DESC ordering if needed
CREATE INDEX IF NOT EXISTS idx_bot_trades_bot_exit
    ON bot_trades (bot_instance_id, exit_timestamp);

-- ─────────────────────────────────────────────────────────────────────────────
-- bot_positions: composite for open/closed position queries per bot
-- Replaces two separate index scans on: WHERE bot_instance_id = ? AND status = ?
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bot_positions_bot_status
    ON bot_positions (bot_instance_id, status);

-- ─────────────────────────────────────────────────────────────────────────────
-- security_login_events: composite for login history per user ordered by time
-- More selective than separate (user_id) + (created_at) indexes for combined predicates
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_security_login_user_time
    ON security_login_events (user_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- audit_logs: composite for audit trail queries per user over time
-- Covers: SELECT ... WHERE user_id = ? ORDER BY created_at DESC LIMIT n
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_time
    ON audit_logs (user_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- backtest_runs: triple composite for user dashboard backtest listing
-- Covers: SELECT ... WHERE user_id = ? AND status = ? ORDER BY created_at DESC
-- Already have idx_backtest_runs_user_created (user_id, created_at DESC);
-- this adds status as a filter column for dashboard status-tab queries.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_backtest_runs_user_status_time
    ON backtest_runs (user_id, status, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- backtest_strategies: FULLTEXT index on selected_markets (JSON array)
-- MariaDB doesn't support GIN indexes like legacy, but FULLTEXT can be used for JSON search.
-- For better JSON array search, consider using JSON_CONTAINS() with BTREE index on parent rows.
-- Alternative: Use BTREE index if JSON_EXTRACT performance is acceptable
-- ─────────────────────────────────────────────────────────────────────────────
-- Note: FULLTEXT indexes require MATCH() operators, so we use BTREE for general purpose
CREATE INDEX IF NOT EXISTS idx_strategy_selected_markets
    ON backtest_strategies (selected_markets(50));
