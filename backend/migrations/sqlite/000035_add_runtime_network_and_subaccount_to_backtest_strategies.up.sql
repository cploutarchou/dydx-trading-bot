ALTER TABLE backtest_strategies
    ADD COLUMN runtime_network TEXT NOT NULL DEFAULT 'testnet';

ALTER TABLE backtest_strategies
    ADD COLUMN runtime_subaccount INTEGER NOT NULL DEFAULT 0;
