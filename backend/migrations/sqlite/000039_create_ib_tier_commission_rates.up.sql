CREATE TABLE IF NOT EXISTS ib_tier_commission_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tier_level INTEGER NOT NULL UNIQUE,
    commission_rate_pct REAL NOT NULL DEFAULT 0,
    rebate_rate_pct REAL NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_by_user_id INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_ib_tier_commission_rates_tier_level ON ib_tier_commission_rates(tier_level);
CREATE INDEX IF NOT EXISTS idx_ib_tier_commission_rates_is_active ON ib_tier_commission_rates(is_active);

-- Seed sensible defaults: tier 1 = 30%, tier 2 = 15%, tier 3 = 7.5%
INSERT OR IGNORE INTO ib_tier_commission_rates (tier_level, commission_rate_pct, rebate_rate_pct, description, is_active, created_at, updated_at)
VALUES
    (1, 30.0, 5.0, 'Direct referral (tier 1)', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    (2, 15.0, 2.5, 'Second-level referral (tier 2)', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    (3, 7.5,  1.0, 'Third-level referral (tier 3)', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
