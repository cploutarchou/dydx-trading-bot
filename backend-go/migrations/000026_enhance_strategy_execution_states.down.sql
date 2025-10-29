-- Migration 000026 Down: Revert Strategy Execution State enhancements

DROP INDEX IF EXISTS idx_strategy_execution_states_status;
DROP INDEX IF EXISTS idx_strategy_execution_states_strategy_id;

ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS win_rate;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS sharpe_ratio;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS max_drawdown;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS open_positions_count;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS active_pairs_count;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS last_cointegration_check;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS uptime_seconds;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS last_trade_at;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS last_stopped;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS last_started;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS config_snapshot;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS last_error_at;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS error_count;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS last_error;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS pnl_pct;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS pnl;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS trades_executed;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS status;
ALTER TABLE strategy_execution_states DROP COLUMN IF NOT EXISTS enabled;

