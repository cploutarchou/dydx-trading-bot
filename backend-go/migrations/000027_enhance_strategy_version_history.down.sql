-- Migration 000027 Down: Revert Strategy Version History enhancements

DROP INDEX IF EXISTS idx_strategy_version_history_created_at;
DROP INDEX IF EXISTS idx_strategy_version_history_created_by_user_id;
DROP INDEX IF EXISTS idx_strategy_version_history_strategy_id;

ALTER TABLE strategy_version_history DROP COLUMN IF NOT EXISTS average_backtest_pnl;
ALTER TABLE strategy_version_history DROP COLUMN IF NOT EXISTS best_backtest_pnl;
ALTER TABLE strategy_version_history DROP COLUMN IF NOT EXISTS backtest_count;
ALTER TABLE strategy_version_history DROP COLUMN IF NOT EXISTS changes;
ALTER TABLE strategy_version_history DROP COLUMN IF NOT EXISTS config_snapshot;
ALTER TABLE strategy_version_history DROP COLUMN IF NOT EXISTS change_description;
ALTER TABLE strategy_version_history DROP COLUMN IF NOT EXISTS version_number;

