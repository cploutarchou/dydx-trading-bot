-- Rollback: Drop performance indexes
DROP INDEX IF EXISTS idx_bot_trades_bot_time ON bot_trades;
DROP INDEX IF EXISTS idx_bot_trades_bot_exit ON bot_trades;
DROP INDEX IF EXISTS idx_bot_positions_bot_status ON bot_positions;
DROP INDEX IF EXISTS idx_security_login_user_time ON security_login_events;
DROP INDEX IF EXISTS idx_audit_logs_user_time ON audit_logs;
DROP INDEX IF EXISTS idx_backtest_runs_user_status_time ON backtest_runs;
DROP INDEX IF EXISTS idx_strategy_selected_markets ON backtest_strategies;
