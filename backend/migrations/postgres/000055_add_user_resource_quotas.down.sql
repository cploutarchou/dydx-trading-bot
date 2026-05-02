ALTER TABLE users
  DROP CONSTRAINT IF EXISTS users_max_active_backtests_positive_chk,
  DROP CONSTRAINT IF EXISTS users_max_strategies_positive_chk,
  DROP CONSTRAINT IF EXISTS users_max_bot_instances_positive_chk;

ALTER TABLE users
  DROP COLUMN IF EXISTS max_active_backtests,
  DROP COLUMN IF EXISTS max_strategies,
  DROP COLUMN IF EXISTS max_bot_instances;
