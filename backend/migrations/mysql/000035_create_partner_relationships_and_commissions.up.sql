CREATE TABLE IF NOT EXISTS partner_relationships (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sponsor_user_id BIGINT NOT NULL REFERENCES users(id),
    partner_user_id BIGINT NOT NULL UNIQUE REFERENCES users(id),
    relationship_type TEXT NOT NULL,
    source_application_id BIGINT REFERENCES partner_applications(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_partner_relationships_sponsor_user_id ON partner_relationships(sponsor_user_id);
CREATE INDEX IF NOT EXISTS idx_partner_relationships_relationship_type ON partner_relationships(relationship_type);

CREATE TABLE IF NOT EXISTS partner_commission_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    direct_clients INTEGER NOT NULL DEFAULT 0,
    sub_ib_count INTEGER NOT NULL DEFAULT 0,
    notional_volume_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    gross_commission_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    rebate_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    net_commission_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE(user_id, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_partner_commission_metrics_user_id ON partner_commission_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_partner_commission_metrics_period ON partner_commission_metrics(period_start, period_end);
