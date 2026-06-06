-- Migration 000045: Add selected_markets to backtest_strategies (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000045_add_selected_markets_to_backtest_strategies.up.sql
-- Changes: JSONB → JSON, default cast handled

ALTER TABLE backtest_strategies
  ADD COLUMN IF NOT EXISTS selected_markets JSON NOT NULL DEFAULT JSON_ARRAY();
