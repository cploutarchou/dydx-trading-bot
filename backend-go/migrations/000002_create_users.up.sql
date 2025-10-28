-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(500) NOT NULL,
    full_name VARCHAR(100) DEFAULT NULL,
    avatar TEXT DEFAULT NULL,
    is_active BOOLEAN DEFAULT NULL,
    is_admin BOOLEAN DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    last_login DATETIME DEFAULT NULL
);

CREATE INDEX idx_user_active ON users(is_active);
CREATE UNIQUE INDEX ix_users_email ON users(email);
CREATE INDEX ix_users_id ON users(id);
CREATE INDEX ix_users_is_active ON users(is_active);
CREATE UNIQUE INDEX ix_users_username ON users(username);

