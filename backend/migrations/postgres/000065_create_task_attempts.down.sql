-- Migration: Drop task_attempts table
-- Down migration for 000065_create_task_attempts.up.sql

DROP TABLE IF EXISTS task_attempts CASCADE;
