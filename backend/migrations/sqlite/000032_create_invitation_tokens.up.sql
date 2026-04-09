CREATE TABLE IF NOT EXISTS invitation_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL DEFAULT '',
    ib_name TEXT NOT NULL DEFAULT '',
    campaign_name TEXT NOT NULL DEFAULT '',
    max_uses INTEGER NOT NULL DEFAULT 1,
    used_count INTEGER NOT NULL DEFAULT 0,
    created_by_user_id INTEGER,
    last_used_by_user_id INTEGER,
    expires_at DATETIME,
    last_used_at DATETIME,
    revoked_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id),
    FOREIGN KEY (last_used_by_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_invitation_tokens_token_code ON invitation_tokens(token_code);
CREATE INDEX IF NOT EXISTS idx_invitation_tokens_revoked_at ON invitation_tokens(revoked_at);
CREATE INDEX IF NOT EXISTS idx_invitation_tokens_expires_at ON invitation_tokens(expires_at);
