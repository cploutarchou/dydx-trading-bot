-- Create users table (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000002_create_users.up.sql
-- Changes: SERIAL → AUTO_INCREMENT

CREATE TABLE IF NOT EXISTS users
(
  id              INT AUTO_INCREMENT PRIMARY KEY,
  username        VARCHAR(50)  NOT NULL UNIQUE,
  email           VARCHAR(100) NOT NULL UNIQUE,
  role            VARCHAR(50)  NOT NULL DEFAULT 'client',
  hashed_password VARCHAR(500) NOT NULL,
  full_name       VARCHAR(100) DEFAULT NULL,
  avatar          LONGTEXT     DEFAULT '',
  is_active       TINYINT(1)      DEFAULT NULL,
  is_admin        TINYINT(1)      DEFAULT NULL,
  password_change_required TINYINT(1) NOT NULL DEFAULT 0,
  created_at      TIMESTAMP    NULL DEFAULT NULL,
  updated_at      TIMESTAMP    NULL DEFAULT NULL,
  last_login      TIMESTAMP    NULL DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_active ON users (is_active);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);
CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
