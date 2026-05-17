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

-- Historical rollback posture: keep strategy columns on backtest_trades.
-- Their presence is non-breaking after backtest_metrics is dropped.

