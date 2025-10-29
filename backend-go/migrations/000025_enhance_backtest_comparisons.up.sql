-- Migration 000025: Enhance Backtest Comparison with all fields
-- Synchronize with Python SQLModel BacktestComparison schema

ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS name VARCHAR(100) NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS description VARCHAR(500) NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS run_id_1 INTEGER NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS run_id_2 INTEGER NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS strategy_id_1 INTEGER NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS strategy_id_2 INTEGER NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS winner_run_id INTEGER NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS pnl_difference REAL NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS sharpe_difference REAL NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS win_rate_difference REAL NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS drawdown_difference REAL NULL;
ALTER TABLE backtest_comparisons ADD COLUMN IF NOT EXISTS comparison_metrics TEXT NULL;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_backtest_comparisons_user_id ON backtest_comparisons(user_id);
CREATE INDEX IF NOT EXISTS idx_backtest_comparisons_strategy_1 ON backtest_comparisons(strategy_id_1);
CREATE INDEX IF NOT EXISTS idx_backtest_comparisons_strategy_2 ON backtest_comparisons(strategy_id_2);

