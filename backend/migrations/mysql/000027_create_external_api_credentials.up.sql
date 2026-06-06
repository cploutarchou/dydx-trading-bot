CREATE TABLE IF NOT EXISTS external_api_credentials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    encrypted_api_key TEXT NOT NULL,
    api_key_hash TEXT NOT NULL DEFAULT '',
    api_key_masked TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_external_api_credentials_user_provider UNIQUE (user_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_external_api_credentials_user_provider
    ON external_api_credentials (user_id, provider);
