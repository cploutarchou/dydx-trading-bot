UPDATE users
SET
  email = 'admin@dydx-trading-bot.local',
  role = 'admin',
  full_name = 'Administrator',
  is_active = 1,
  is_admin = 1,
  password_change_required = 1,
  updated_at = CURRENT_TIMESTAMP
WHERE username = 'admin' OR email = 'admin@dydx-trading-bot.local';
