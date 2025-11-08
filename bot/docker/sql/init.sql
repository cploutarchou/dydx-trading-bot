-- =============================================================================
-- PostgreSQL Initialization Script for dYdX Trading Bot
-- =============================================================================
-- This script initializes the PostgreSQL database with proper settings
-- =============================================================================

-- Create database if not exists (handled by POSTGRES_DB env var)
-- CREATE DATABASE IF NOT EXISTS dydx_trading_bot;

-- Create user extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Set timezone
SET timezone = 'UTC';

-- Performance optimizations
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET log_statement = 'mod';
ALTER SYSTEM SET log_min_duration_statement = '1s';
ALTER SYSTEM SET track_activities = on;
ALTER SYSTEM SET track_counts = on;

-- Security settings
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;
ALTER SYSTEM SET log_checkpoints = on;

-- Connection settings
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;

-- Reload configuration
SELECT pg_reload_conf();

-- Create initial database structure placeholder
-- Note: Actual tables will be created by Alembic migrations
COMMENT ON DATABASE current_database() IS 'dYdX Trading Bot Database - Initialized with Docker';

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'dYdX Trading Bot PostgreSQL database initialized successfully at %', now();
END $$;