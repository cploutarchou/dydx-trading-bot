-- Rollback for 000053_phase4_drop_redundant_indexes
-- Re-creates all dropped indexes. These are non-CONCURRENTLY (rollback context may be in a transaction).
-- In production, prefer running each CREATE CONCURRENTLY manually after taking the migration down.

-- users
CREATE INDEX IF NOT EXISTS ix_users_id         ON users (id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email    ON users (email);

-- audit_logs
CREATE INDEX IF NOT EXISTS ix_audit_logs_id      ON audit_logs (id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id);

-- backtest_runs
CREATE INDEX IF NOT EXISTS ix_backtest_runs_id      ON backtest_runs (id);
CREATE INDEX IF NOT EXISTS ix_backtest_runs_user_id ON backtest_runs (user_id);
CREATE INDEX IF NOT EXISTS idx_run_user_created     ON backtest_runs (user_id, created_at DESC);

-- strategy_execution_states
CREATE INDEX IF NOT EXISTS ix_strategy_execution_states_id          ON strategy_execution_states (id);
CREATE INDEX IF NOT EXISTS ix_strategy_execution_states_strategy_id ON strategy_execution_states (strategy_id);
CREATE INDEX IF NOT EXISTS idx_execution_state_updated              ON strategy_execution_states (updated_at);

-- strategy_version_history
CREATE INDEX IF NOT EXISTS ix_strategy_version_history_id          ON strategy_version_history (id);
CREATE INDEX IF NOT EXISTS ix_strategy_version_history_strategy_id ON strategy_version_history (strategy_id);

-- backtest_strategies
CREATE INDEX IF NOT EXISTS ix_backtest_strategies_id ON backtest_strategies (id);

-- dydx_keys
CREATE INDEX IF NOT EXISTS ix_dydx_keys_id      ON dydx_keys (id);
CREATE INDEX IF NOT EXISTS ix_dydx_keys_user_id ON dydx_keys (user_id);

-- bot_settings
CREATE INDEX IF NOT EXISTS ix_bot_settings_id          ON bot_settings (id);
CREATE INDEX IF NOT EXISTS idx_bot_setting_section_key ON bot_settings (section, key);
