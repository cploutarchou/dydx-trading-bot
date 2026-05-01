-- Rollback for 000051_phase1_missing_indexes
DROP INDEX IF EXISTS idx_bot_trades_bot_time;
DROP INDEX IF EXISTS idx_bot_trades_bot_exit;
DROP INDEX IF EXISTS idx_bot_positions_bot_status;
DROP INDEX IF EXISTS idx_security_login_user_time;
DROP INDEX IF EXISTS idx_audit_logs_user_time;
DROP INDEX IF EXISTS idx_backtest_runs_user_status_time;
DROP INDEX IF EXISTS idx_strategy_selected_markets_gin;
