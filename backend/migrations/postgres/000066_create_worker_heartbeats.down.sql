-- Migration: Drop worker_heartbeats table
-- Down migration for 000066_create_worker_heartbeats.up.sql

DROP TABLE IF EXISTS worker_heartbeats CASCADE;
