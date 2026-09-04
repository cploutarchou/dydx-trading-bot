-- Reverts Phase 2 money columns to REAL. Values beyond float4 precision
-- (~6 significant digits) are lost on the way back down.
ALTER TABLE backtest_runs
    ALTER COLUMN total_pnl TYPE REAL USING total_pnl::REAL,
    ALTER COLUMN total_pnl_usd TYPE REAL USING total_pnl_usd::REAL,
    ALTER COLUMN starting_balance TYPE REAL USING starting_balance::REAL,
    ALTER COLUMN ending_balance TYPE REAL USING ending_balance::REAL,
    ALTER COLUMN max_balance TYPE REAL USING max_balance::REAL,
    ALTER COLUMN min_balance TYPE REAL USING min_balance::REAL;

ALTER TABLE backtest_trades
    ALTER COLUMN entry_price_1 TYPE REAL USING entry_price_1::REAL,
    ALTER COLUMN entry_price_2 TYPE REAL USING entry_price_2::REAL,
    ALTER COLUMN size_1 TYPE REAL USING size_1::REAL,
    ALTER COLUMN size_2 TYPE REAL USING size_2::REAL,
    ALTER COLUMN exit_price_1 TYPE REAL USING exit_price_1::REAL,
    ALTER COLUMN exit_price_2 TYPE REAL USING exit_price_2::REAL,
    ALTER COLUMN pnl TYPE REAL USING pnl::REAL,
    ALTER COLUMN transaction_fee TYPE REAL USING transaction_fee::REAL,
    ALTER COLUMN slippage TYPE REAL USING slippage::REAL;

ALTER TABLE backtest_positions
    ALTER COLUMN entry_price_1 TYPE REAL USING entry_price_1::REAL,
    ALTER COLUMN entry_price_2 TYPE REAL USING entry_price_2::REAL,
    ALTER COLUMN size_1 TYPE REAL USING size_1::REAL,
    ALTER COLUMN size_2 TYPE REAL USING size_2::REAL,
    ALTER COLUMN current_price_1 TYPE REAL USING current_price_1::REAL,
    ALTER COLUMN current_price_2 TYPE REAL USING current_price_2::REAL,
    ALTER COLUMN unrealized_pnl TYPE REAL USING unrealized_pnl::REAL,
    ALTER COLUMN realized_pnl TYPE REAL USING realized_pnl::REAL;
