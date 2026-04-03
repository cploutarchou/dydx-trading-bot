-- Migration 000023: Create bot_trades table for bot runtime trade tracking
CREATE TABLE IF NOT EXISTS bot_trades (
  id SERIAL PRIMARY KEY,
  bot_instance_id INTEGER NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
  trade_id TEXT NOT NULL UNIQUE,
  market_1 TEXT NOT NULL,
  market_2 TEXT NOT NULL,
  entry_timestamp TIMESTAMP NOT NULL,
  entry_price_1 DOUBLE PRECISION NOT NULL,
  entry_price_2 DOUBLE PRECISION NOT NULL,
  entry_zscore DOUBLE PRECISION,
  side_1 TEXT NOT NULL,
  side_2 TEXT NOT NULL,
  size_1 DOUBLE PRECISION NOT NULL,
  size_2 DOUBLE PRECISION NOT NULL,
  hedge_ratio DOUBLE PRECISION,
  exit_timestamp TIMESTAMP,
  exit_price_1 DOUBLE PRECISION,
  exit_price_2 DOUBLE PRECISION,
  exit_zscore DOUBLE PRECISION,
  pnl DOUBLE PRECISION,
  pnl_pct DOUBLE PRECISION,
  duration_hours DOUBLE PRECISION,
  strategy_zscore_threshold DOUBLE PRECISION,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_trades_bot_instance_id ON bot_trades (bot_instance_id);
CREATE INDEX IF NOT EXISTS idx_bot_trades_trade_id ON bot_trades (trade_id);
CREATE INDEX IF NOT EXISTS idx_bot_trades_entry_timestamp ON bot_trades (entry_timestamp DESC);

