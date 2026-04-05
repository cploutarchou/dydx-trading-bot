ALTER TABLE backtest_strategies
ADD COLUMN IF NOT EXISTS runtime_strategy TEXT NOT NULL DEFAULT 'cointegration';
