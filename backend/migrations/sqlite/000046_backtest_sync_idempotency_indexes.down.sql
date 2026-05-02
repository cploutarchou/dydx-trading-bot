-- Rollback for 000046_backtest_sync_idempotency_indexes.up.sql

DROP INDEX IF EXISTS uq_backtest_candles_sync_key_fk;
DROP INDEX IF EXISTS uq_backtest_positions_position_id_sync;
DROP INDEX IF EXISTS uq_backtest_trades_trade_id_sync;
