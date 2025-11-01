-- Create bot_settings table
CREATE TABLE IF NOT EXISTS bot_settings
(
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  section       VARCHAR(50) NOT NULL,
  key VARCHAR (100) NOT NULL,
  value         TEXT        NOT NULL,
  value_type    VARCHAR(20) NOT NULL,
  description   TEXT     DEFAULT NULL,
  default_value TEXT     DEFAULT NULL,
  is_active     BOOLEAN  DEFAULT NULL,
  version       INTEGER  DEFAULT NULL,
  created_at    DATETIME DEFAULT NULL,
  updated_at    DATETIME DEFAULT NULL,
  updated_by    INTEGER  DEFAULT NULL,
  FOREIGN KEY (updated_by) REFERENCES users (id),
  UNIQUE(section, key)
);

CREATE INDEX idx_bot_setting_active ON bot_settings (is_active);
CREATE INDEX idx_bot_setting_section_key ON bot_settings (section, key);
CREATE INDEX ix_bot_settings_id ON bot_settings (id);
CREATE INDEX ix_bot_settings_is_active ON bot_settings (is_active);
CREATE INDEX ix_bot_settings_key ON bot_settings (key);
CREATE INDEX ix_bot_settings_section ON bot_settings (section);

-- Insert default settings
INSERT INTO bot_settings (section, key, value, value_type, description, default_value, is_active, version, created_at, updated_at)
VALUES
  ('trading', 'max_position_size', '1000', 'integer', 'Maximum position size per trade', '1000', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('trading', 'stop_loss_percentage', '5', 'float', 'Stop loss percentage for trades', '5', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('trading', 'take_profit_percentage', '10', 'float', 'Take profit percentage for trades', '10', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('api', 'request_timeout', '30', 'integer', 'API request timeout in seconds', '30', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('api', 'retry_attempts', '3', 'integer', 'Number of retry attempts for failed requests', '3', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('bot', 'enabled', 'false', 'boolean', 'Enable or disable the trading bot', 'false', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('bot', 'log_level', 'info', 'string', 'Logging level (debug, info, warn, error)', 'info', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT(section, key) DO NOTHING;

