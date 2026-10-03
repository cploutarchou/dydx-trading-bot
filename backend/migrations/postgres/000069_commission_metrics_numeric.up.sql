-- Phase 1 of the money-precision migration (TASK-039): the payout-critical
-- partner commission columns move from DOUBLE PRECISION (binary float, loses
-- cents when summed) to NUMERIC(20,8). Existing values convert losslessly for
-- realistic magnitudes; Go models continue scanning into float64.
--
-- Phase 2 (backtest_runs/bot_trades/bot_positions REAL columns) is deferred
-- until it can be rehearsed against a production-sized snapshot.
ALTER TABLE partner_commission_metrics
    ALTER COLUMN notional_volume_usd TYPE NUMERIC(20,8) USING notional_volume_usd::NUMERIC(20,8),
    ALTER COLUMN gross_commission_usd TYPE NUMERIC(20,8) USING gross_commission_usd::NUMERIC(20,8),
    ALTER COLUMN rebate_usd TYPE NUMERIC(20,8) USING rebate_usd::NUMERIC(20,8),
    ALTER COLUMN net_commission_usd TYPE NUMERIC(20,8) USING net_commission_usd::NUMERIC(20,8);
