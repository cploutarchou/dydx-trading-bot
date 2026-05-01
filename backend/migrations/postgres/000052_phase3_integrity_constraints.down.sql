-- Rollback for 000052_phase3_integrity_constraints
-- Re-applies nullable defaults (NOT NULL removal requires a default or explicit nullable declaration).

-- Remove CHECK on bot_instances.status
ALTER TABLE bot_instances DROP CONSTRAINT IF EXISTS chk_bot_instances_status;

-- Remove NOT NULL from users.is_active / is_admin (restore nullable + drop defaults)
ALTER TABLE users
    ALTER COLUMN is_active DROP NOT NULL,
    ALTER COLUMN is_active DROP DEFAULT,
    ALTER COLUMN is_admin  DROP NOT NULL,
    ALTER COLUMN is_admin  DROP DEFAULT;

-- Remove FK from external_api_credentials
ALTER TABLE external_api_credentials
    DROP CONSTRAINT IF EXISTS fk_external_api_credentials_user_id;

-- Remove FK from bot_instances
ALTER TABLE bot_instances
    DROP CONSTRAINT IF EXISTS fk_bot_instances_user_id;
