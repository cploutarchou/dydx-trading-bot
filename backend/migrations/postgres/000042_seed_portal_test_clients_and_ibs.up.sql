-- Seed data for CRM/IB portal testing
-- Unique marker: seed_portal_20260411
-- This dataset is intentionally removable via the matching down migration.

-- -----------------------------------------------------------------------------
-- 1) Seed users (CRM clients + IB/sub-IB hierarchy)
-- -----------------------------------------------------------------------------
-- Password hash below is bcrypt for a known dev-only secret.
-- Keep this migration for non-production/testing usage only.

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
    'seed_portal_20260411_ib_atlas',
    'seed_portal_20260411_ib_atlas@seed.local',
    'ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed IB Atlas',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_20260411_ib_nova',
    'seed_portal_20260411_ib_nova@seed.local',
    'ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed IB Nova',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_20260411_sub_ib_atlas_1',
    'seed_portal_20260411_sub_ib_atlas_1@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Sub-IB Atlas 1',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_20260411_sub_ib_nova_1',
    'seed_portal_20260411_sub_ib_nova_1@seed.local',
    'sub_ib',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Sub-IB Nova 1',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_20260411_client_alpha_1',
    'seed_portal_20260411_client_alpha_1@seed.local',
    'client',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Client Alpha 1',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_20260411_client_alpha_2',
    'seed_portal_20260411_client_alpha_2@seed.local',
    'client',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Client Alpha 2',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_20260411_client_beta_1',
    'seed_portal_20260411_client_beta_1@seed.local',
    'client',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Client Beta 1',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'seed_portal_20260411_client_nova_1',
    'seed_portal_20260411_client_nova_1@seed.local',
    'client',
    '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
    'Seed Client Nova 1',
    '',
    TRUE,
    FALSE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  )
ON CONFLICT (username) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2) Seed partner relationships (IB hierarchy)
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
    ('seed_portal_20260411_ib_atlas', 'seed_portal_20260411_sub_ib_atlas_1', 'sub_ib'),
    ('seed_portal_20260411_ib_atlas', 'seed_portal_20260411_client_alpha_1', 'client'),
    ('seed_portal_20260411_ib_atlas', 'seed_portal_20260411_client_alpha_2', 'client'),
    ('seed_portal_20260411_sub_ib_atlas_1', 'seed_portal_20260411_client_beta_1', 'client'),
    ('seed_portal_20260411_ib_nova', 'seed_portal_20260411_sub_ib_nova_1', 'sub_ib'),
    ('seed_portal_20260411_ib_nova', 'seed_portal_20260411_client_nova_1', 'client')
) AS mapping(sponsor_username, partner_username, relationship_type)
JOIN users sponsor ON sponsor.username = mapping.sponsor_username
JOIN users partner ON partner.username = mapping.partner_username
ON CONFLICT (partner_user_id) DO UPDATE
SET
  sponsor_user_id = EXCLUDED.sponsor_user_id,
  relationship_type = EXCLUDED.relationship_type,
  is_active = EXCLUDED.is_active,
  updated_at = EXCLUDED.updated_at;

-- -----------------------------------------------------------------------------
-- 3) Seed commission metrics for IB/sub-IB accounts
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
  CURRENT_TIMESTAMP - INTERVAL '30 days',
  CURRENT_TIMESTAMP,
  metrics.direct_clients,
  metrics.sub_ib_count,
  metrics.notional_volume_usd,
  metrics.gross_commission_usd,
  metrics.rebate_usd,
  metrics.net_commission_usd,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM (
  VALUES
    ('seed_portal_20260411_ib_atlas', 2, 1, 1250000.00, 3850.00, 880.00, 2970.00),
    ('seed_portal_20260411_sub_ib_atlas_1', 1, 0, 420000.00, 1140.00, 240.00, 900.00),
    ('seed_portal_20260411_ib_nova', 1, 1, 860000.00, 2490.00, 520.00, 1970.00),
    ('seed_portal_20260411_sub_ib_nova_1', 0, 0, 190000.00, 480.00, 120.00, 360.00)
) AS metrics(username, direct_clients, sub_ib_count, notional_volume_usd, gross_commission_usd, rebate_usd, net_commission_usd)
JOIN users u ON u.username = metrics.username
ON CONFLICT (user_id, period_start, period_end) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 4) Seed partner applications (small QA sample)
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
    (
      'seed_portal_20260411_sub_ib_atlas_1',
      'seed_portal_20260411_ib_atlas',
      'ib',
      'pending',
      'seed_portal_20260411 atlas promotion request',
      'seed_portal_20260411 sub-ib requests IB upgrade',
      '',
      NULL::TEXT,
      NULL::TIMESTAMPTZ,
      INTERVAL '3 days',
      INTERVAL '3 days'
    ),
    (
      'seed_portal_20260411_client_alpha_1',
      'seed_portal_20260411_ib_atlas',
      'sub_ib',
      'approved',
      'seed_portal_20260411 alpha sub-ib application',
      'seed_portal_20260411 client applying for sub-ib',
      'approved in small seed dataset',
      'seed_portal_20260411_ib_atlas',
      CURRENT_TIMESTAMP - INTERVAL '6 days',
      INTERVAL '8 days',
      INTERVAL '6 days'
    ),
    (
      'seed_portal_20260411_client_alpha_2',
      'seed_portal_20260411_ib_atlas',
      'sub_ib',
      'reviewing',
      'seed_portal_20260411 alpha reviewing application',
      'seed_portal_20260411 in manual review queue',
      'reviewing for additional checks',
      'seed_portal_20260411_ib_atlas',
      CURRENT_TIMESTAMP - INTERVAL '2 days',
      INTERVAL '4 days',
      INTERVAL '2 days'
    ),
    (
      'seed_portal_20260411_client_nova_1',
      'seed_portal_20260411_ib_nova',
      'sub_ib',
      'rejected',
      'seed_portal_20260411 nova sub-ib application',
      'seed_portal_20260411 insufficient referral history',
      'rejected for QA visibility',
      'seed_portal_20260411_ib_nova',
      CURRENT_TIMESTAMP - INTERVAL '5 days',
      INTERVAL '10 days',
      INTERVAL '5 days'
    )
) AS app(
  applicant_username,
  sponsor_username,
  requested_role,
  status,
  business_name,
  notes,
  review_notes,
  reviewer_username,
  reviewed_at,
  created_offset,
  updated_offset
)
JOIN users applicant ON applicant.username = app.applicant_username
LEFT JOIN users sponsor ON sponsor.username = app.sponsor_username
LEFT JOIN users reviewer ON reviewer.username = app.reviewer_username
WHERE NOT EXISTS (
  SELECT 1
  FROM partner_applications existing
  WHERE existing.applicant_user_id = applicant.id
    AND existing.business_name = app.business_name
);
