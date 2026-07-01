-- Migration: Create task_attempts table for retry and redelivery audit
-- Purpose: Retry and redelivery audit trail for task execution
-- Part of Phase 4: NATS JetStream command/event bus foundation

CREATE TABLE task_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_run_id UUID NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    worker_id TEXT NULL,
    consumer_name TEXT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ NULL,
    outcome TEXT NOT NULL,
    error_code TEXT NULL,
    error_message TEXT NULL
);

-- Create index for task run lookups (all attempts for a given run)
CREATE INDEX idx_task_attempts_task_run_id ON task_attempts (task_run_id);

-- Create index for attempt number queries
CREATE INDEX idx_task_attempts_attempt_number ON task_attempts (task_run_id, attempt_number);

-- Create index for outcome analysis
CREATE INDEX idx_task_attempts_outcome ON task_attempts (outcome, finished_at DESC);

-- Create index for worker/consumer analysis
CREATE INDEX idx_task_attempts_worker_consumer ON task_attempts (worker_id, consumer_name, finished_at DESC) WHERE worker_id IS NOT NULL AND consumer_name IS NOT NULL;

-- Add comments for table and columns
COMMENT ON TABLE task_attempts IS 'Retry and redelivery audit trail. Tracks every execution attempt for a task run, enabling debugging of retry patterns and failure analysis.';

COMMENT ON COLUMN task_attempts.task_run_id IS 'References task_runs.id - the parent task execution record';
COMMENT ON COLUMN task_attempts.attempt_number IS 'Sequential attempt number (1, 2, 3, ...) for this task run';
COMMENT ON COLUMN task_attempts.worker_id IS 'Identifier of the worker that processed this attempt';
COMMENT ON COLUMN task_attempts.consumer_name IS 'NATS consumer name that delivered this attempt';
COMMENT ON COLUMN task_attempts.outcome IS 'Attempt outcome (success, failed, timeout, etc.)';
COMMENT ON COLUMN task_attempts.finished_at IS 'When the attempt completed (null if still running)';
