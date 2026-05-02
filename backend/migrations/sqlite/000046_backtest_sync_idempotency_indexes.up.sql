-- Migration 000046: Backtest sync idempotency indexes for distributed-safe UPSERT

-- Normalize candle resolution for deterministic uniqueness.
UPDATE backtest_candles
SET resolution = '1HOUR'
WHERE resolution IS NULL OR trim(resolution) = '';

-- Deduplicate trade_id and position_id by keeping newest rowid.
DELETE FROM backtest_trades
WHERE rowid NOT IN (
    SELECT MAX(rowid)
    FROM backtest_trades
    GROUP BY trade_id
);

DELETE FROM backtest_positions
WHERE rowid NOT IN (
    SELECT MAX(rowid)
    FROM backtest_positions
    GROUP BY position_id
);

-- Deduplicate candles by natural key.
DELETE FROM backtest_candles
WHERE rowid NOT IN (
    SELECT MAX(rowid)
    FROM backtest_candles
    GROUP BY run_id_fk, market, timestamp, IFNULL(resolution, '1HOUR')
);

-- Enforce unique keys used by UPSERT paths.
CREATE UNIQUE INDEX IF NOT EXISTS uq_backtest_trades_trade_id_sync
    ON backtest_trades (trade_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_backtest_positions_position_id_sync
    ON backtest_positions (position_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_backtest_candles_sync_key_fk
    ON backtest_candles (run_id_fk, market, timestamp, IFNULL(resolution, '1HOUR'));
