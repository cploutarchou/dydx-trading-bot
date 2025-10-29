-- Migration 000027: Enhance Strategy Version History with all fields
-- Synchronize with Python SQLModel StrategyVersionHistory schema

ALTER TABLE strategy_version_history ADD COLUMN IF NOT EXISTS version_number INTEGER NULL;
ALTER TABLE strategy_version_history ADD COLUMN IF NOT EXISTS change_description VARCHAR(500) NULL;
ALTER TABLE strategy_version_history ADD COLUMN IF NOT EXISTS config_snapshot TEXT NULL;
ALTER TABLE strategy_version_history ADD COLUMN IF NOT EXISTS changes TEXT NULL;
ALTER TABLE strategy_version_history ADD COLUMN IF NOT EXISTS backtest_count INTEGER NULL;
ALTER TABLE strategy_version_history ADD COLUMN IF NOT EXISTS best_backtest_pnl REAL NULL;
ALTER TABLE strategy_version_history ADD COLUMN IF NOT EXISTS average_backtest_pnl REAL NULL;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_strategy_version_history_strategy_id ON strategy_version_history(strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategy_version_history_created_by_user_id ON strategy_version_history(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_strategy_version_history_created_at ON strategy_version_history(created_at);

