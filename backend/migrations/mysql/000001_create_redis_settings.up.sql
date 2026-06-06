-- Create redis_settings table (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000001_create_redis_settings.up.sql
-- Changes: SERIAL → AUTO_INCREMENT

CREATE TABLE IF NOT EXISTS redis_settings
(
  id                     INT AUTO_INCREMENT PRIMARY KEY,
  enabled                BOOLEAN      DEFAULT NULL,
  host                   VARCHAR(255) DEFAULT NULL,
  port                   INTEGER      DEFAULT NULL,
  db                     INTEGER      DEFAULT NULL,
  password               VARCHAR(255) DEFAULT NULL,
  ssl                    BOOLEAN      DEFAULT NULL,
  timeout                INTEGER      DEFAULT NULL,
  max_connections        INTEGER      DEFAULT NULL,
  cache_ttl_seconds      INTEGER      DEFAULT NULL,
  cache_backtest_results BOOLEAN      DEFAULT NULL,
  cache_market_data      BOOLEAN      DEFAULT NULL,
  cache_analysis_results BOOLEAN      DEFAULT NULL,
  last_connection_test   TIMESTAMP    NULL DEFAULT NULL,
  last_connection_status VARCHAR(20)  DEFAULT NULL,
  total_cache_hits       INTEGER      DEFAULT NULL,
  total_cache_misses     INTEGER      DEFAULT NULL,
  created_at             TIMESTAMP    NULL DEFAULT NULL,
  updated_at             TIMESTAMP    NULL DEFAULT NULL
);

CREATE INDEX idx_redis_enabled ON redis_settings (enabled);
CREATE INDEX ix_redis_settings_enabled ON redis_settings (enabled);
CREATE INDEX ix_redis_settings_id ON redis_settings (id);
