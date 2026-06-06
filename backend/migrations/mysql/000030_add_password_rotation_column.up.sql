ALTER TABLE users ADD COLUMN IF NOT EXISTS password_change_required TINYINT(1) NOT NULL DEFAULT 0;

UPDATE users
SET password_change_required = 1
WHERE username = 'admin' OR email = 'admin@dydx-trading-bot.local';
