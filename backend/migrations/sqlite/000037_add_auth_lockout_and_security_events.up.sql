ALTER TABLE users
    ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE users
    ADD COLUMN locked_until DATETIME;

ALTER TABLE users
    ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS security_login_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    ip_address TEXT,
    user_agent TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_security_login_events_user_id ON security_login_events(user_id);
CREATE INDEX IF NOT EXISTS idx_security_login_events_created_at ON security_login_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_login_events_outcome ON security_login_events(outcome);
