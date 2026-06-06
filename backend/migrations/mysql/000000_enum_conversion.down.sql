-- ============================================================================
-- ENUM Conversion Script: Rollback
-- ============================================================================
-- This script removes the lookup tables created for ENUM conversion
-- WARNING: This will delete all enum lookup data. Only run during initial setup.
-- ============================================================================

-- Drop lookup tables (in reverse order of creation due to potential foreign keys)
DROP TABLE IF EXISTS trade_status_enum;
DROP TABLE IF EXISTS job_status_enum;
DROP TABLE IF EXISTS bot_status_enum;
