-- ============================================================================
-- ENUM Conversion Script: PostgreSQL ENUM → MariaDB Lookup Tables
-- ============================================================================
-- This script creates lookup tables to replace PostgreSQL's native ENUM types
--
-- PostgreSQL ENUM types being converted:
-- 1. botstatusenum
-- 2. jobstatusenum
-- 3. tradestatusenum
--
-- Run this BEFORE any migrations that reference these ENUM types
-- ============================================================================

-- ============================================================================
-- 1. Bot Status Enum → Lookup Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS bot_status_enum (
  value VARCHAR(20) PRIMARY KEY,
  description VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

INSERT IGNORE INTO bot_status_enum (value, description) VALUES
  ('CREATED', 'Bot instance created, not yet initialized'),
  ('STARTING', 'Bot starting up, initializing connections'),
  ('RUNNING', 'Bot running and trading'),
  ('PAUSED', 'Bot paused by user'),
  ('STOPPING', 'Bot shutting down gracefully'),
  ('STOPPED', 'Bot stopped'),
  ('ERROR', 'Bot encountered an error');

-- ============================================================================
-- 2. Job Status Enum → Lookup Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_status_enum (
  value VARCHAR(20) PRIMARY KEY,
  description VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

INSERT IGNORE INTO job_status_enum (value, description) VALUES
  ('QUEUED', 'Job queued, waiting to execute'),
  ('RUNNING', 'Job currently executing'),
  ('COMPLETED', 'Job completed successfully'),
  ('FAILED', 'Job failed with error'),
  ('CANCELLED', 'Job cancelled by user'),
  ('RETRYING', 'Job retrying after failure');

-- ============================================================================
-- 3. Trade Status Enum → Lookup Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS trade_status_enum (
  value VARCHAR(20) PRIMARY KEY,
  description VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

INSERT IGNORE INTO trade_status_enum (value, description) VALUES
  ('PENDING', 'Trade pending execution'),
  ('OPENED', 'Trade position opened'),
  ('CLOSED', 'Trade position closed'),
  ('CANCELLED', 'Trade cancelled before execution'),
  ('FAILED', 'Trade failed due to error or rejection'),
  ('PARTIAL', 'Trade partially filled'),
  ('EXECUTING', 'Trade currently executing');

-- ============================================================================
-- Add Foreign Key Constraints (These should be added in individual migrations)
-- ============================================================================
-- NOTE: These constraints should be added in the specific migration files
-- that reference these ENUM types, NOT here. This ensures correct ordering.
--
-- Example constraint additions:
--
-- ALTER TABLE bot_instance
--   ADD CONSTRAINT fk_bot_instance_status
--   FOREIGN KEY (status);
--
-- ALTER TABLE background_jobs
--   ADD CONSTRAINT fk_job_status
--   FOREIGN KEY (status);
--
-- ALTER TABLE bot_trades
--   ADD CONSTRAINT fk_trade_status
--   FOREIGN KEY (status);

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- Verify lookup tables created:
-- SELECT * FROM bot_status_enum;
-- SELECT * FROM job_status_enum;
-- SELECT * FROM trade_status_enum;
--
-- Check for any enum columns that should use these lookups:
-- SELECT COLUMN_NAME, COLUMN_TYPE
-- FROM INFORMATION_SCHEMA.COLUMNS
-- WHERE COLUMN_TYPE LIKE '%enum%' AND TABLE_SCHEMA = 'your_db_name';
