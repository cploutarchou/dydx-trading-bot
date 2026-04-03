-- Migration 000022: Create bot_instances table for bot runtime endpoints
CREATE TABLE IF NOT EXISTS bot_instances (
  id SERIAL PRIMARY KEY,
  instance_id TEXT NOT NULL UNIQUE,
  instance_name TEXT,
  user_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'STOPPED',
  network TEXT,
  strategy TEXT,
  config TEXT,
  trading_params TEXT,
  total_trades INTEGER NOT NULL DEFAULT 0,
  total_pnl DOUBLE PRECISION,
  current_balance DOUBLE PRECISION,
  starting_balance DOUBLE PRECISION,
  process_id INTEGER,
  pid TEXT,
  host TEXT,
  port INTEGER,
  error_message TEXT,
  last_error_at TIMESTAMP,
  started_at TIMESTAMP,
  stopped_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_instances_user_id ON bot_instances (user_id);
CREATE INDEX IF NOT EXISTS idx_bot_instances_created_at ON bot_instances (created_at DESC);

