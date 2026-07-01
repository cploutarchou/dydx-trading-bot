-- Migration: Create task_runs table for generic execution records
-- Purpose: Generic execution record for async tasks (backtest runs, bot commands)
-- Part of Phase 4: NATS JetStream command/event bus foundation

CREATE TABLE task_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    command_id UUID REFERENCES task_commands(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress_pct NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    worker_backend TEXT NULL,
    worker_owner TEXT NULL,
    worker_task_id TEXT NULL,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    last_heartbeat_at TIMESTAMPTZ NULL,
    error_code TEXT NULL,
    error_message TEXT NULL,
    summary_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create foreign key index for command lookups
CREATE INDEX idx_task_runs_command_id ON task_runs (command_id);

-- Create index for task type and status queries
CREATE INDEX idx_task_runs_task_type_status ON task_runs (task_type, status, updated_at DESC);

-- Create index for heartbeat-based monitoring
CREATE INDEX idx_task_runs_last_heartbeat ON task_runs (last_heartbeat_at) WHERE last_heartbeat_at IS NOT NULL;

-- Create index for worker task ID lookups
CREATE INDEX idx_task_runs_worker_task_id ON task_runs (worker_task_id) WHERE worker_task_id IS NOT NULL;

-- Create index for updated_at for recent activity queries
CREATE INDEX idx_task_runs_updated_at ON task_runs (updated_at DESC);

-- Add updated_at trigger for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_task_runs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trig_task_runs_updated_at
    BEFORE UPDATE ON task_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_task_runs_updated_at();

-- Add comments for table and columns
COMMENT ON TABLE task_runs IS 'Generic execution records for async tasks. Links to task_commands for idempotency and tracks execution state, progress, retries, and worker assignment.';

COMMENT ON COLUMN task_runs.command_id IS 'References task_commands.id for command intent and idempotency';
COMMENT ON COLUMN task_runs.task_type IS 'Task type classification (backtest, bot_start, etc.)';
COMMENT ON COLUMN task_runs.summary_json IS 'Small summary-only JSON, bounded in size';
COMMENT ON COLUMN task_runs.last_heartbeat_at IS 'Last worker heartbeat timestamp for liveness monitoring';
COMMENT ON COLUMN task_runs.worker_task_id IS 'Worker-assigned task identifier for consumer tracking';
