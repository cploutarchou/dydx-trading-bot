-- Migration 000045: Add selected_markets to backtest_strategies (MySQL/MariaDB version)

ALTER TABLE backtest_strategies
  ADD COLUMN IF NOT EXISTS selected_markets JSON NOT NULL DEFAULT JSON_ARRAY();
