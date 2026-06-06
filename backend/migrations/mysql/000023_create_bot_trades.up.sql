-- Migration 000023: Create bot_trades table for bot runtime trade tracking (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000023_create_bot_trades.up.sql
-- Changes: SERIAL → AUTO_INCREMENT, TIMESTAMP DEFAULT CURRENT_TIMESTAMP

CREATE TABLE IF NOT EXISTS bot_trades (
  id INT AUTO_INCREMENT PRIMARY KEY,
  bot_instance_id INTEGER NOT NULL,
  trade_id VARCHAR(255) NOT NULL UNIQUE,
  market_1 VARCHAR(255) NOT NULL,
  market_2 VARCHAR(255) NOT NULL,
  entry_timestamp TIMESTAMP NOT NULL,
  entry_price_1 DOUBLE PRECISION NOT NULL,
  entry_price_2 DOUBLE PRECISION NOT NULL,
  entry_zscore DOUBLE PRECISION,
  side_1 VARCHAR(20) NOT NULL,
  side_2 VARCHAR(20) NOT NULL,
  size_1 DOUBLE PRECISION NOT NULL,
  size_2 DOUBLE PRECISION NOT NULL,
  hedge_ratio DOUBLE PRECISION,
  exit_timestamp TIMESTAMP NULL,
  exit_price_1 DOUBLE PRECISION,
  exit_price_2 DOUBLE PRECISION,
  exit_zscore DOUBLE PRECISION,
  pnl DOUBLE PRECISION,
  pnl_pct DOUBLE PRECISION,
  duration_hours DOUBLE PRECISION,
  strategy_zscore_threshold DOUBLE PRECISION,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (bot_instance_id) REFERENCES bot_instances(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bot_trades_bot_instance_id ON bot_trades (bot_instance_id);
CREATE INDEX IF NOT EXISTS idx_bot_trades_trade_id ON bot_trades (trade_id);
CREATE INDEX IF NOT EXISTS idx_bot_trades_entry_timestamp ON bot_trades (entry_timestamp DESC);
