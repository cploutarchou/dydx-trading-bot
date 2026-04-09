CREATE TABLE IF NOT EXISTS partner_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sponsor_user_id INTEGER NOT NULL,
    partner_user_id INTEGER NOT NULL UNIQUE,
    relationship_type TEXT NOT NULL,
    source_application_id INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (sponsor_user_id) REFERENCES users(id),
    FOREIGN KEY (partner_user_id) REFERENCES users(id),
    FOREIGN KEY (source_application_id) REFERENCES partner_applications(id)
);

CREATE INDEX IF NOT EXISTS idx_partner_relationships_sponsor_user_id ON partner_relationships(sponsor_user_id);
CREATE INDEX IF NOT EXISTS idx_partner_relationships_relationship_type ON partner_relationships(relationship_type);

CREATE TABLE IF NOT EXISTS partner_commission_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    period_start DATETIME NOT NULL,
    period_end DATETIME NOT NULL,
    direct_clients INTEGER NOT NULL DEFAULT 0,
    sub_ib_count INTEGER NOT NULL DEFAULT 0,
    notional_volume_usd REAL NOT NULL DEFAULT 0,
    gross_commission_usd REAL NOT NULL DEFAULT 0,
    rebate_usd REAL NOT NULL DEFAULT 0,
    net_commission_usd REAL NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_partner_commission_metrics_user_id ON partner_commission_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_partner_commission_metrics_period ON partner_commission_metrics(period_start, period_end);
