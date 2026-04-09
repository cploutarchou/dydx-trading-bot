ALTER TABLE backtest_strategies
    DROP COLUMN IF EXISTS runtime_subaccount;

ALTER TABLE backtest_strategies
    DROP COLUMN IF EXISTS runtime_network;
