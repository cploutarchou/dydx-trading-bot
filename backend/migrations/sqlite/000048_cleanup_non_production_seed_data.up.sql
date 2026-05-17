-- Remove role smoke-test users inserted by 000044 when they are still clean
-- seed accounts. Runtime-owned accounts are left in place to avoid deleting
-- operational resources from a migrated developer database.

UPDATE backtest_runs
SET user_id = NULL
WHERE user_id IN (
  SELECT id
  FROM users
  WHERE username IN ('user', 'officer', 'ib')
    AND email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
);

UPDATE audit_logs
SET user_id = NULL
WHERE user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username IN ('user', 'officer', 'ib')
    AND seed.email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

UPDATE bot_settings
SET updated_by = NULL
WHERE updated_by IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username IN ('user', 'officer', 'ib')
    AND seed.email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

UPDATE custom_roles
SET created_by_user_id = NULL
WHERE created_by_user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username IN ('user', 'officer', 'ib')
    AND seed.email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

UPDATE custom_roles
SET created_by_user_id = NULL
WHERE created_by_user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

DELETE FROM user_mfa_credentials
WHERE user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username IN ('user', 'officer', 'ib')
    AND seed.email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

DELETE FROM user_permission_overrides
WHERE user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username IN ('user', 'officer', 'ib')
    AND seed.email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
OR granted_by_user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username IN ('user', 'officer', 'ib')
    AND seed.email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

DELETE FROM users
WHERE id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username IN ('user', 'officer', 'ib')
    AND seed.email IN (
      'user@dydx-trading-bot.local',
      'officer@dydx-trading-bot.local',
      'ib@dydx-trading-bot.local'
    )
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

-- Remove the historical default admin only if it is still the untouched
-- bootstrap row with the known admin123 hash and owns no runtime resources.
UPDATE backtest_runs
SET user_id = NULL
WHERE user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

UPDATE audit_logs
SET user_id = NULL
WHERE user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

UPDATE bot_settings
SET updated_by = NULL
WHERE updated_by IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

DELETE FROM user_mfa_credentials
WHERE user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

DELETE FROM user_permission_overrides
WHERE user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
)
OR granted_by_user_id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);

DELETE FROM users
WHERE id IN (
  SELECT seed.id
  FROM users seed
  WHERE seed.username = 'admin'
    AND seed.email = 'admin@dydx-trading-bot.local'
    AND seed.hashed_password = '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra'
    AND NOT EXISTS (SELECT 1 FROM bot_instances WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_strategies WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM backtest_comparisons WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_keys WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM dydx_key_settings WHERE user_id = seed.id)
    AND NOT EXISTS (SELECT 1 FROM external_api_credentials WHERE user_id = seed.id)
);
