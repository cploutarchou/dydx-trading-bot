-- Migration 000019 Down: Revert strategy fields and backtest_metrics table

-- Drop indexes
DROP INDEX IF EXISTS idx_backtest_trades_strategy_id;
DROP INDEX IF EXISTS idx_backtest_trades_strategy_name;
DROP INDEX IF EXISTS idx_backtest_metrics_run_id;
DROP INDEX IF EXISTS idx_backtest_metrics_created_at;
DROP INDEX IF EXISTS idx_backtest_metrics_total_pnl;
DROP INDEX IF EXISTS idx_backtest_metrics_sharpe_ratio;

-- Drop backtest_metrics table
DROP TABLE IF EXISTS backtest_metrics;

-- Note: SQLite doesn't support dropping columns easily
-- The strategy_id, strategy_name, and strategy_zscore_threshold columns would remain
-- If full rollback is needed, backtest_trades table would need to be recreated

