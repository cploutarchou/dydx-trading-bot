-- Migration 000053: Phase 4 — Drop confirmed-redundant indexes
-- Source: DBA audit report 2026-05-01, Section 3.1
--
-- ⚠️  PREREQUISITE: Verify idx_scan = 0 for ALL indexes listed below via pg_stat_user_indexes
--     over a representative window of ≥ 2 weeks on the LIVE database before applying.
--     Sample query:
--       SELECT indexname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS size
--       FROM pg_stat_user_indexes
--       WHERE indexname IN (
--           'ix_users_id', 'ix_users_username', 'ix_users_email',
--           'ix_audit_logs_id', 'ix_audit_logs_user_id',
--           'ix_backtest_runs_id', 'ix_backtest_runs_user_id',
--           'idx_run_user_created',
--           'ix_strategy_execution_states_id',
--           'idx_execution_state_updated',
--           'ix_strategy_version_history_id',
--           'ix_strategy_version_history_strategy_id'
--       )
--       ORDER BY idx_scan DESC;
--
-- Uses transaction-safe DROP INDEX IF EXISTS for golang-migrate compatibility.
-- Rollback: 000053_phase4_drop_redundant_indexes.down.sql re-creates them.

-- ─────────────────────────────────────────────────────────────────────────────
-- users table — 3 redundant indexes
-- users_username_key (from UNIQUE column constraint) covers ix_users_username
-- users_email_key    (from UNIQUE column constraint) covers ix_users_email
-- PK index on id covers ix_users_id
-- ─────────────────────────────────────────────────────────────────────────────
DROP INDEX IF EXISTS ix_users_id;
DROP INDEX IF EXISTS ix_users_username;
DROP INDEX IF EXISTS ix_users_email;

-- ─────────────────────────────────────────────────────────────────────────────
-- audit_logs — 2 redundant indexes
-- idx_audit_user_action (user_id, action) covers ix_audit_logs_user_id
-- PK index covers ix_audit_logs_id
-- ─────────────────────────────────────────────────────────────────────────────
DROP INDEX IF EXISTS ix_audit_logs_id;
DROP INDEX IF EXISTS ix_audit_logs_user_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- backtest_runs — 3 redundant indexes
-- backtest_runs_run_id_key (UNIQUE constraint) covers ix_backtest_runs_run_id
-- idx_backtest_runs_user_created (user_id, created_at) covers ix_backtest_runs_user_id
-- idx_run_user_created is a duplicate of idx_backtest_runs_user_created
-- PK covers ix_backtest_runs_id
-- ─────────────────────────────────────────────────────────────────────────────
DROP INDEX IF EXISTS ix_backtest_runs_id;
DROP INDEX IF EXISTS ix_backtest_runs_user_id;
DROP INDEX IF EXISTS idx_run_user_created;

-- ─────────────────────────────────────────────────────────────────────────────
-- strategy_execution_states — 3 redundant indexes
-- PK covers ix_strategy_execution_states_id
-- unique constraint + composite indexes cover ix_strategy_execution_states_strategy_id
-- idx_execution_state_updated duplicates ix_strategy_execution_states_updated_at
-- ─────────────────────────────────────────────────────────────────────────────
DROP INDEX IF EXISTS ix_strategy_execution_states_id;
DROP INDEX IF EXISTS ix_strategy_execution_states_strategy_id;
DROP INDEX IF EXISTS idx_execution_state_updated;

-- ─────────────────────────────────────────────────────────────────────────────
-- strategy_version_history — 2 redundant indexes
-- PK covers ix_strategy_version_history_id
-- idx_strategy_version (strategy_id, version_number) covers ix_strategy_version_history_strategy_id
-- ─────────────────────────────────────────────────────────────────────────────
DROP INDEX IF EXISTS ix_strategy_version_history_id;
DROP INDEX IF EXISTS ix_strategy_version_history_strategy_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- backtest_strategies — 1 redundant index
-- PK covers ix_backtest_strategies_id
-- ─────────────────────────────────────────────────────────────────────────────
DROP INDEX IF EXISTS ix_backtest_strategies_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- dydx_keys — 2 redundant indexes
-- PK covers ix_dydx_keys_id
-- dydx_keys_user_id_network_key (UNIQUE user_id, network) covers ix_dydx_keys_user_id
-- ─────────────────────────────────────────────────────────────────────────────
DROP INDEX IF EXISTS ix_dydx_keys_id;
DROP INDEX IF EXISTS ix_dydx_keys_user_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- bot_settings — 2 redundant indexes
-- PK covers ix_bot_settings_id
-- bot_settings_section_key_key (UNIQUE section, key) covers idx_bot_setting_section_key
-- ─────────────────────────────────────────────────────────────────────────────
DROP INDEX IF EXISTS ix_bot_settings_id;
DROP INDEX IF EXISTS idx_bot_setting_section_key;
