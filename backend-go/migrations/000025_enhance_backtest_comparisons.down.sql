-- Migration 000025 Down: Revert Backtest Comparison enhancements

DROP INDEX IF EXISTS idx_backtest_comparisons_strategy_2;
DROP INDEX IF EXISTS idx_backtest_comparisons_strategy_1;
DROP INDEX IF EXISTS idx_backtest_comparisons_user_id;

ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS comparison_metrics;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS drawdown_difference;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS win_rate_difference;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS sharpe_difference;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS pnl_difference;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS winner_run_id;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS strategy_id_2;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS strategy_id_1;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS run_id_2;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS run_id_1;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS description;
ALTER TABLE backtest_comparisons DROP COLUMN IF NOT EXISTS name;

