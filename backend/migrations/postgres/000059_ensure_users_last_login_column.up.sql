-- Ensure legacy databases contain users.last_login required by auth/bootstrap flows.
ALTER TABLE users
ADD COLUMN IF NOT EXISTS last_login TIMESTAMP DEFAULT NULL;