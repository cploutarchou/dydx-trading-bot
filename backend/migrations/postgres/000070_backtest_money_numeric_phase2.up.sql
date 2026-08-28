-- Phase 2 of the money-precision migration (TASK-039): converts the remaining
-- REAL (float4, ~6 significant digits) money columns to NUMERIC(20,8).
--
-- STATUS: WRITTEN BUT NOT REHEARSED — this migration rewrites the largest
-- tables in the system (backtest_runs/backtest_trades/backtest_positions).
-- Rehearse against a production-sized snapshot before enabling in
-- deployment: measure ALTER duration, lock time, and disk headroom, and run
-- during a low-traffic window. Values convert via ::NUMERIC and carry their
-- stored precision forward unchanged; Go models continue scanning float64.
--
-- Deferred sub-phase: bot_trades/bot_positions DOUBLE PRECISION columns can
-- follow the same pattern once this one is proven.

ALTER TABLE backtest_runs
    ALTER COLUMN total_pnl TYPE NUMERIC(20,8) USING total_pnl::NUMERIC(20,8),
    ALTER COLUMN total_pnl_usd TYPE NUMERIC(20,8) USING total_pnl_usd::NUMERIC(20,8),
    ALTER COLUMN starting_balance TYPE NUMERIC(20,8) USING starting_balance::NUMERIC(20,8),
    ALTER COLUMN ending_balance TYPE NUMERIC(20,8) USING ending_balance::NUMERIC(20,8),
    ALTER COLUMN max_balance TYPE NUMERIC(20,8) USING max_balance::NUMERIC(20,8),
    ALTER COLUMN min_balance TYPE NUMERIC(20,8) USING min_balance::NUMERIC(20,8);

ALTER TABLE backtest_trades
    ALTER COLUMN entry_price_1 TYPE NUMERIC(20,8) USING entry_price_1::NUMERIC(20,8),
    ALTER COLUMN entry_price_2 TYPE NUMERIC(20,8) USING entry_price_2::NUMERIC(20,8),
    ALTER COLUMN size_1 TYPE NUMERIC(20,8) USING size_1::NUMERIC(20,8),
    ALTER COLUMN size_2 TYPE NUMERIC(20,8) USING size_2::NUMERIC(20,8),
    ALTER COLUMN exit_price_1 TYPE NUMERIC(20,8) USING exit_price_1::NUMERIC(20,8),
    ALTER COLUMN exit_price_2 TYPE NUMERIC(20,8) USING exit_price_2::NUMERIC(20,8),
    ALTER COLUMN pnl TYPE NUMERIC(20,8) USING pnl::NUMERIC(20,8),
    ALTER COLUMN pnl_usd TYPE NUMERIC(20,8) USING pnl_usd::NUMERIC(20,8),
    ALTER COLUMN transaction_fee TYPE NUMERIC(20,8) USING transaction_fee::NUMERIC(20,8),
    ALTER COLUMN slippage TYPE NUMERIC(20,8) USING slippage::NUMERIC(20,8);

ALTER TABLE backtest_positions
    ALTER COLUMN entry_price_1 TYPE NUMERIC(20,8) USING entry_price_1::NUMERIC(20,8),
    ALTER COLUMN entry_price_2 TYPE NUMERIC(20,8) USING entry_price_2::NUMERIC(20,8),
    ALTER COLUMN size_1 TYPE NUMERIC(20,8) USING size_1::NUMERIC(20,8),
    ALTER COLUMN size_2 TYPE NUMERIC(20,8) USING size_2::NUMERIC(20,8),
    ALTER COLUMN current_price_1 TYPE NUMERIC(20,8) USING current_price_1::NUMERIC(20,8),
    ALTER COLUMN current_price_2 TYPE NUMERIC(20,8) USING current_price_2::NUMERIC(20,8),
    ALTER COLUMN unrealized_pnl TYPE NUMERIC(20,8) USING unrealized_pnl::NUMERIC(20,8),
    ALTER COLUMN realized_pnl TYPE NUMERIC(20,8) USING realized_pnl::NUMERIC(20,8);
