-- Migration 000021: Create default admin user
-- Creates an admin user with username: admin, password: admin123

-- Insert admin user (password is bcrypt hash of "admin123")
-- Hash generated using: bcrypt.GenerateFromPassword([]byte("admin123"), bcrypt.DefaultCost)
INSERT INTO users (username, email, role, full_name, avatar, is_active, is_admin, hashed_password, created_at, updated_at)
VALUES ('admin',
        'admin@dydx-trading-bot.local',
        'admin',
        'Administrator',
        '',
        true,
        true,
        '$2a$10$wTHTBe5KhqRqKKXvCc1K9eGhgzzVH4kaPhDB9935o6S62GwMoO/ra',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP)
ON CONFLICT
  (username)
  DO UPDATE SET hashed_password = EXCLUDED.hashed_password;

-- Create index on username for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_username_lookup ON users(username);

