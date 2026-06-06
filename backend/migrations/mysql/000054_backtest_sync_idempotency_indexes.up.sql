-- Migration 000054: Backtest sync idempotency indexes for distributed-safe UPSERT
-- Purpose:
--   1) Remove accidental duplicate rows in child sync tables.
--   2) Enforce unique keys used by repository UPSERT paths.
--
-- Notes:
-- - Transaction-safe statements only (no CONCURRENTLY).
-- - Existing schemas already enforce unique trade_id/position_id in many environments,
--   but these indexes guarantee the contract for drifted databases.

-- -----------------------------------------------------------------------------
-- Normalize nullable candle resolution so unique key semantics are deterministic.
-- -----------------------------------------------------------------------------
UPDATE backtest_candles
SET resolution = '1HOUR'
WHERE resolution IS NULL OR btrim(resolution) = '';

ALTER TABLE backtest_candles
    ALTER COLUMN resolution SET DEFAULT '1HOUR',
    ALTER COLUMN resolution SET NOT NULL;

-- -----------------------------------------------------------------------------
-- Deduplicate trade_id and position_id by keeping the newest row.
-- -----------------------------------------------------------------------------
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY trade_id ORDER BY id DESC) AS rn
    FROM backtest_trades
)
DELETE FROM backtest_trades t
USING ranked r
WHERE t.id = r.id
  AND r.rn > 1;

WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY position_id ORDER BY id DESC) AS rn
    FROM backtest_positions
)
DELETE FROM backtest_positions p
USING ranked r
WHERE p.id = r.id
  AND r.rn > 1;

-- -----------------------------------------------------------------------------
-- Deduplicate candles by natural key. Handle both run_id_fk and legacy run_id
-- schemas to preserve compatibility.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'backtest_candles'
          AND column_name = 'run_id_fk'
    ) THEN
        EXECUTE '
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY run_id_fk, market, timestamp, resolution
                           ORDER BY id DESC
                       ) AS rn
                FROM backtest_candles
            )
            DELETE FROM backtest_candles c
            USING ranked r
            WHERE c.id = r.id
              AND r.rn > 1
        ';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'backtest_candles'
          AND column_name = 'run_id'
    ) THEN
        EXECUTE '
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY run_id, market, timestamp, resolution
                           ORDER BY id DESC
                       ) AS rn
                FROM backtest_candles
            )
            DELETE FROM backtest_candles c
            USING ranked r
            WHERE c.id = r.id
              AND r.rn > 1
        ';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- Enforce unique indexes consumed by UPSERT paths.
-- -----------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_backtest_trades_trade_id_sync
    ON backtest_trades (trade_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_backtest_positions_position_id_sync
    ON backtest_positions (position_id);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'backtest_candles'
          AND column_name = 'run_id_fk'
    ) THEN
        EXECUTE '
            CREATE UNIQUE INDEX IF NOT EXISTS uq_backtest_candles_sync_key_fk
            ON backtest_candles (run_id_fk, market, timestamp, resolution)
        ';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'backtest_candles'
          AND column_name = 'run_id'
    ) THEN
        EXECUTE '
            CREATE UNIQUE INDEX IF NOT EXISTS uq_backtest_candles_sync_key_legacy
            ON backtest_candles (run_id, market, timestamp, resolution)
        ';
    END IF;
END $$;
