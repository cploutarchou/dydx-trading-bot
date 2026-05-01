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
