-- Migration 000051: Phase 1 — Add missing performance indexes
-- Source: DBA audit report 2026-05-01
-- All indexes use CONCURRENTLY + IF NOT EXISTS: no table lock, zero downtime, safe to run on live DB.
-- Rollback: 000051_phase1_missing_indexes.down.sql

-- ─────────────────────────────────────────────────────────────────────────────
-- bot_trades: composite covering index for trade history queries per bot
-- Replaces full-table sequential scan on: SELECT ... WHERE bot_instance_id = ? ORDER BY entry_timestamp DESC
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bot_trades_bot_time
    ON bot_trades (bot_instance_id, entry_timestamp DESC);

-- Composite for exit-time queries (closed trade analysis, PnL reporting)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bot_trades_bot_exit
    ON bot_trades (bot_instance_id, exit_timestamp DESC NULLS FIRST);

-- ─────────────────────────────────────────────────────────────────────────────
-- bot_positions: composite for open/closed position queries per bot
-- Replaces two separate index scans on: WHERE bot_instance_id = ? AND status = ?
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bot_positions_bot_status
    ON bot_positions (bot_instance_id, status);

-- ─────────────────────────────────────────────────────────────────────────────
-- security_login_events: composite for login history per user ordered by time
-- More selective than separate (user_id) + (created_at) indexes for combined predicates
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_security_login_user_time
    ON security_login_events (user_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- audit_logs: composite for audit trail queries per user over time
-- Covers: SELECT ... WHERE user_id = ? ORDER BY created_at DESC LIMIT n
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_user_time
    ON audit_logs (user_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- backtest_runs: triple composite for user dashboard backtest listing
-- Covers: SELECT ... WHERE user_id = ? AND status = ? ORDER BY created_at DESC
-- Already have idx_backtest_runs_user_created (user_id, created_at DESC);
-- this adds status as a filter column for dashboard status-tab queries.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtest_runs_user_status_time
    ON backtest_runs (user_id, status, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- backtest_strategies: GIN index on selected_markets (JSONB array)
-- Required for any query filtering strategies by market name inside the array.
-- Without this, every such query performs a full table scan.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_strategy_selected_markets_gin
    ON backtest_strategies USING gin (selected_markets);
