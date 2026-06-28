-- Migration: Drop task_runs table
-- Down migration for 000064_create_task_runs.up.sql

-- Drop trigger function first
DROP FUNCTION IF EXISTS update_task_runs_updated_at() CASCADE;

-- Drop table
DROP TABLE IF EXISTS task_runs CASCADE;
