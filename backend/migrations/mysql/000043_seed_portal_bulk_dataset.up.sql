-- Bulk seed data for CRM/IB portal stress testing (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000043_seed_portal_bulk_dataset.up.sql
-- Changes: ON CONFLICT → ON DUPLICATE KEY UPDATE, generate_series → number table, :: → CAST, || → CONCAT, INTERVAL → INTERVAL notation

-- Note: Requires existence of:
-- - users table with id, username, email, role, hashed_password, full_name, avatar, is_active, is_admin, password_change_required, created_at, updated_at
-- - partner_relationships table
-- - partner_commission_metrics table
-- - partner_applications table
-- - invitation_tokens table
-- - ib_tier_commission_rates table

-- Create a temporary numbers table for generate_series equivalent
CREATE TEMPORARY TABLE IF NOT EXISTS numbers (n INT);
INSERT INTO numbers VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9),(10),
(11),(12),(13),(14),(15),(16),(17),(18),(19),(20),
(21),(22),(23),(24),(25),(26),(27),(28),(29),(30),
(31),(32),(33),(34),(35),(36),(37),(38),(39),(40),
(41),(42),(43),(44),(45),(46),(47),(48),(49),(50),
(51),(52),(53),(54),(55),(56),(57),(58),(59),(60);

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) Seed users (IBs, sub-IBs, and many clients)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT IGNORE INTO users (
  username,
  email,
  role,
  hashed_password,
  full_name,
  avatar,
  is_active,
  is_admin,
  password_change_required,
  created_at,
  updated_at
)
VALUES
  (
    'seed_portal_bulk_20260411_ib_atlas',
    'seed_portal_bulk_20260411_ib_atlas@seed.local',
    'ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk IB Atlas',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_ib_nova',
    'seed_portal_bulk_20260411_ib_nova@seed.local',
    'ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk IB Nova',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_ib_orion',
    'seed_portal_bulk_20260411_ib_orion@seed.local',
    'ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk IB Orion',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_sub_ib_atlas_1',
    'seed_portal_bulk_20260411_sub_ib_atlas_1@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk Sub-IB Atlas 1',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_sub_ib_atlas_2',
    'seed_portal_bulk_20260411_sub_ib_atlas_2@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk Sub-IB Atlas 2',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_sub_ib_atlas_3',
    'seed_portal_bulk_20260411_sub_ib_atlas_3@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk Sub-IB Atlas 3',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_sub_ib_nova_1',
    'seed_portal_bulk_20260411_sub_ib_nova_1@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk Sub-IB Nova 1',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_sub_ib_nova_2',
    'seed_portal_bulk_20260411_sub_ib_nova_2@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk Sub-IB Nova 2',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_sub_ib_nova_3',
    'seed_portal_bulk_20260411_sub_ib_nova_3@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk Sub-IB Nova 3',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_sub_ib_orion_1',
    'seed_portal_bulk_20260411_sub_ib_orion_1@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk Sub-IB Orion 1',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_sub_ib_orion_2',
    'seed_portal_bulk_20260411_sub_ib_orion_2@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk Sub-IB Orion 2',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_bulk_20260411_sub_ib_orion_3',
    'seed_portal_bulk_20260411_sub_ib_orion_3@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Bulk Sub-IB Orion 3',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  );

-- Insert 60 client users (using temporary numbers table)
INSERT IGNORE INTO users (
  username,
  email,
  role,
  hashed_password,
  full_name,
  avatar,
  is_active,
  is_admin,
  password_change_required,
  created_at,
  updated_at
)
SELECT
  CONCAT('seed_portal_bulk_20260411_client_', LPAD(n, 3, '0')) AS username,
  CONCAT('seed_portal_bulk_20260411_client_', LPAD(n, 3, '0'), '@seed.local') AS email,
  'client' AS role,
  '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra' AS hashed_password,
  CONCAT('Seed Bulk Client ', LPAD(n, 3, '0')) AS full_name,
  '' AS avatar,
  TRUE AS is_active,
  FALSE AS is_admin,
  TRUE AS password_change_required,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM numbers;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) Seed partner hierarchy relationships
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO partner_relationships (
  sponsor_user_id,
  partner_user_id,
  relationship_type,
  source_application_id,
  is_active,
  created_at,
  updated_at
)
SELECT
  sponsor.id,
  partner.id,
  mapping.relationship_type,
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM (
  SELECT 'seed_portal_bulk_20260411_ib_atlas' as sponsor_username, 'seed_portal_bulk_20260411_sub_ib_atlas_1' as partner_username, 'sub_ib' as relationship_type UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_atlas', 'seed_portal_bulk_20260411_sub_ib_atlas_2', 'sub_ib' UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_atlas', 'seed_portal_bulk_20260411_sub_ib_atlas_3', 'sub_ib' UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_sub_ib_nova_1', 'sub_ib' UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_sub_ib_nova_2', 'sub_ib' UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_sub_ib_nova_3', 'sub_ib' UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_sub_ib_orion_1', 'sub_ib' UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_sub_ib_orion_2', 'sub_ib' UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_sub_ib_orion_3', 'sub_ib'
) AS mapping
JOIN users sponsor ON sponsor.username = mapping.sponsor_username
JOIN users partner ON partner.username = mapping.partner_username
ON DUPLICATE KEY UPDATE
  sponsor_user_id = VALUES(sponsor_user_id),
  relationship_type = VALUES(relationship_type),
  is_active = VALUES(is_active),
  updated_at = VALUES(updated_at);

