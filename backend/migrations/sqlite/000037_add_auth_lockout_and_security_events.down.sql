DROP TABLE IF EXISTS security_login_events;

-- SQLite does not support dropping columns directly in this migration stack.
-- The failed_login_attempts, locked_until, and mfa_enabled columns are left in place on rollback.
