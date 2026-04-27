ALTER TABLE backtest_strategies
  ADD COLUMN selected_markets TEXT NOT NULL DEFAULT '[]';

