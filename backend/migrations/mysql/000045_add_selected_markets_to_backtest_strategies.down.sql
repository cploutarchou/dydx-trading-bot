-- Rollback: Drop selected_markets column
ALTER TABLE backtest_strategies
  DROP COLUMN IF EXISTS selected_markets;
