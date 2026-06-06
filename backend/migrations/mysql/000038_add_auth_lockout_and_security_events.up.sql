ALTER TABLE users
    ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP NULL;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS mfa_enabled TINYINT(1) NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS security_login_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    username VARCHAR(100) NOT NULL DEFAULT '',
    event_type VARCHAR(50) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    ip_address VARCHAR(64),
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_login_events_user_id ON security_login_events(user_id);
CREATE INDEX IF NOT EXISTS idx_security_login_events_created_at ON security_login_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_login_events_outcome ON security_login_events(outcome);
