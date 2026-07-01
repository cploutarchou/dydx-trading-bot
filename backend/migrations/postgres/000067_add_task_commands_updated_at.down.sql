-- Migration: Remove updated_at from task_commands
-- Down migration for 000067_add_task_commands_updated_at.up.sql

DROP TRIGGER IF EXISTS trig_task_commands_updated_at ON task_commands;
DROP FUNCTION IF EXISTS update_task_commands_updated_at();
DROP INDEX IF EXISTS idx_task_commands_updated_at;
ALTER TABLE task_commands DROP COLUMN IF EXISTS updated_at;
