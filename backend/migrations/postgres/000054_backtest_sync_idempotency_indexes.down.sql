-- Rollback for 000054_backtest_sync_idempotency_indexes.up.sql

DROP INDEX IF EXISTS uq_backtest_candles_sync_key_fk;
DROP INDEX IF EXISTS uq_backtest_candles_sync_key_legacy;
DROP INDEX IF EXISTS uq_backtest_positions_position_id_sync;
DROP INDEX IF EXISTS uq_backtest_trades_trade_id_sync;

-- Revert strict candle default/not-null constraint introduced by up migration.
ALTER TABLE backtest_candles
    ALTER COLUMN resolution DROP NOT NULL,
    ALTER COLUMN resolution DROP DEFAULT;
