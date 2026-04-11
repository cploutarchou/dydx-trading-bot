-- Bulk seed data for CRM/IB portal stress testing
-- Unique marker: seed_portal_bulk_20260411
-- This dataset is intentionally removable via the matching down migration.

-- -----------------------------------------------------------------------------
-- 1) Seed users (IBs, sub-IBs, and many clients)
-- -----------------------------------------------------------------------------

INSERT INTO users (
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
  )
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (
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
  'seed_portal_bulk_20260411_client_' || LPAD(gs::TEXT, 3, '0') AS username,
  'seed_portal_bulk_20260411_client_' || LPAD(gs::TEXT, 3, '0') || '@seed.local' AS email,
  'client' AS role,
  '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra' AS hashed_password,
  'Seed Bulk Client ' || LPAD(gs::TEXT, 3, '0') AS full_name,
  '' AS avatar,
  TRUE AS is_active,
  FALSE AS is_admin,
  TRUE AS password_change_required,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM generate_series(1, 60) AS gs
ON CONFLICT (username) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2) Seed partner hierarchy relationships
-- -----------------------------------------------------------------------------

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
  VALUES
    ('seed_portal_bulk_20260411_ib_atlas', 'seed_portal_bulk_20260411_sub_ib_atlas_1', 'sub_ib'),
    ('seed_portal_bulk_20260411_ib_atlas', 'seed_portal_bulk_20260411_sub_ib_atlas_2', 'sub_ib'),
    ('seed_portal_bulk_20260411_ib_atlas', 'seed_portal_bulk_20260411_sub_ib_atlas_3', 'sub_ib'),
    ('seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_sub_ib_nova_1', 'sub_ib'),
    ('seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_sub_ib_nova_2', 'sub_ib'),
    ('seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_sub_ib_nova_3', 'sub_ib'),
    ('seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_sub_ib_orion_1', 'sub_ib'),
    ('seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_sub_ib_orion_2', 'sub_ib'),
    ('seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_sub_ib_orion_3', 'sub_ib')
) AS mapping(sponsor_username, partner_username, relationship_type)
JOIN users sponsor ON sponsor.username = mapping.sponsor_username
JOIN users partner ON partner.username = mapping.partner_username
ON CONFLICT (partner_user_id) DO UPDATE
SET
  sponsor_user_id = EXCLUDED.sponsor_user_id,
  relationship_type = EXCLUDED.relationship_type,
  is_active = EXCLUDED.is_active,
  updated_at = EXCLUDED.updated_at;

WITH bulk_clients AS (
  SELECT
    username,
    ROW_NUMBER() OVER (ORDER BY username) AS idx
  FROM users
  WHERE username LIKE 'seed_portal_bulk_20260411_client_%'
),
client_mapping AS (
  SELECT
    username AS partner_username,
    CASE
      WHEN idx % 12 = 1 THEN 'seed_portal_bulk_20260411_sub_ib_atlas_1'
      WHEN idx % 12 = 2 THEN 'seed_portal_bulk_20260411_sub_ib_atlas_2'
      WHEN idx % 12 = 3 THEN 'seed_portal_bulk_20260411_sub_ib_atlas_3'
      WHEN idx % 12 = 4 THEN 'seed_portal_bulk_20260411_sub_ib_nova_1'
      WHEN idx % 12 = 5 THEN 'seed_portal_bulk_20260411_sub_ib_nova_2'
      WHEN idx % 12 = 6 THEN 'seed_portal_bulk_20260411_sub_ib_nova_3'
      WHEN idx % 12 = 7 THEN 'seed_portal_bulk_20260411_sub_ib_orion_1'
      WHEN idx % 12 = 8 THEN 'seed_portal_bulk_20260411_sub_ib_orion_2'
      WHEN idx % 12 = 9 THEN 'seed_portal_bulk_20260411_sub_ib_orion_3'
      WHEN idx % 12 = 10 THEN 'seed_portal_bulk_20260411_ib_atlas'
      WHEN idx % 12 = 11 THEN 'seed_portal_bulk_20260411_ib_nova'
      ELSE 'seed_portal_bulk_20260411_ib_orion'
    END AS sponsor_username
  FROM bulk_clients
)
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
FROM client_mapping m
JOIN users sponsor ON sponsor.username = m.sponsor_username
JOIN users client ON client.username = m.partner_username
ON CONFLICT (partner_user_id) DO UPDATE
SET
  sponsor_user_id = EXCLUDED.sponsor_user_id,
  relationship_type = EXCLUDED.relationship_type,
  is_active = EXCLUDED.is_active,
  updated_at = EXCLUDED.updated_at;

