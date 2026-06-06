-- Rollback: Remove bulk seed data
-- Unique marker: seed_portal_bulk_20260411

DELETE FROM partner_commission_metrics
WHERE user_id IN (
  SELECT id FROM users WHERE username LIKE 'seed_portal_bulk_20260411_%'
);

DELETE FROM partner_relationships
WHERE partner_user_id IN (
  SELECT id FROM users WHERE username LIKE 'seed_portal_bulk_20260411_%'
)
   OR sponsor_user_id IN (
  SELECT id FROM users WHERE username LIKE 'seed_portal_bulk_20260411_%'
);

DELETE FROM partner_applications
WHERE applicant_user_id IN (
  SELECT id FROM users WHERE username LIKE 'seed_portal_bulk_20260411_%'
)
   OR sponsor_user_id IN (
  SELECT id FROM users WHERE username LIKE 'seed_portal_bulk_20260411_%'
)
   OR reviewed_by_user_id IN (
  SELECT id FROM users WHERE username LIKE 'seed_portal_bulk_20260411_%'
)
   OR business_name LIKE 'seed_portal_bulk_20260411%'
   OR notes LIKE 'seed_portal_bulk_20260411%'
   OR review_notes LIKE 'seed_portal_bulk_20260411%';

DELETE FROM invitation_tokens
WHERE token_code LIKE 'SEED-BULK-20260411-%'
   OR label LIKE 'seed_portal_bulk_20260411%';

DELETE FROM ib_tier_commission_rates
WHERE description LIKE 'seed_portal_bulk_20260411%';

DELETE FROM users
WHERE username LIKE 'seed_portal_bulk_20260411_%';
