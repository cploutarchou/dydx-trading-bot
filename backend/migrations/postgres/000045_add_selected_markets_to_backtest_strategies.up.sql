ALTER TABLE backtest_strategies
  ADD COLUMN IF NOT EXISTS selected_markets JSONB NOT NULL DEFAULT '[]'::jsonb;

