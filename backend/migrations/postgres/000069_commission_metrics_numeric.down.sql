ALTER TABLE partner_commission_metrics
    ALTER COLUMN notional_volume_usd TYPE DOUBLE PRECISION USING notional_volume_usd::DOUBLE PRECISION,
    ALTER COLUMN gross_commission_usd TYPE DOUBLE PRECISION USING gross_commission_usd::DOUBLE PRECISION,
    ALTER COLUMN rebate_usd TYPE DOUBLE PRECISION USING rebate_usd::DOUBLE PRECISION,
    ALTER COLUMN net_commission_usd TYPE DOUBLE PRECISION USING net_commission_usd::DOUBLE PRECISION;