-- -----------------------------------------------------------------------------
-- 3) Seed commission metrics (IB + sub-IB users)
-- -----------------------------------------------------------------------------

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
  DATE_TRUNC('month', CURRENT_TIMESTAMP) - INTERVAL '1 month',
  DATE_TRUNC('month', CURRENT_TIMESTAMP),
  m.direct_clients,
  m.sub_ib_count,
  m.notional_volume_usd,
  m.gross_commission_usd,
  m.rebate_usd,
  m.net_commission_usd,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM (
  VALUES
    ('seed_portal_bulk_20260411_ib_atlas', 8, 3, 3450000.00, 10620.00, 2480.00, 8140.00),
    ('seed_portal_bulk_20260411_ib_nova', 8, 3, 3120000.00, 9720.00, 2240.00, 7480.00),
    ('seed_portal_bulk_20260411_ib_orion', 8, 3, 2980000.00, 9140.00, 2080.00, 7060.00),
    ('seed_portal_bulk_20260411_sub_ib_atlas_1', 5, 0, 920000.00, 2550.00, 610.00, 1940.00),
    ('seed_portal_bulk_20260411_sub_ib_atlas_2', 5, 0, 870000.00, 2390.00, 560.00, 1830.00),
    ('seed_portal_bulk_20260411_sub_ib_atlas_3', 5, 0, 810000.00, 2230.00, 520.00, 1710.00),
    ('seed_portal_bulk_20260411_sub_ib_nova_1', 5, 0, 880000.00, 2430.00, 580.00, 1850.00),
    ('seed_portal_bulk_20260411_sub_ib_nova_2', 5, 0, 760000.00, 2090.00, 500.00, 1590.00),
    ('seed_portal_bulk_20260411_sub_ib_nova_3', 5, 0, 705000.00, 1935.00, 455.00, 1480.00),
    ('seed_portal_bulk_20260411_sub_ib_orion_1', 5, 0, 835000.00, 2300.00, 545.00, 1755.00),
    ('seed_portal_bulk_20260411_sub_ib_orion_2', 5, 0, 790000.00, 2170.00, 520.00, 1650.00),
    ('seed_portal_bulk_20260411_sub_ib_orion_3', 4, 0, 640000.00, 1760.00, 420.00, 1340.00)
) AS m(username, direct_clients, sub_ib_count, notional_volume_usd, gross_commission_usd, rebate_usd, net_commission_usd)
JOIN users u ON u.username = m.username
ON CONFLICT (user_id, period_start, period_end) DO UPDATE
SET
  direct_clients = EXCLUDED.direct_clients,
  sub_ib_count = EXCLUDED.sub_ib_count,
  notional_volume_usd = EXCLUDED.notional_volume_usd,
  gross_commission_usd = EXCLUDED.gross_commission_usd,
  rebate_usd = EXCLUDED.rebate_usd,
  net_commission_usd = EXCLUDED.net_commission_usd,
  updated_at = EXCLUDED.updated_at;

-- -----------------------------------------------------------------------------
-- 4) Seed partner applications (pending + reviewed scenarios)
-- -----------------------------------------------------------------------------

