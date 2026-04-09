ALTER TABLE backtest_strategies
    ADD COLUMN IF NOT EXISTS runtime_network TEXT NOT NULL DEFAULT 'testnet';

ALTER TABLE backtest_strategies
    ADD COLUMN IF NOT EXISTS runtime_subaccount INTEGER NOT NULL DEFAULT 0;
