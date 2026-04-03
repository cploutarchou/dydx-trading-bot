-- Migration 000022: Create bot_instances table for bot runtime endpoints
CREATE TABLE IF NOT EXISTS bot_instances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instance_id TEXT NOT NULL UNIQUE,
  instance_name TEXT,
  user_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'STOPPED',
  network TEXT,
  strategy TEXT,
  config TEXT,
  trading_params TEXT,
  total_trades INTEGER NOT NULL DEFAULT 0,
  total_pnl REAL,
  current_balance REAL,
  starting_balance REAL,
  process_id INTEGER,
  pid TEXT,
  host TEXT,
  port INTEGER,
  error_message TEXT,
  last_error_at DATETIME,
  started_at DATETIME,
  stopped_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_instances_user_id ON bot_instances (user_id);
CREATE INDEX IF NOT EXISTS idx_bot_instances_created_at ON bot_instances (created_at DESC);

