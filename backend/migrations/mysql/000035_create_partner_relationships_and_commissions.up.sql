CREATE TABLE IF NOT EXISTS partner_relationships (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sponsor_user_id BIGINT NOT NULL,
    partner_user_id BIGINT NOT NULL UNIQUE,
    relationship_type TEXT NOT NULL,
    source_application_id BIGINT,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_partner_relationships_sponsor_user_id ON partner_relationships(sponsor_user_id);
CREATE INDEX IF NOT EXISTS idx_partner_relationships_relationship_type ON partner_relationships(relationship_type);

CREATE TABLE IF NOT EXISTS partner_commission_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    direct_clients INTEGER NOT NULL DEFAULT 0,
    sub_ib_count INTEGER NOT NULL DEFAULT 0,
    notional_volume_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    gross_commission_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    rebate_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    net_commission_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    UNIQUE(user_id, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_partner_commission_metrics_user_id ON partner_commission_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_partner_commission_metrics_period ON partner_commission_metrics(period_start, period_end);
