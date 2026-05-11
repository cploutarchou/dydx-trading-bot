-- Migration 000056: Performance compound indexes
-- Adds covering indexes for the most frequent query patterns that are not yet
-- covered by prior migrations.  All use transaction-safe CREATE INDEX IF NOT
-- EXISTS (no CONCURRENTLY) so they work inside the golang-migrate startup flow.
-- ─────────────────────────────────────────────────────────────────────────────
-- backtest_runs: partial index for active runs
-- Covers: SELECT ... WHERE user_id = ? AND status IN ('running','pending','started')
-- This is a small, frequently-queried set — a partial index keeps it tight.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_backtest_runs_active ON backtest_runs (user_id, created_at DESC)
WHERE
	status IN ('running', 'pending', 'started');

-- ─────────────────────────────────────────────────────────────────────────────
-- bot_instances: composite for dashboard list queries filtered by status
-- Covers: SELECT ... WHERE user_id = ? AND status = ? ORDER BY created_at DESC
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bot_instances_user_status ON bot_instances (user_id, status);

-- ─────────────────────────────────────────────────────────────────────────────
-- bot_trades: composite ordered by created_at (used by trade history pages)
-- Complements existing idx_bot_trades_bot_time (entry_timestamp) for queries
-- that sort by insertion time rather than trade entry time.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bot_trades_instance_created ON bot_trades (bot_instance_id, created_at DESC);