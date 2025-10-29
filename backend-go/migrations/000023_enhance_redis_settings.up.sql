-- Migration 000023: Enhance Redis Settings with all fields
-- Synchronize with Python SQLModel RedisSettings schema

ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS timeout INTEGER DEFAULT 5;
ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS max_connections INTEGER DEFAULT 10;
ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS cache_ttl_seconds INTEGER DEFAULT 86400;
ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS cache_backtest_results BOOLEAN DEFAULT TRUE;
ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS cache_market_data BOOLEAN DEFAULT TRUE;
ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS cache_analysis_results BOOLEAN DEFAULT TRUE;
ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS last_connection_test TIMESTAMP NULL;
ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS last_connection_status VARCHAR(20) DEFAULT 'unknown';
ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS total_cache_hits INTEGER DEFAULT 0;
ALTER TABLE redis_settings ADD COLUMN IF NOT EXISTS total_cache_misses INTEGER DEFAULT 0;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_redis_settings_enabled ON redis_settings(enabled);
CREATE INDEX IF NOT EXISTS idx_redis_settings_host ON redis_settings(host);

