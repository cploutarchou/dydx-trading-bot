-- Migration 000021: Enhance User model with missing fields
-- Synchronize with Python SQLModel User schema

-- Add missing fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR(500) NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP NULL;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

