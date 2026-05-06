-- Rollback for 000056: drop compound performance indexes
DROP INDEX IF EXISTS idx_backtest_runs_active;

DROP INDEX IF EXISTS idx_bot_instances_user_status;

DROP INDEX IF EXISTS idx_bot_trades_instance_created;