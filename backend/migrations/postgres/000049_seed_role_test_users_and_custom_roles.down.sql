DELETE FROM users
WHERE username IN ('user', 'officer', 'ib')
  AND email IN (
    'user@dydx-trading-bot.local',
    'officer@dydx-trading-bot.local',
    'ib@dydx-trading-bot.local'
  );

DROP TABLE IF EXISTS custom_roles;
