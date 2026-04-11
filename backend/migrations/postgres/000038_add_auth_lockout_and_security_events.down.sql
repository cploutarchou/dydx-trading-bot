DROP TABLE IF EXISTS security_login_events;

ALTER TABLE users
    DROP COLUMN IF EXISTS mfa_enabled;

ALTER TABLE users
    DROP COLUMN IF EXISTS locked_until;

ALTER TABLE users
    DROP COLUMN IF EXISTS failed_login_attempts;
