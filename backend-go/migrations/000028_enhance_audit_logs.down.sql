-- Migration 000028 Down: Revert Audit Log enhancements

DROP INDEX IF EXISTS idx_audit_logs_created_at;
DROP INDEX IF EXISTS idx_audit_logs_resource_type;
DROP INDEX IF EXISTS idx_audit_logs_action;
DROP INDEX IF EXISTS idx_audit_logs_user_id;

ALTER TABLE audit_logs DROP COLUMN IF NOT EXISTS details;
ALTER TABLE audit_logs DROP COLUMN IF NOT EXISTS ip_address;
ALTER TABLE audit_logs DROP COLUMN IF NOT EXISTS status;
ALTER TABLE audit_logs DROP COLUMN IF NOT EXISTS resource_id;
ALTER TABLE audit_logs DROP COLUMN IF NOT EXISTS resource_type;
ALTER TABLE audit_logs DROP COLUMN IF NOT EXISTS action;

