-- Migration 000023 Down: Revert Redis Settings enhancements

DROP INDEX IF EXISTS idx_redis_settings_host;
DROP INDEX IF EXISTS idx_redis_settings_enabled;

ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS total_cache_misses;
ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS total_cache_hits;
ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS last_connection_status;
ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS last_connection_test;
ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS cache_analysis_results;
ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS cache_market_data;
ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS cache_backtest_results;
ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS cache_ttl_seconds;
ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS max_connections;
ALTER TABLE redis_settings DROP COLUMN IF NOT EXISTS timeout;

