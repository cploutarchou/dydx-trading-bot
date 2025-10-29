-- Migration 000029 Down: Revert Trade Log enhancements

DROP INDEX IF EXISTS idx_trade_logs_created_at;
DROP INDEX IF EXISTS idx_trade_logs_entry_timestamp;
DROP INDEX IF EXISTS idx_trade_logs_result_id;

ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS exit_zscore;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS entry_zscore;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS pnl_usd;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS pnl;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS side_2;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS side_1;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS quantity_2;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS quantity_1;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS exit_price_2;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS exit_price_1;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS entry_price_2;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS entry_price_1;
ALTER TABLE trade_logs DROP COLUMN IF NOT EXISTS trade_number;

