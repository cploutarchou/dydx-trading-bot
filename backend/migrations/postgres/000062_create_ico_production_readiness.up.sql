CREATE TABLE IF NOT EXISTS ico_production_readiness (
    id SMALLINT PRIMARY KEY,
    tokenomics_allocation_finalized BOOLEAN NOT NULL DEFAULT FALSE,
    tokenomics_allocation_notes TEXT NOT NULL DEFAULT '',
    vesting_schedule_finalized BOOLEAN NOT NULL DEFAULT FALSE,
    vesting_schedule_notes TEXT NOT NULL DEFAULT '',
    token_price VARCHAR(120) NOT NULL DEFAULT '',
    accepted_currencies TEXT NOT NULL DEFAULT '',
    smart_contract_address VARCHAR(180) NOT NULL DEFAULT '',
    smart_contract_audit_status VARCHAR(120) NOT NULL DEFAULT '',
    smart_contract_audit_url VARCHAR(500) NOT NULL DEFAULT '',
    kyc_provider VARCHAR(180) NOT NULL DEFAULT '',
    kyc_policy_url VARCHAR(500) NOT NULL DEFAULT '',
    restricted_jurisdictions TEXT NOT NULL DEFAULT '',
    legal_entity_name VARCHAR(220) NOT NULL DEFAULT '',
    controller_contact VARCHAR(220) NOT NULL DEFAULT '',
    participation_terms_url VARCHAR(500) NOT NULL DEFAULT '',
    privacy_notice_url VARCHAR(500) NOT NULL DEFAULT '',
    risk_disclosure_url VARCHAR(500) NOT NULL DEFAULT '',
    mailgun_dns_verified BOOLEAN NOT NULL DEFAULT FALSE,
    spf_verified BOOLEAN NOT NULL DEFAULT FALSE,
    dkim_verified BOOLEAN NOT NULL DEFAULT FALSE,
    dmarc_verified BOOLEAN NOT NULL DEFAULT FALSE,
    production_smoke_test_passed BOOLEAN NOT NULL DEFAULT FALSE,
    monitoring_configured BOOLEAN NOT NULL DEFAULT FALSE,
    alerting_configured BOOLEAN NOT NULL DEFAULT FALSE,
    backups_configured BOOLEAN NOT NULL DEFAULT FALSE,
    business_approved BOOLEAN NOT NULL DEFAULT FALSE,
    legal_approved BOOLEAN NOT NULL DEFAULT FALSE,
    technical_approved BOOLEAN NOT NULL DEFAULT FALSE,
    published BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by INTEGER NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ico_readiness_updated_by FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE SET NULL
);

INSERT INTO
    ico_production_readiness (id)
VALUES
    (1) ON CONFLICT (id) DO NOTHING;
