-- Migration 000024 Down: Revert Backtest Trades enhancements

DROP INDEX IF EXISTS idx_backtest_trades_entry_timestamp;
DROP INDEX IF EXISTS idx_backtest_trades_strategy_id;
DROP INDEX IF EXISTS idx_backtest_trades_market_2;
DROP INDEX IF EXISTS idx_backtest_trades_market_1;

ALTER TABLE backtest_trades DROP COLUMN IF NOT EXISTS strategy_zscore_threshold;
ALTER TABLE backtest_trades DROP COLUMN IF NOT EXISTS strategy_name;
ALTER TABLE backtest_trades DROP COLUMN IF NOT EXISTS strategy_id;

