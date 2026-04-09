CREATE TABLE IF NOT EXISTS invitation_tokens (
    id BIGSERIAL PRIMARY KEY,
    token_code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL DEFAULT '',
    ib_name TEXT NOT NULL DEFAULT '',
    campaign_name TEXT NOT NULL DEFAULT '',
    max_uses INTEGER NOT NULL DEFAULT 1,
    used_count INTEGER NOT NULL DEFAULT 0,
    created_by_user_id BIGINT REFERENCES users(id),
    last_used_by_user_id BIGINT REFERENCES users(id),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_invitation_tokens_token_code ON invitation_tokens(token_code);
CREATE INDEX IF NOT EXISTS idx_invitation_tokens_revoked_at ON invitation_tokens(revoked_at);
CREATE INDEX IF NOT EXISTS idx_invitation_tokens_expires_at ON invitation_tokens(expires_at);
