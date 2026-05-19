-- Remove non-production fixture data from runtime databases.
-- Historical seed migrations remain for migration-order compatibility; this
-- migration makes the final migrated state production-data-only.

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
DELETE FROM partner_commission_metrics
WHERE user_id IN (SELECT id FROM seeded_users);

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
DELETE FROM partner_relationships
WHERE partner_user_id IN (SELECT id FROM seeded_users)
   OR sponsor_user_id IN (SELECT id FROM seeded_users);

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
DELETE FROM partner_applications
WHERE applicant_user_id IN (SELECT id FROM seeded_users)
   OR sponsor_user_id IN (SELECT id FROM seeded_users)
   OR reviewed_by_user_id IN (SELECT id FROM seeded_users)
   OR business_name LIKE 'seed_portal_20260411%'
   OR business_name LIKE 'seed_portal_bulk_20260411%'
   OR notes LIKE 'seed_portal_20260411%'
   OR notes LIKE 'seed_portal_bulk_20260411%'
   OR review_notes LIKE 'seed_portal_20260411%'
   OR review_notes LIKE 'seed_portal_bulk_20260411%';

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
DELETE FROM invitation_tokens
WHERE created_by_user_id IN (SELECT id FROM seeded_users)
   OR last_used_by_user_id IN (SELECT id FROM seeded_users)
   OR token_code LIKE 'SEED-BULK-20260411-%'
   OR label LIKE 'seed_portal_bulk_20260411%';

DELETE FROM ib_tier_commission_rates
WHERE description LIKE 'seed_portal_bulk_20260411%';

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
UPDATE audit_logs
SET user_id = NULL
WHERE user_id IN (SELECT id FROM seeded_users);

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
UPDATE backtest_runs
SET user_id = NULL
WHERE user_id IN (SELECT id FROM seeded_users);

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
UPDATE bot_settings
SET updated_by = NULL
WHERE updated_by IN (SELECT id FROM seeded_users);

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
UPDATE custom_roles
SET created_by_user_id = NULL
WHERE created_by_user_id IN (SELECT id FROM seeded_users);

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
UPDATE user_permission_overrides
SET granted_by_user_id = NULL
WHERE granted_by_user_id IN (SELECT id FROM seeded_users);

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
DELETE FROM user_permission_overrides
WHERE user_id IN (SELECT id FROM seeded_users);

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
DELETE FROM user_mfa_credentials
WHERE user_id IN (SELECT id FROM seeded_users);

WITH seeded_users AS (
  SELECT id
  FROM users
  WHERE username LIKE 'seed_portal_20260411_%'
     OR username LIKE 'seed_portal_bulk_20260411_%'
)
DELETE FROM users
WHERE id IN (SELECT id FROM seeded_users);

-- Remove role smoke-test users inserted by 000049 when they are still clean
-- seed accounts. If any of those accounts owns runtime resources, leave it in
-- place rather than deleting data that may now be operational.
WITH role_seed_users AS (
  SELECT id
  FROM users
  WHERE username IN ('user', 'officer', 'ib')
    AND email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
),
deletable_role_seed_users AS (
  SELECT id
  FROM role_seed_users seed
  WHERE NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
UPDATE backtest_runs
SET user_id = NULL
WHERE user_id IN (SELECT id FROM role_seed_users);

WITH role_seed_users AS (
  SELECT id
  FROM users
  WHERE username IN ('user', 'officer', 'ib')
    AND email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
),
deletable_role_seed_users AS (
  SELECT id
  FROM role_seed_users seed
  WHERE NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
UPDATE audit_logs
SET user_id = NULL
WHERE user_id IN (SELECT id FROM deletable_role_seed_users);

WITH role_seed_users AS (
  SELECT id
  FROM users
  WHERE username IN ('user', 'officer', 'ib')
    AND email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
),
deletable_role_seed_users AS (
  SELECT id
  FROM role_seed_users seed
  WHERE NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
UPDATE bot_settings
SET updated_by = NULL
WHERE updated_by IN (SELECT id FROM deletable_role_seed_users);

WITH role_seed_users AS (
  SELECT id
  FROM users
  WHERE username IN ('user', 'officer', 'ib')
    AND email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
),
deletable_role_seed_users AS (
  SELECT id
  FROM role_seed_users seed
  WHERE NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
UPDATE custom_roles
SET created_by_user_id = NULL
WHERE created_by_user_id IN (SELECT id FROM deletable_role_seed_users);

WITH role_seed_users AS (
  SELECT id
  FROM users
  WHERE username IN ('user', 'officer', 'ib')
    AND email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
),
deletable_role_seed_users AS (
  SELECT id
  FROM role_seed_users seed
  WHERE NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
DELETE FROM user_mfa_credentials
WHERE user_id IN (SELECT id FROM deletable_role_seed_users);

WITH role_seed_users AS (
  SELECT id
  FROM users
  WHERE username IN ('user', 'officer', 'ib')
    AND email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
),
deletable_role_seed_users AS (
  SELECT id
  FROM role_seed_users seed
  WHERE NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
DELETE FROM user_permission_overrides
WHERE user_id IN (SELECT id FROM deletable_role_seed_users)
   OR granted_by_user_id IN (SELECT id FROM deletable_role_seed_users);

WITH role_seed_users AS (
  SELECT id
  FROM users
  WHERE username IN ('user', 'officer', 'ib')
    AND email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
),
deletable_role_seed_users AS (
  SELECT id
  FROM role_seed_users seed
  WHERE NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
DELETE FROM users
WHERE id IN (SELECT id FROM deletable_role_seed_users);

-- Remove the historical default admin only if it is still the untouched
-- bootstrap row with the known admin123 hash and owns no runtime resources.
WITH default_admin_seed AS (
  SELECT id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
UPDATE backtest_runs
SET user_id = NULL
WHERE user_id IN (SELECT id FROM default_admin_seed);

WITH default_admin_seed AS (
  SELECT id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
UPDATE audit_logs
SET user_id = NULL
WHERE user_id IN (SELECT id FROM default_admin_seed);

WITH default_admin_seed AS (
  SELECT id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
UPDATE bot_settings
SET updated_by = NULL
WHERE updated_by IN (SELECT id FROM default_admin_seed);

WITH default_admin_seed AS (
  SELECT id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
UPDATE custom_roles
SET created_by_user_id = NULL
WHERE created_by_user_id IN (SELECT id FROM default_admin_seed);

WITH default_admin_seed AS (
  SELECT id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
DELETE FROM user_mfa_credentials
WHERE user_id IN (SELECT id FROM default_admin_seed);

WITH default_admin_seed AS (
  SELECT id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
DELETE FROM user_permission_overrides
WHERE user_id IN (SELECT id FROM default_admin_seed)
   OR granted_by_user_id IN (SELECT id FROM default_admin_seed);

WITH default_admin_seed AS (
  SELECT id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
DELETE FROM users
WHERE id IN (SELECT id FROM default_admin_seed);
