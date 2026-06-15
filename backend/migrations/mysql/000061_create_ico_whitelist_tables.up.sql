CREATE TABLE IF NOT EXISTS ico_whitelist_applications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
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
    reviewed_by INT NULL,
    approved_at TIMESTAMP NULL,
    rejected_at TIMESTAMP NULL,
    rejection_reason TEXT NOT NULL,
    unsubscribed_at TIMESTAMP NULL,
    withdrawn_at TIMESTAMP NULL,
    source VARCHAR(80) NOT NULL DEFAULT 'ico_public_form',
    locale VARCHAR(20) NOT NULL DEFAULT '',
    referral_code VARCHAR(120) NOT NULL DEFAULT '',
    campaign VARCHAR(120) NOT NULL DEFAULT '',
    email_fingerprint VARCHAR(128) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_ico_whitelist_normalized_email (normalized_email),
    KEY idx_ico_whitelist_status_created (status, created_at),
    KEY idx_ico_whitelist_consent (marketing_consent, marketing_confirmed_at, unsubscribed_at),
    KEY idx_ico_whitelist_confirmation_hash (confirmation_token_hash),
    KEY idx_ico_whitelist_unsubscribe_hash (unsubscribe_token_hash),
    KEY idx_ico_whitelist_withdraw_hash (withdraw_token_hash),
    CONSTRAINT fk_ico_whitelist_reviewed_by
        FOREIGN KEY (reviewed_by) REFERENCES users(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ico_consent_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    whitelist_application_id BIGINT NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    policy_version VARCHAR(80) NOT NULL DEFAULT '',
    consent_text TEXT NOT NULL,
    source VARCHAR(80) NOT NULL DEFAULT 'ico_public_form',
    metadata_json TEXT NOT NULL,
    occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_ico_consent_application (whitelist_application_id, occurred_at),
    KEY idx_ico_consent_event_type (event_type, occurred_at),
    CONSTRAINT fk_ico_consent_application
        FOREIGN KEY (whitelist_application_id) REFERENCES ico_whitelist_applications(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ico_email_outbox (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    whitelist_application_id BIGINT NULL,
    idempotency_key VARCHAR(160) NOT NULL,
    email_type VARCHAR(80) NOT NULL,
    recipient_email VARCHAR(320) NOT NULL,
    recipient_fingerprint VARCHAR(128) NOT NULL DEFAULT '',
    subject VARCHAR(255) NOT NULL,
    template_key VARCHAR(120) NOT NULL,
    payload_encrypted LONGTEXT NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    last_error TEXT NOT NULL,
    provider_message_id VARCHAR(160) NOT NULL DEFAULT '',
    scheduled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_ico_email_outbox_idempotency (idempotency_key),
    KEY idx_ico_email_outbox_status_scheduled (status, scheduled_at),
    KEY idx_ico_email_outbox_application (whitelist_application_id),
    CONSTRAINT fk_ico_email_outbox_application
        FOREIGN KEY (whitelist_application_id) REFERENCES ico_whitelist_applications(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ico_email_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    outbox_id BIGINT NULL,
    provider_message_id VARCHAR(160) NOT NULL DEFAULT '',
    event_type VARCHAR(80) NOT NULL,
    recipient_fingerprint VARCHAR(128) NOT NULL DEFAULT '',
    provider_timestamp TIMESTAMP NULL,
    event_hash VARCHAR(128) NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_ico_email_event_hash (event_hash),
    KEY idx_ico_email_events_provider_message (provider_message_id),
    KEY idx_ico_email_events_type_created (event_type, created_at),
    CONSTRAINT fk_ico_email_events_outbox
        FOREIGN KEY (outbox_id) REFERENCES ico_email_outbox(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ico_marketing_suppressions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    normalized_email VARCHAR(320) NOT NULL,
    email_fingerprint VARCHAR(128) NOT NULL,
    reason VARCHAR(80) NOT NULL,
    source VARCHAR(80) NOT NULL DEFAULT 'local',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_ico_suppression_email (normalized_email),
    KEY idx_ico_suppression_reason (reason, created_at),
    KEY idx_ico_suppression_fingerprint (email_fingerprint)
);
