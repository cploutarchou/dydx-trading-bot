-- Migration 000024: Enhance Backtest Trades with strategy fields
-- Synchronize with Python SQLModel BacktestTrade schema

ALTER TABLE backtest_trades ADD COLUMN IF NOT EXISTS strategy_id INTEGER NULL;
ALTER TABLE backtest_trades ADD COLUMN IF NOT EXISTS strategy_name VARCHAR(100) NULL;
ALTER TABLE backtest_trades ADD COLUMN IF NOT EXISTS strategy_zscore_threshold REAL NULL;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_backtest_trades_market_1 ON backtest_trades(market_1);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_market_2 ON backtest_trades(market_2);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_strategy_id ON backtest_trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_entry_timestamp ON backtest_trades(entry_timestamp);

