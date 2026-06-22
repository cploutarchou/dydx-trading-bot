CREATE TABLE IF NOT EXISTS ico_whitelist_applications (
    id SERIAL PRIMARY KEY,
    email VARCHAR(320) NOT NULL,
    normalized_email VARCHAR(320) NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'pending_confirmation',
    marketing_consent BOOLEAN NOT NULL DEFAULT FALSE,
    marketing_consent_version VARCHAR(80) NOT NULL DEFAULT '',
    marketing_consent_text TEXT NOT NULL,
    marketing_consented_at TIMESTAMP NULL,
    marketing_confirmed_at TIMESTAMP NULL,
    privacy_notice_version VARCHAR(80) NOT NULL,
    privacy_accepted_at TIMESTAMP NOT NULL,
    confirmation_token_hash VARCHAR(128) NOT NULL,
    confirmation_expires_at TIMESTAMP NOT NULL,
    unsubscribe_token_hash VARCHAR(128) NOT NULL DEFAULT '',
    withdraw_token_hash VARCHAR(128) NOT NULL DEFAULT '',
    email_confirmed_at TIMESTAMP NULL,
    reviewed_at TIMESTAMP NULL,
    reviewed_by INTEGER NULL,
    approved_at TIMESTAMP NULL,
    rejected_at TIMESTAMP NULL,
    rejection_reason TEXT NOT NULL DEFAULT '',
    unsubscribed_at TIMESTAMP NULL,
    withdrawn_at TIMESTAMP NULL,
    source VARCHAR(80) NOT NULL DEFAULT 'ico_public_form',
    locale VARCHAR(20) NOT NULL DEFAULT '',
    referral_code VARCHAR(120) NOT NULL DEFAULT '',
    campaign VARCHAR(120) NOT NULL DEFAULT '',
    email_fingerprint VARCHAR(128) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ico_whitelist_normalized_email UNIQUE (normalized_email),
    CONSTRAINT fk_ico_whitelist_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ico_whitelist_status_created ON ico_whitelist_applications (status, created_at);

CREATE INDEX IF NOT EXISTS idx_ico_whitelist_consent ON ico_whitelist_applications (
    marketing_consent,
    marketing_confirmed_at,
    unsubscribed_at
);

CREATE INDEX IF NOT EXISTS idx_ico_whitelist_confirmation_hash ON ico_whitelist_applications (confirmation_token_hash);

CREATE INDEX IF NOT EXISTS idx_ico_whitelist_unsubscribe_hash ON ico_whitelist_applications (unsubscribe_token_hash);

CREATE INDEX IF NOT EXISTS idx_ico_whitelist_withdraw_hash ON ico_whitelist_applications (withdraw_token_hash);

CREATE TABLE IF NOT EXISTS ico_consent_events (
    id SERIAL PRIMARY KEY,
    whitelist_application_id INTEGER NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    policy_version VARCHAR(80) NOT NULL DEFAULT '',
    consent_text TEXT NOT NULL,
    source VARCHAR(80) NOT NULL DEFAULT 'ico_public_form',
    metadata_json TEXT NOT NULL,
    occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ico_consent_application FOREIGN KEY (whitelist_application_id) REFERENCES ico_whitelist_applications (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ico_consent_application ON ico_consent_events (whitelist_application_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_ico_consent_event_type ON ico_consent_events (event_type, occurred_at);

CREATE TABLE IF NOT EXISTS ico_email_outbox (
    id SERIAL PRIMARY KEY,
    whitelist_application_id INTEGER NULL,
    idempotency_key VARCHAR(160) NOT NULL,
    email_type VARCHAR(80) NOT NULL,
    recipient_email VARCHAR(320) NOT NULL,
    recipient_fingerprint VARCHAR(128) NOT NULL DEFAULT '',
    subject VARCHAR(255) NOT NULL,
    template_key VARCHAR(120) NOT NULL,
    payload_encrypted TEXT NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    last_error TEXT NOT NULL DEFAULT '',
    provider_message_id VARCHAR(160) NOT NULL DEFAULT '',
    scheduled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ico_email_outbox_idempotency UNIQUE (idempotency_key),
    CONSTRAINT fk_ico_email_outbox_application FOREIGN KEY (whitelist_application_id) REFERENCES ico_whitelist_applications (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ico_email_outbox_status_scheduled ON ico_email_outbox (status, scheduled_at);

CREATE INDEX IF NOT EXISTS idx_ico_email_outbox_application ON ico_email_outbox (whitelist_application_id);

CREATE TABLE IF NOT EXISTS ico_email_events (
    id SERIAL PRIMARY KEY,
    outbox_id INTEGER NULL,
    provider_message_id VARCHAR(160) NOT NULL DEFAULT '',
    event_type VARCHAR(80) NOT NULL,
    recipient_fingerprint VARCHAR(128) NOT NULL DEFAULT '',
    provider_timestamp TIMESTAMP NULL,
    event_hash VARCHAR(128) NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ico_email_event_hash UNIQUE (event_hash),
    CONSTRAINT fk_ico_email_events_outbox FOREIGN KEY (outbox_id) REFERENCES ico_email_outbox (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ico_email_events_provider_message ON ico_email_events (provider_message_id);

CREATE INDEX IF NOT EXISTS idx_ico_email_events_type_created ON ico_email_events (event_type, created_at);

CREATE TABLE IF NOT EXISTS ico_marketing_suppressions (
    id SERIAL PRIMARY KEY,
    normalized_email VARCHAR(320) NOT NULL,
    email_fingerprint VARCHAR(128) NOT NULL,
    reason VARCHAR(80) NOT NULL,
    source VARCHAR(80) NOT NULL DEFAULT 'local',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ico_suppression_email UNIQUE (normalized_email)
);

CREATE INDEX IF NOT EXISTS idx_ico_suppression_reason ON ico_marketing_suppressions (reason, created_at);

CREATE INDEX IF NOT EXISTS idx_ico_suppression_fingerprint ON ico_marketing_suppressions (email_fingerprint);