INSERT INTO partner_applications (
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
  sponsor.id,
  app.requested_role,
  app.status,
  app.business_name,
  app.notes,
  app.review_notes,
  reviewer.id,
  app.reviewed_at,
  CURRENT_TIMESTAMP - app.created_offset,
  CURRENT_TIMESTAMP - app.updated_offset
FROM (
  VALUES
    ('seed_portal_bulk_20260411_sub_ib_atlas_1', 'seed_portal_bulk_20260411_ib_atlas', 'ib', 'pending',  'seed_portal_bulk_20260411 business atlas pending',  'seed_portal_bulk_20260411 pending review', '', NULL::TEXT, INTERVAL '4 days', INTERVAL '4 days'),
    ('seed_portal_bulk_20260411_sub_ib_atlas_2', 'seed_portal_bulk_20260411_ib_atlas', 'ib', 'reviewing', 'seed_portal_bulk_20260411 business atlas reviewing', 'seed_portal_bulk_20260411 active manual review', 'reviewing with compliance checks', 'seed_portal_bulk_20260411_ib_atlas', INTERVAL '6 days', INTERVAL '3 days'),
    ('seed_portal_bulk_20260411_sub_ib_nova_2',  'seed_portal_bulk_20260411_ib_nova',  'ib', 'approved', 'seed_portal_bulk_20260411 business nova approved', 'seed_portal_bulk_20260411 approved case', 'approved in bulk seed', 'seed_portal_bulk_20260411_ib_nova', INTERVAL '12 days', INTERVAL '10 days'),
    ('seed_portal_bulk_20260411_sub_ib_orion_3', 'seed_portal_bulk_20260411_ib_orion', 'ib', 'rejected', 'seed_portal_bulk_20260411 business orion rejected', 'seed_portal_bulk_20260411 rejected case', 'insufficient documentation', 'seed_portal_bulk_20260411_ib_orion', INTERVAL '20 days', INTERVAL '18 days'),
    ('seed_portal_bulk_20260411_client_001',     'seed_portal_bulk_20260411_ib_atlas', 'ib', 'pending',  'seed_portal_bulk_20260411 client001 application', 'seed_portal_bulk_20260411 first-time request', '', NULL::TEXT, INTERVAL '2 days', INTERVAL '2 days'),
    ('seed_portal_bulk_20260411_client_002',     'seed_portal_bulk_20260411_sub_ib_nova_1', 'sub_ib', 'pending', 'seed_portal_bulk_20260411 client002 sub-ib', 'seed_portal_bulk_20260411 wants sub-ib role', '', NULL::TEXT, INTERVAL '1 day', INTERVAL '1 day')
) AS app(applicant_username, sponsor_username, requested_role, status, business_name, notes, review_notes, reviewer_username, created_offset, updated_offset)
JOIN users applicant ON applicant.username = app.applicant_username
LEFT JOIN users sponsor ON sponsor.username = app.sponsor_username
LEFT JOIN users reviewer ON reviewer.username = app.reviewer_username
WHERE NOT EXISTS (
  SELECT 1
  FROM partner_applications existing
  WHERE existing.applicant_user_id = applicant.id
    AND existing.business_name = app.business_name
);

-- -----------------------------------------------------------------------------
-- 5) Seed invitation tokens for IB portal workflows
-- -----------------------------------------------------------------------------

