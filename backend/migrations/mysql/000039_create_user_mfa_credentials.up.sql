CREATE TABLE IF NOT EXISTS user_mfa_credentials (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    encrypted_secret TEXT NOT NULL,
    encrypted_backup_codes TEXT NOT NULL DEFAULT '',
    enabled TINYINT(1) NOT NULL DEFAULT 0,
    verified_at TIMESTAMP NULL,
    last_used_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_mfa_credentials_enabled ON user_mfa_credentials(enabled);
