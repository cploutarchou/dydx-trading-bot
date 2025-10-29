-- Migration 000029: Enhance Trade Log with all fields
-- Synchronize with Python SQLModel TradeLog schema

ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS trade_number INTEGER NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS entry_price_1 REAL NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS entry_price_2 REAL NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS exit_price_1 REAL NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS exit_price_2 REAL NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS quantity_1 REAL NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS quantity_2 REAL NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS side_1 VARCHAR(10) NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS side_2 VARCHAR(10) NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS pnl REAL NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS pnl_usd REAL NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS entry_zscore REAL NULL;
ALTER TABLE trade_logs ADD COLUMN IF NOT EXISTS exit_zscore REAL NULL;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_trade_logs_result_id ON trade_logs(result_id_fk);
CREATE INDEX IF NOT EXISTS idx_trade_logs_entry_timestamp ON trade_logs(entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_trade_logs_created_at ON trade_logs(created_at);

