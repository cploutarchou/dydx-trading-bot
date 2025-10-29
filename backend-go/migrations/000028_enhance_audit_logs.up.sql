-- Migration 000028: Enhance Audit Log with all fields
-- Synchronize with Python SQLModel AuditLog schema

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action VARCHAR(100) NULL;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS resource_type VARCHAR(50) NULL;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS resource_id VARCHAR(100) NULL;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'success';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS ip_address VARCHAR(50) NULL;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS details TEXT NULL;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

