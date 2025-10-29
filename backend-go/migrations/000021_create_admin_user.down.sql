-- Migration 000021: Rollback - Remove default admin user
-- Removes the admin user created in the up migration

DELETE FROM users WHERE username = 'admin' AND email = 'admin@dydx-trading-bot.local';

-- Drop the index if it exists
DROP INDEX IF EXISTS idx_users_username_lookup;

