-- Migration: Add updated_at to task_commands
-- Purpose: Phase 0 consistency fix. task_commands status transitions
-- (pending -> published -> completed -> failed) need a last-modified timestamp
-- for operational observability (command publish success/failure tracking) and
-- to align the repository status-update path with the real schema. Without this
-- column, repository.UpdateTaskCommandStatus fails at runtime because it sets
-- updated_at on a table that does not have it. Mirrors the task_runs pattern
-- (migration 000064).
-- Part of Phase 0: NATS JetStream command/event bus foundation cleanup.

ALTER TABLE task_commands
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Index for recent-activity queries on command status changes.
CREATE INDEX IF NOT EXISTS idx_task_commands_updated_at
    ON task_commands (updated_at DESC);

COMMENT ON COLUMN task_commands.updated_at IS
    'Last status-change time; maintained by trig_task_commands_updated_at on every UPDATE.';

-- Maintain updated_at automatically on UPDATE, reusing the same trigger shape as
-- task_runs (update_task_runs_updated_at) for operational consistency.
CREATE OR REPLACE FUNCTION update_task_commands_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trig_task_commands_updated_at ON task_commands;

CREATE TRIGGER trig_task_commands_updated_at
    BEFORE UPDATE ON task_commands
    FOR EACH ROW
    EXECUTE FUNCTION update_task_commands_updated_at();
