-- Migration 000024: Create bot_positions table for bot runtime position tracking
CREATE TABLE IF NOT EXISTS bot_positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bot_instance_id INTEGER NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
  position_id TEXT NOT NULL UNIQUE,
  market_1 TEXT NOT NULL,
  market_2 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  is_active INTEGER NOT NULL DEFAULT 1,
  entry_timestamp DATETIME NOT NULL,
  entry_price_1 REAL NOT NULL,
  entry_price_2 REAL NOT NULL,
  entry_zscore REAL,
  side_1 TEXT NOT NULL,
  side_2 TEXT NOT NULL,
  size_1 REAL NOT NULL,
  size_2 REAL NOT NULL,
  hedge_ratio REAL,
  current_price_1 REAL,
  current_price_2 REAL,
  current_zscore REAL,
  unrealized_pnl REAL,
  unrealized_pnl_pct REAL,
  exit_timestamp DATETIME,
  exit_price_1 REAL,
  exit_price_2 REAL,
  exit_zscore REAL,
  realized_pnl REAL,
  realized_pnl_pct REAL,
  duration_hours REAL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_positions_bot_instance_id ON bot_positions (bot_instance_id);
CREATE INDEX IF NOT EXISTS idx_bot_positions_position_id ON bot_positions (position_id);
CREATE INDEX IF NOT EXISTS idx_bot_positions_status ON bot_positions (status);
CREATE INDEX IF NOT EXISTS idx_bot_positions_entry_timestamp ON bot_positions (entry_timestamp DESC);

