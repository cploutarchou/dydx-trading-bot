-- Create dydx_key_settings table (MySQL/MariaDB version)

CREATE TABLE IF NOT EXISTS dydx_key_settings
(
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  user_id             INTEGER     NOT NULL UNIQUE,
  default_network     VARCHAR(50) NOT NULL,
  auto_switch_testnet TINYINT(1)     NOT NULL,
  created_at          TIMESTAMP    NOT NULL,
  updated_at          TIMESTAMP    NOT NULL,
  KEY idx_fk_user_id (user_id)
);

CREATE INDEX ix_dydx_key_settings_id ON dydx_key_settings (id);
CREATE UNIQUE INDEX ix_dydx_key_settings_user_id ON dydx_key_settings (user_id);