INSERT INTO invitation_tokens (
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
  last_used.id,
  t.expires_at,
  t.last_used_at,
  t.revoked_at,
  CURRENT_TIMESTAMP - t.created_offset,
  CURRENT_TIMESTAMP - t.updated_offset
FROM (
  VALUES
    ('SEED-BULK-20260411-ATLAS-001', 'seed_portal_bulk_20260411 Atlas onboarding', 'Atlas IB', 'Q2 Atlas Campaign', 250, 120, 'seed_portal_bulk_20260411_ib_atlas', 'seed_portal_bulk_20260411_client_004', CURRENT_TIMESTAMP + INTERVAL '90 days', CURRENT_TIMESTAMP - INTERVAL '1 day', NULL::timestamptz, INTERVAL '30 days', INTERVAL '1 day'),
    ('SEED-BULK-20260411-ATLAS-002', 'seed_portal_bulk_20260411 Atlas VIP', 'Atlas IB', 'VIP Segment', 40, 7, 'seed_portal_bulk_20260411_ib_atlas', 'seed_portal_bulk_20260411_client_009', CURRENT_TIMESTAMP + INTERVAL '30 days', CURRENT_TIMESTAMP - INTERVAL '3 days', NULL::timestamptz, INTERVAL '20 days', INTERVAL '3 days'),
    ('SEED-BULK-20260411-NOVA-001',  'seed_portal_bulk_20260411 Nova growth', 'Nova IB', 'Q2 Nova Campaign', 150, 88, 'seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_client_021', CURRENT_TIMESTAMP + INTERVAL '75 days', CURRENT_TIMESTAMP - INTERVAL '6 hours', NULL::timestamptz, INTERVAL '25 days', INTERVAL '6 hours'),
    ('SEED-BULK-20260411-NOVA-002',  'seed_portal_bulk_20260411 Nova expired', 'Nova IB', 'Legacy Campaign', 100, 100, 'seed_portal_bulk_20260411_ib_nova', 'seed_portal_bulk_20260411_client_030', CURRENT_TIMESTAMP - INTERVAL '1 day', CURRENT_TIMESTAMP - INTERVAL '2 days', NULL::timestamptz, INTERVAL '60 days', INTERVAL '2 days'),
    ('SEED-BULK-20260411-ORION-001', 'seed_portal_bulk_20260411 Orion onboarding', 'Orion IB', 'Orion Launch', 200, 55, 'seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_client_042', CURRENT_TIMESTAMP + INTERVAL '120 days', CURRENT_TIMESTAMP - INTERVAL '5 days', NULL::timestamptz, INTERVAL '40 days', INTERVAL '5 days'),
    ('SEED-BULK-20260411-ORION-002', 'seed_portal_bulk_20260411 Orion revoked', 'Orion IB', 'Suspended Test', 60, 9, 'seed_portal_bulk_20260411_ib_orion', 'seed_portal_bulk_20260411_client_045', CURRENT_TIMESTAMP + INTERVAL '50 days', CURRENT_TIMESTAMP - INTERVAL '12 days', CURRENT_TIMESTAMP - INTERVAL '10 days', INTERVAL '35 days', INTERVAL '10 days')
) AS t(token_code, label, ib_name, campaign_name, max_uses, used_count, creator_username, last_used_username, expires_at, last_used_at, revoked_at, created_offset, updated_offset)
JOIN users creator ON creator.username = t.creator_username
LEFT JOIN users last_used ON last_used.username = t.last_used_username
ON CONFLICT (token_code) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 6) Seed additional IB tier rates for stress/UI scenarios
-- -----------------------------------------------------------------------------

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
  VALUES
    (4, 3.50, 0.70, 'seed_portal_bulk_20260411 tier 4', TRUE, 'seed_portal_bulk_20260411_ib_atlas'),
    (5, 1.80, 0.35, 'seed_portal_bulk_20260411 tier 5', TRUE, 'seed_portal_bulk_20260411_ib_nova'),
    (6, 0.90, 0.20, 'seed_portal_bulk_20260411 tier 6', TRUE, 'seed_portal_bulk_20260411_ib_orion')
) AS r(tier_level, commission_rate_pct, rebate_rate_pct, description, is_active, creator_username)
JOIN users creator ON creator.username = r.creator_username
ON CONFLICT (tier_level) DO UPDATE
SET
  commission_rate_pct = EXCLUDED.commission_rate_pct,
  rebate_rate_pct = EXCLUDED.rebate_rate_pct,
  description = EXCLUDED.description,
  is_active = EXCLUDED.is_active,
  created_by_user_id = EXCLUDED.created_by_user_id,
  updated_at = EXCLUDED.updated_at;
