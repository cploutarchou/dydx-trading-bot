-- Migration 000043: Drop tables that have no backend query references.
-- These tables were created in earlier migrations but are never read or written
-- by any Go repository, handler, or service in the backend.
-- Safe to drop: none of these tables are referenced as FKs by other tables.

-- bot_alerts: no Go handler or repository uses it (bot runtime alerts are managed by the Python bot)
DROP TABLE IF EXISTS bot_alerts;

-- backtest_comparisons: no Go handler or repository uses it
DROP TABLE IF EXISTS backtest_comparisons;

-- backtest_metrics: no Go repository writes/reads it; metrics are stored in JSON files
DROP TABLE IF EXISTS backtest_metrics;

-- cointegration_results: pair storage is file-based (services/pair_storage.go); table is unused
DROP TABLE IF EXISTS cointegration_results;

-- dydx_key_settings: no Go handler or repository uses it; key management uses dydx_keys table instead
DROP TABLE IF EXISTS dydx_key_settings;

