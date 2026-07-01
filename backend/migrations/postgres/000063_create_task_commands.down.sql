-- Migration: Drop task_commands table
-- Down migration for 000063_create_task_commands.up.sql

DROP TABLE IF EXISTS task_commands CASCADE;
