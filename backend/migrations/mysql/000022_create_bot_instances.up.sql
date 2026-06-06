-- Migration 000022: Create bot_instances table for bot runtime endpoints (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000022_create_bot_instances.up.sql
-- Changes: SERIAL → AUTO_INCREMENT, TIMESTAMP DEFAULT CURRENT_TIMESTAMP

CREATE TABLE IF NOT EXISTS bot_instances (
  id INT AUTO_INCREMENT PRIMARY KEY,
  instance_id VARCHAR(255) NOT NULL UNIQUE,
  instance_name VARCHAR(255),
  user_id INTEGER NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'STOPPED',
  network VARCHAR(255),
  strategy VARCHAR(255),
  config LONGTEXT,
  trading_params LONGTEXT,
  total_trades INTEGER NOT NULL DEFAULT 0,
  total_pnl DOUBLE PRECISION,
  current_balance DOUBLE PRECISION,
  starting_balance DOUBLE PRECISION,
  process_id INTEGER,
  pid VARCHAR(50),
  host VARCHAR(255),
  port INTEGER,
  error_message LONGTEXT,
  last_error_at TIMESTAMP NULL,
  started_at TIMESTAMP NULL,
  stopped_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Align schema for existing deployments
-- MariaDB supports ADD COLUMN IF NOT EXISTS
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS instance_name VARCHAR(255);
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS trading_params LONGTEXT;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS total_trades INTEGER NOT NULL DEFAULT 0;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS total_pnl DOUBLE PRECISION;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS current_balance DOUBLE PRECISION;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS starting_balance DOUBLE PRECISION;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS pid VARCHAR(50);
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS host VARCHAR(255);
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS port INTEGER;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS error_message LONGTEXT;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMP NULL;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS started_at TIMESTAMP NULL;
ALTER TABLE bot_instances ADD COLUMN IF NOT EXISTS stopped_at TIMESTAMP NULL;

-- Set user_id to admin or first user if not set
UPDATE bot_instances
SET user_id = COALESCE(
  user_id,
  (SELECT id FROM users WHERE username = 'admin' ORDER BY id LIMIT 1),
  (SELECT id FROM users ORDER BY id LIMIT 1)
)
WHERE user_id IS NULL;

-- Set NOT NULL constraints after data is populated
ALTER TABLE bot_instances MODIFY user_id INTEGER NOT NULL;
ALTER TABLE bot_instances MODIFY status VARCHAR(50) NOT NULL DEFAULT 'STOPPED';
ALTER TABLE bot_instances MODIFY total_trades INTEGER NOT NULL DEFAULT 0;
ALTER TABLE bot_instances MODIFY created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_bot_instances_user_id ON bot_instances (user_id);
CREATE INDEX IF NOT EXISTS idx_bot_instances_created_at ON bot_instances (created_at DESC);
