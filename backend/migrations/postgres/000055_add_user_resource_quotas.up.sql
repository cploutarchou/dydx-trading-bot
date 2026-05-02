ALTER TABLE users
  ADD COLUMN IF NOT EXISTS max_active_backtests INTEGER NOT NULL DEFAULT 10,
  ADD COLUMN IF NOT EXISTS max_strategies INTEGER NOT NULL DEFAULT 10,
  ADD COLUMN IF NOT EXISTS max_bot_instances INTEGER NOT NULL DEFAULT 10;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'users_max_active_backtests_positive_chk'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT users_max_active_backtests_positive_chk
      CHECK (max_active_backtests >= 1);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'users_max_strategies_positive_chk'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT users_max_strategies_positive_chk
      CHECK (max_strategies >= 1);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'users_max_bot_instances_positive_chk'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT users_max_bot_instances_positive_chk
      CHECK (max_bot_instances >= 1);
  END IF;
END;
$$;
