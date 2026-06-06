ALTER TABLE backtest_strategies
ADD COLUMN IF NOT EXISTS pair_selection_mode TEXT NOT NULL DEFAULT 'liquidity';

UPDATE backtest_strategies
SET pair_selection_mode = 'liquidity'
WHERE pair_selection_mode IS NULL OR TRIM(pair_selection_mode) = '';
