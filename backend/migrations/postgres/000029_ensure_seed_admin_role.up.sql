UPDATE users
SET
  email = 'admin@dydx-trading-bot.local',
  role = 'admin',
  full_name = 'Administrator',
  is_active = true,
  is_admin = true,
  updated_at = CURRENT_TIMESTAMP
WHERE username = 'admin' OR email = 'admin@dydx-trading-bot.local';
