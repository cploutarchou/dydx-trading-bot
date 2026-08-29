-- Migration 000021: Create default admin user
-- Creates an admin user with username: admin, password: admin123

-- Older deployments created users before role/avatar/password rotation metadata
-- existed. Keep this seed migration safe when it runs against those schemas.
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'client';
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_change_required BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE users
SET role = CASE WHEN is_admin THEN 'admin' ELSE 'client' END
WHERE role IS NULL OR BTRIM(role) = '';

-- Insert admin user (password is bcrypt hash of "admin123")
-- Hash generated using: bcrypt.GenerateFromPassword([]byte("admin123"), bcrypt.DefaultCost)
-- SECURITY: DO NOT "heal" this conflict clause into an UPDATE of
-- hashed_password. Re-running migrations must never reset an operator's
-- rotated admin password back to the repo-known default. Fresh installs
-- get the seeded admin (password_change_required=true forces rotation);
-- existing rows are left untouched. Production bootstrap is handled by
-- EnsureBootstrapAdmin (BOOTSTRAP_ADMIN_PASSWORD), not this seed.
INSERT INTO users (username, email, role, full_name, avatar, is_active, is_admin, password_change_required, hashed_password, created_at, updated_at)
VALUES ('admin',
        'admin@dydx-trading-bot.local',
        'admin',
        'Administrator',
        '',
        true,
        true,
        true,
        '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP)
ON CONFLICT
  (username)
  DO NOTHING;

-- Create index on username for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_username_lookup ON users(username);

