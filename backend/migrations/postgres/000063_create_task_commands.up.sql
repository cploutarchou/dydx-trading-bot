-- Migration: Create task_commands table for normalized command intent
-- Purpose: Immutable command intent created by backend for NATS JetStream integration
-- Part of Phase 4: NATS JetStream command/event bus foundation

CREATE TABLE task_commands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    command_type TEXT NOT NULL,
    owner_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    requested_by_user_id INTEGER NULL,
    payload_json JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create unique constraint on idempotency_key for command deduplication
CREATE UNIQUE INDEX idx_task_commands_idempotency_key_unique ON task_commands (idempotency_key);

-- Create index for owner-based queries
CREATE INDEX idx_task_commands_owner ON task_commands (owner_type, owner_id, created_at DESC);

-- Create index for command type queries
CREATE INDEX idx_task_commands_command_type ON task_commands (command_type, created_at DESC);

-- Create index for status queries
CREATE INDEX idx_task_commands_status ON task_commands (status, created_at DESC);

-- Add comment for table purpose
COMMENT ON TABLE task_commands IS 'Immutable command intent records for NATS JetStream publishing and worker consumption. Backend creates commands here before publishing to NATS.';

COMMENT ON COLUMN task_commands.idempotency_key IS 'Unique key for command deduplication across NATS and PostgreSQL';
COMMENT ON COLUMN task_commands.payload_json IS 'Bounded input-sized payload only, not result-sized';
COMMENT ON COLUMN task_commands.status IS 'Command lifecycle status (pending, published, completed, failed)';
