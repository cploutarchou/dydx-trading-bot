-- Create bot_settings table (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000005_create_bot_settings.up.sql
-- Changes: SERIAL → AUTO_INCREMENT, ON CONFLICT DO NOTHING → ON DUPLICATE KEY UPDATE with INSERT IGNORE

CREATE TABLE IF NOT EXISTS bot_settings (
	id INT AUTO_INCREMENT PRIMARY KEY,
	section VARCHAR(50) NOT NULL,
	key VARCHAR(100) NOT NULL,
	value LONGTEXT NOT NULL,
	value_type VARCHAR(20) NOT NULL,
	description LONGTEXT DEFAULT NULL,
	default_value LONGTEXT DEFAULT NULL,
	is_active BOOLEAN DEFAULT NULL,
	version INTEGER DEFAULT NULL,
	created_at TIMESTAMP NULL DEFAULT NULL,
	updated_at TIMESTAMP NULL DEFAULT NULL,
	updated_by INTEGER DEFAULT NULL,
	FOREIGN KEY (updated_by) REFERENCES users (id),
	UNIQUE (section, key)
);

CREATE INDEX idx_bot_setting_active ON bot_settings (is_active);

CREATE INDEX idx_bot_setting_section_key ON bot_settings (section, key);

CREATE INDEX ix_bot_settings_id ON bot_settings (id);

CREATE INDEX ix_bot_settings_is_active ON bot_settings (is_active);

CREATE INDEX ix_bot_settings_key ON bot_settings (key);

CREATE INDEX ix_bot_settings_section ON bot_settings (section);

-- Insert default settings
-- MariaDB: Use INSERT IGNORE instead of ON CONFLICT DO NOTHING
INSERT IGNORE INTO bot_settings (
	section,
	key,
	value,
	value_type,
	description,
	default_value,
	is_active,
	version,
	created_at,
	updated_at
)
VALUES
	(
		'trading',
		'max_position_size',
		'1000',
		'integer',
		'Maximum position size per trade',
		'1000',
		true,
		1,
		CURRENT_TIMESTAMP,
		CURRENT_TIMESTAMP
	),
	(
		'trading',
		'stop_loss_percentage',
		'2.0',
		'float',
		'Stop loss percentage',
		'2.0',
		true,
		1,
		CURRENT_TIMESTAMP,
		CURRENT_TIMESTAMP
	),
	(
		'trading',
		'take_profit_percentage',
		'5.0',
		'float',
		'Take profit percentage',
		'5.0',
		true,
		1,
		CURRENT_TIMESTAMP,
		CURRENT_TIMESTAMP
	),
	(
		'trading',
		'max_daily_loss',
		'5000',
		'float',
		'Maximum daily loss limit',
		'5000',
		true,
		1,
		CURRENT_TIMESTAMP,
		CURRENT_TIMESTAMP
	);
