-- Migration: Create worker_heartbeats table for worker liveness tracking
-- Purpose: Track current liveness for workers and consumers
-- Part of Phase 4: NATS JetStream command/event bus foundation

CREATE TABLE worker_heartbeats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id TEXT NOT NULL,
    worker_type TEXT NOT NULL,
    hostname TEXT NOT NULL,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'active',
    metadata_json JSONB NULL
);

-- Create unique constraint on worker_id for current worker state
CREATE UNIQUE INDEX idx_worker_heartbeats_worker_id_unique ON worker_heartbeats (worker_id);

-- Create index for worker type and last seen queries
CREATE INDEX idx_worker_heartbeats_type_last_seen ON worker_heartbeats (worker_type, last_seen_at DESC);

-- Create index for lease expiration monitoring
CREATE INDEX idx_worker_heartbeats_lease_expires ON worker_heartbeats (lease_expires_at) WHERE lease_expires_at IS NOT NULL;

-- Create index for status queries
CREATE INDEX idx_worker_heartbeats_status ON worker_heartbeats (status, last_seen_at DESC);

-- Add comments for table and columns
COMMENT ON TABLE worker_heartbeats IS 'Worker and consumer liveness tracking. Enables monitoring of active workers, detecting stale leases, and managing worker health.';

COMMENT ON COLUMN worker_heartbeats.worker_id IS 'Unique identifier for the worker or consumer instance';
COMMENT ON COLUMN worker_heartbeats.worker_type IS 'Worker type classification (backtest-worker, bot-worker, etc.)';
COMMENT ON COLUMN worker_heartbeats.lease_expires_at IS 'When the worker lease expires - used for dead worker detection';
COMMENT ON COLUMN worker_heartbeats.last_seen_at IS 'Last heartbeat timestamp from the worker';
COMMENT ON COLUMN worker_heartbeats.metadata_json IS 'Small metadata JSON, bounded in size';
