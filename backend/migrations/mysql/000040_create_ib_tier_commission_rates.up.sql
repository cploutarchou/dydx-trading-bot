CREATE TABLE IF NOT EXISTS ib_tier_commission_rates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tier_level INTEGER NOT NULL UNIQUE,
    commission_rate_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    rebate_rate_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_by_user_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ib_tier_commission_rates_tier_level ON ib_tier_commission_rates(tier_level);
CREATE INDEX IF NOT EXISTS idx_ib_tier_commission_rates_is_active ON ib_tier_commission_rates(is_active);

-- Seed defaults
INSERT IGNORE INTO ib_tier_commission_rates (tier_level, commission_rate_pct, rebate_rate_pct, description, is_active)
VALUES
    (1, 30.0, 5.0, 'Direct referral (tier 1)', 1),
    (2, 15.0, 2.5, 'Second-level referral (tier 2)', 1),
    (3, 7.5,  1.0, 'Third-level referral (tier 3)', 1);
