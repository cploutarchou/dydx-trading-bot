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

-- Older deployments created a narrower bot_instances table. Align it before
-- creating indexes and later constraints that expect the full runtime schema.
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS instance_name TEXT;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS trading_params TEXT;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS total_trades INTEGER NOT NULL DEFAULT 0;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS total_pnl DOUBLE PRECISION;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS current_balance DOUBLE PRECISION;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS starting_balance DOUBLE PRECISION;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS pid TEXT;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS host TEXT;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS port INTEGER;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMP;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS started_at TIMESTAMP;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS stopped_at TIMESTAMP;

UPDATE bot_instances
SET user_id = COALESCE(
  user_id,
  (SELECT id FROM users WHERE username = 'admin' ORDER BY id LIMIT 1),
  (SELECT id FROM users ORDER BY id LIMIT 1)
)
WHERE user_id IS NULL;

ALTER TABLE bot_instances ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE bot_instances ALTER COLUMN status SET DEFAULT 'STOPPED';
ALTER TABLE bot_instances ALTER COLUMN status SET NOT NULL;
ALTER TABLE bot_instances ALTER COLUMN total_trades SET DEFAULT 0;
ALTER TABLE bot_instances ALTER COLUMN total_trades SET NOT NULL;
ALTER TABLE bot_instances ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE bot_instances ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE bot_instances ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE bot_instances ALTER COLUMN updated_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bot_instances_user_id ON bot_instances (user_id);
CREATE INDEX IF NOT EXISTS idx_bot_instances_created_at ON bot_instances (created_at DESC);