-- Client relationships (distributed among sub-IBs and top IBs)
INSERT INTO partner_relationships (
  sponsor_user_id,
  partner_user_id,
  relationship_type,
  source_application_id,
  is_active,
  created_at,
  updated_at
)
SELECT
  sponsor.id,
  client.id,
  'client',
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM numbers n
JOIN users client ON client.username = CONCAT('seed_portal_bulk_20260411_client_', LPAD(n.n, 3, '0'))
JOIN users sponsor ON sponsor.username = CASE
  WHEN MOD(n.n, 12) = 1 THEN 'seed_portal_bulk_20260411_sub_ib_atlas_1'
  WHEN MOD(n.n, 12) = 2 THEN 'seed_portal_bulk_20260411_sub_ib_atlas_2'
  WHEN MOD(n.n, 12) = 3 THEN 'seed_portal_bulk_20260411_sub_ib_atlas_3'
  WHEN MOD(n.n, 12) = 4 THEN 'seed_portal_bulk_20260411_sub_ib_nova_1'
  WHEN MOD(n.n, 12) = 5 THEN 'seed_portal_bulk_20260411_sub_ib_nova_2'
  WHEN MOD(n.n, 12) = 6 THEN 'seed_portal_bulk_20260411_sub_ib_nova_3'
  WHEN MOD(n.n, 12) = 7 THEN 'seed_portal_bulk_20260411_sub_ib_orion_1'
  WHEN MOD(n.n, 12) = 8 THEN 'seed_portal_bulk_20260411_sub_ib_orion_2'
  WHEN MOD(n.n, 12) = 9 THEN 'seed_portal_bulk_20260411_sub_ib_orion_3'
  WHEN MOD(n.n, 12) = 10 THEN 'seed_portal_bulk_20260411_ib_atlas'
  WHEN MOD(n.n, 12) = 11 THEN 'seed_portal_bulk_20260411_ib_nova'
  ELSE 'seed_portal_bulk_20260411_ib_orion'
END
ON DUPLICATE KEY UPDATE
  sponsor_user_id = VALUES(sponsor_user_id),
  relationship_type = VALUES(relationship_type),
  is_active = VALUES(is_active),
  updated_at = VALUES(updated_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3) Seed commission metrics (IB + sub-IB users)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO partner_commission_metrics (
  user_id,
  period_start,
  period_end,
  direct_clients,
  sub_ib_count,
  notional_volume_usd,
  gross_commission_usd,
  rebate_usd,
  net_commission_usd,
  created_at,
  updated_at
)
SELECT
  u.id,
  DATE_SUB(LAST_DAY(DATE_SUB(CURRENT_DATE, INTERVAL 1 DAY)), INTERVAL 1 DAY),
  LAST_DAY(DATE_SUB(CURRENT_DATE, INTERVAL 1 DAY)),
  m.direct_clients,
  m.sub_ib_count,
  m.notional_volume_usd,
  m.gross_commission_usd,
  m.rebate_usd,
  m.net_commission_usd,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM (
  SELECT 'seed_portal_bulk_20260411_ib_atlas' as username, 8 as direct_clients, 3 as sub_ib_count, 3450000.00 as notional_volume_usd, 10620.00 as gross_commission_usd, 2480.00 as rebate_usd, 8140.00 as net_commission_usd UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_nova', 8, 3, 3120000.00, 9720.00, 2240.00, 7480.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_ib_orion', 8, 3, 2980000.00, 9140.00, 2080.00, 7060.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_atlas_1', 5, 0, 920000.00, 2550.00, 610.00, 1940.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_atlas_2', 5, 0, 870000.00, 2390.00, 560.00, 1830.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_atlas_3', 5, 0, 810000.00, 2230.00, 520.00, 1710.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_nova_1', 5, 0, 880000.00, 2430.00, 580.00, 1850.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_nova_2', 5, 0, 760000.00, 2090.00, 500.00, 1590.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_nova_3', 5, 0, 705000.00, 1935.00, 455.00, 1480.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_orion_1', 5, 0, 835000.00, 2300.00, 545.00, 1755.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_orion_2', 5, 0, 790000.00, 2170.00, 520.00, 1650.00 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_orion_3', 4, 0, 640000.00, 1760.00, 420.00, 1340.00
) AS m
JOIN users u ON u.username = m.username
ON DUPLICATE KEY UPDATE
  direct_clients = VALUES(direct_clients),
  sub_ib_count = VALUES(sub_ib_count),
  notional_volume_usd = VALUES(notional_volume_usd),
  gross_commission_usd = VALUES(gross_commission_usd),
  rebate_usd = VALUES(rebate_usd),
  net_commission_usd = VALUES(net_commission_usd),
  updated_at = VALUES(updated_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4) Seed partner applications
