ALTER TABLE users ADD COLUMN IF NOT EXISTS password_change_required BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE users
SET password_change_required = true
WHERE username = 'admin' OR email = 'admin@dydx-trading-bot.local';
