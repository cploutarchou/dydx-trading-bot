-- Migration 000021: Create default admin user
-- Creates an admin user with username: admin, password: admin123

-- Older deployments created users before role/avatar/password rotation metadata
-- existed. Keep this seed migration safe when it runs against those schemas.
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'client';
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_change_required TINYINT(1) NOT NULL DEFAULT 0;

UPDATE users
SET role = CASE WHEN is_admin THEN 'admin' ELSE 'client' END
WHERE role IS NULL OR TRIM(role) = '';

-- Insert admin user (password is bcrypt hash of "admin123")
-- Hash generated using: bcrypt.GenerateFromPassword([]byte("admin123"), bcrypt.DefaultCost)
INSERT INTO users (username, email, role, full_name, avatar, is_active, is_admin, password_change_required, hashed_password, created_at, updated_at)
VALUES ('admin',
        'admin@dydx-trading-bot.local',
        'admin',
        'Administrator',
        '',
        1,
        1,
        1,
        '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP)
ON DUPLICATE KEY UPDATE hashed_password = VALUES(hashed_password),
                password_change_required = VALUES(password_change_required);

-- Create index on username for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_username_lookup ON users(username);