-- ─────────────────────────────────────────────────────────────────────────────

INSERT IGNORE INTO partner_applications (
  applicant_user_id,
  sponsor_user_id,
  requested_role,
  status,
  business_name,
  notes,
  review_notes,
  reviewed_by_user_id,
  reviewed_at,
  created_at,
  updated_at
)
SELECT
  applicant.id,
  COALESCE(sponsor.id, 0),
  app.requested_role,
  app.status,
  app.business_name,
  app.notes,
  app.review_notes,
  COALESCE(reviewer.id, NULL),
  CASE WHEN app.reviewer_username IS NOT NULL THEN DATE_SUB(CURRENT_TIMESTAMP, INTERVAL app.hours_back_updated HOUR) ELSE NULL END,
  DATE_SUB(CURRENT_TIMESTAMP, INTERVAL app.hours_back_created HOUR),
  DATE_SUB(CURRENT_TIMESTAMP, INTERVAL app.hours_back_updated HOUR)
FROM (
  SELECT 'seed_portal_bulk_20260411_sub_ib_atlas_1' as applicant_username, 'seed_portal_bulk_20260411_ib_atlas' as sponsor_username, 'ib' as requested_role, 'pending' as status, 'seed_portal_bulk_20260411 business atlas pending' as business_name, 'seed_portal_bulk_20260411 pending review' as notes, '' as review_notes, NULL as reviewer_username, 96 as hours_back_created, 96 as hours_back_updated UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_atlas_2', 'seed_portal_bulk_20260411_ib_atlas', 'ib', 'reviewing', 'seed_portal_bulk_20260411 business atlas reviewing', 'seed_portal_bulk_20260411 active manual review', 'reviewing with compliance checks', 'seed_portal_bulk_20260411_ib_atlas', 144, 72 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_nova_2', 'seed_portal_bulk_20260411_ib_nova', 'ib', 'approved', 'seed_portal_bulk_20260411 business nova approved', 'seed_portal_bulk_20260411 approved case', 'approved in bulk seed', 'seed_portal_bulk_20260411_ib_nova', 288, 240 UNION ALL
  SELECT 'seed_portal_bulk_20260411_sub_ib_orion_3', 'seed_portal_bulk_20260411_ib_orion', 'ib', 'rejected', 'seed_portal_bulk_20260411 business orion rejected', 'seed_portal_bulk_20260411 rejected case', 'insufficient documentation', 'seed_portal_bulk_20260411_ib_orion', 480, 432 UNION ALL
  SELECT 'seed_portal_bulk_20260411_client_001', 'seed_portal_bulk_20260411_ib_atlas', 'ib', 'pending', 'seed_portal_bulk_20260411 client001 application', 'seed_portal_bulk_20260411 first-time request', '', NULL, 48, 48 UNION ALL
  SELECT 'seed_portal_bulk_20260411_client_002', 'seed_portal_bulk_20260411_sub_ib_nova_1', 'sub_ib', 'pending', 'seed_portal_bulk_20260411 client002 sub-ib', 'seed_portal_bulk_20260411 wants sub-ib role', '', NULL, 24, 24
) AS app
JOIN users applicant ON applicant.username = app.applicant_username
LEFT JOIN users sponsor ON sponsor.username = app.sponsor_username
LEFT JOIN users reviewer ON reviewer.username = app.reviewer_username;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5) Seed invitation tokens
-- ─────────────────────────────────────────────────────────────────────────────

