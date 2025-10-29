-- Migration 000021: Create default admin user
-- Creates an admin user with username: admin, password: admin123

-- Insert admin user (password is bcrypt hash of "admin123")
-- Hash generated using: bcrypt("admin123") = $2a$10$N9qo8uLOickgx2ZMRZoMye
INSERT INTO users (username, email, full_name, avatar, is_active, is_admin, hashed_password, created_at, updated_at)
VALUES (
    'admin',
    'admin@dydx-trading-bot.local',
    'Administrator',
    NULL,
    true,
    true,
    '$2a$10$N9qo8uLOickgx2ZMRZoMyeiKbItbrxtfXoYT8KKIUgO2J0H/B1Umi',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT(username) DO NOTHING;

-- Create index on username for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_username_lookup ON users(username);

