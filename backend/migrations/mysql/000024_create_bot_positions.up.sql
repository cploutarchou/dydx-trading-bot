-- Migration 000024: Create bot_positions table for bot runtime position tracking
CREATE TABLE IF NOT EXISTS bot_positions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  bot_instance_id INTEGER NOT NULL,
  position_id TEXT NOT NULL UNIQUE,
  market_1 TEXT NOT NULL,
  market_2 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  is_active INTEGER NOT NULL DEFAULT 1,
  entry_timestamp TIMESTAMP NOT NULL,
  entry_price_1 DOUBLE PRECISION NOT NULL,
  entry_price_2 DOUBLE PRECISION NOT NULL,
  entry_zscore DOUBLE PRECISION,
  side_1 TEXT NOT NULL,
  side_2 TEXT NOT NULL,
  size_1 DOUBLE PRECISION NOT NULL,
  size_2 DOUBLE PRECISION NOT NULL,
  hedge_ratio DOUBLE PRECISION,
  current_price_1 DOUBLE PRECISION,
  current_price_2 DOUBLE PRECISION,
  current_zscore DOUBLE PRECISION,
  unrealized_pnl DOUBLE PRECISION,
  unrealized_pnl_pct DOUBLE PRECISION,
  exit_timestamp TIMESTAMP,
  exit_price_1 DOUBLE PRECISION,
  exit_price_2 DOUBLE PRECISION,
  exit_zscore DOUBLE PRECISION,
  realized_pnl DOUBLE PRECISION,
  realized_pnl_pct DOUBLE PRECISION,
  duration_hours DOUBLE PRECISION,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_positions_bot_instance_id ON bot_positions (bot_instance_id);
CREATE INDEX IF NOT EXISTS idx_bot_positions_position_id ON bot_positions (position_id);
CREATE INDEX IF NOT EXISTS idx_bot_positions_status ON bot_positions (status);
CREATE INDEX IF NOT EXISTS idx_bot_positions_entry_timestamp ON bot_positions (entry_timestamp DESC);

