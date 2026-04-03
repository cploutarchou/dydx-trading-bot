-- Migration 000023: Create bot_trades table for bot runtime trade tracking
CREATE TABLE IF NOT EXISTS bot_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bot_instance_id INTEGER NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
  trade_id TEXT NOT NULL UNIQUE,
  market_1 TEXT NOT NULL,
  market_2 TEXT NOT NULL,
  entry_timestamp DATETIME NOT NULL,
  entry_price_1 REAL NOT NULL,
  entry_price_2 REAL NOT NULL,
  entry_zscore REAL,
  side_1 TEXT NOT NULL,
  side_2 TEXT NOT NULL,
  size_1 REAL NOT NULL,
  size_2 REAL NOT NULL,
  hedge_ratio REAL,
  exit_timestamp DATETIME,
  exit_price_1 REAL,
  exit_price_2 REAL,
  exit_zscore REAL,
  pnl REAL,
  pnl_pct REAL,
  duration_hours REAL,
  strategy_zscore_threshold REAL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_trades_bot_instance_id ON bot_trades (bot_instance_id);
CREATE INDEX IF NOT EXISTS idx_bot_trades_trade_id ON bot_trades (trade_id);
CREATE INDEX IF NOT EXISTS idx_bot_trades_entry_timestamp ON bot_trades (entry_timestamp DESC);

