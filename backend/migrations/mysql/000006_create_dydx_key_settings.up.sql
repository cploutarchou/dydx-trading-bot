-- Create dydx_key_settings table (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000006_create_dydx_key_settings.up.sql
-- Changes: SERIAL → AUTO_INCREMENT

CREATE TABLE IF NOT EXISTS dydx_key_settings
(
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  user_id             INTEGER     NOT NULL UNIQUE,
  default_network     VARCHAR(50) NOT NULL,
  auto_switch_testnet BOOLEAN     NOT NULL,
  created_at          TIMESTAMP    NOT NULL,
  updated_at          TIMESTAMP    NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX ix_dydx_key_settings_id ON dydx_key_settings (id);
CREATE UNIQUE INDEX ix_dydx_key_settings_user_id ON dydx_key_settings (user_id);
