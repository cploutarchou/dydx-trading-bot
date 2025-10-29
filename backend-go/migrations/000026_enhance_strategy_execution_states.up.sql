-- Migration 000026: Enhance Strategy Execution State with all fields
-- Synchronize with Python SQLModel StrategyExecutionState schema

ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS enabled BOOLEAN NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS status VARCHAR(20) NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS trades_executed INTEGER DEFAULT 0;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS pnl REAL NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS pnl_pct REAL NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS last_error VARCHAR(500) NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS error_count INTEGER DEFAULT 0;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMP NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS config_snapshot TEXT NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS last_started TIMESTAMP NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS last_stopped TIMESTAMP NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS last_trade_at TIMESTAMP NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS uptime_seconds INTEGER DEFAULT 0;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS last_cointegration_check TIMESTAMP NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS active_pairs_count INTEGER DEFAULT 0;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS open_positions_count INTEGER DEFAULT 0;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS max_drawdown REAL NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS sharpe_ratio REAL NULL;
ALTER TABLE strategy_execution_states ADD COLUMN IF NOT EXISTS win_rate REAL NULL;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_strategy_execution_states_strategy_id ON strategy_execution_states(strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategy_execution_states_status ON strategy_execution_states(status);