INSERT IGNORE INTO invitation_tokens (
  token_code,
  label,
  ib_name,
  campaign_name,
  max_uses,
  used_count,
  created_by_user_id,
  last_used_by_user_id,
  expires_at,
  last_used_at,
  revoked_at,
  created_at,
  updated_at
)
SELECT
  t.token_code,
  t.label,
  t.ib_name,
  t.campaign_name,
  t.max_uses,
  t.used_count,
  creator.id,
  COALESCE(last_used.id, NULL),
  DATE_ADD(CURRENT_TIMESTAMP, INTERVAL t.expires_days DAY),
  CASE WHEN t.last_used_days_back > 0 THEN DATE_SUB(CURRENT_TIMESTAMP, INTERVAL t.last_used_days_back DAY) ELSE NULL END,
  CASE WHEN t.revoked_days_back > 0 THEN DATE_SUB(CURRENT_TIMESTAMP, INTERVAL t.revoked_days_back DAY) ELSE NULL END,
  DATE_SUB(CURRENT_TIMESTAMP, INTERVAL t.created_days_back DAY),
  DATE_SUB(CURRENT_TIMESTAMP, INTERVAL t.updated_days_back DAY)
FROM (
  SELECT 'SEED-BULK-20260411-ATLAS-001' as token_code, 'seed_portal_bulk_20260411 Atlas onboarding' as label, 'Atlas IB' as ib_name, 'Q2 Atlas Campaign' as campaign_name, 250 as max_uses, 120 as used_count, 'seed_portal_bulk_20260411_ib_atlas' as creator_username, 'seed_portal_bulk_20260411_client_004' as last_used_username, 90 as expires_days, 1 as last_used_days_back, 0 as revoked_days_back, 30 as created_days_back, 1 as updated_days_back UNION ALL
  SELECT 'SEED-BULK-20260411-ATLAS-002', 'seed_portal_bulk_20260411 Atlas VIP', 'Atlas IB', 'VIP Segment', 40, 7, 'seed_portal_bulk_20260411_ib_atlas', 'seed_portal_bulk_20260411_client_009', 30, 3, 0, 20, 3 UNION ALL
  SELECT 'SEED-BULK-20260411-NOVA-001', 'seed_portal_bulk_20260411 Nova growth', 'Nova IB', 'Q2 Nova Campaign', 150, 88, 'seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_client_021', 75, 0, 0, 25, 0 UNION ALL
  SELECT 'SEED-BULK-20260411-NOVA-002', 'seed_portal_bulk_20260411 Nova expired', 'Nova IB', 'Legacy Campaign', 100, 100, 'seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_client_030', -1, 2, 0, 60, 2 UNION ALL
  SELECT 'SEED-BULK-20260411-ORION-001', 'seed_portal_bulk_20260411 Orion onboarding', 'Orion IB', 'Orion Launch', 200, 55, 'seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_client_042', 120, 5, 0, 40, 5 UNION ALL
  SELECT 'SEED-BULK-20260411-ORION-002', 'seed_portal_bulk_20260411 Orion revoked', 'Orion IB', 'Suspended Test', 60, 9, 'seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_client_045', 50, 12, 10, 35, 10
) AS t
JOIN users creator ON creator.username = t.creator_username
LEFT JOIN users last_used ON last_used.username = t.last_used_username
ON DUPLICATE KEY UPDATE
  max_uses = VALUES(max_uses),
  used_count = VALUES(used_count),
  expires_at = VALUES(expires_at),
  last_used_at = VALUES(last_used_at),
  revoked_at = VALUES(revoked_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- 6) Seed IB tier commission rates
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO ib_tier_commission_rates (
  tier_level,
  commission_rate_pct,
  rebate_rate_pct,
  description,
  is_active,
  created_by_user_id,
  created_at,
  updated_at
)
SELECT
  r.tier_level,
  r.commission_rate_pct,
  r.rebate_rate_pct,
  r.description,
  r.is_active,
  creator.id,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM (
  SELECT 4 as tier_level, 3.50 as commission_rate_pct, 0.70 as rebate_rate_pct, 'seed_portal_bulk_20260411 tier 4' as description, TRUE as is_active, 'seed_portal_bulk_20260411_ib_atlas' as creator_username UNION ALL
  SELECT 5, 1.80, 0.35, 'seed_portal_bulk_20260411 tier 5', TRUE, 'seed_portal_bulk_20260411_ib_nova' UNION ALL
  SELECT 6, 0.90, 0.20, 'seed_portal_bulk_20260411 tier 6', TRUE, 'seed_portal_bulk_20260411_ib_orion'
) AS r
JOIN users creator ON creator.username = r.creator_username
ON DUPLICATE KEY UPDATE
  commission_rate_pct = VALUES(commission_rate_pct),
  rebate_rate_pct = VALUES(rebate_rate_pct),
  description = VALUES(description),
  is_active = VALUES(is_active),
  created_by_user_id = VALUES(created_by_user_id),
  updated_at = VALUES(updated_at);

-- Clean up temporary table
DROP TEMPORARY TABLE IF EXISTS numbers;
