-- Create bot_settings table
CREATE TABLE IF NOT EXISTS bot_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section VARCHAR(50) NOT NULL,
    key VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    value_type VARCHAR(20) NOT NULL,
    description TEXT DEFAULT NULL,
    default_value TEXT DEFAULT NULL,
    is_active BOOLEAN DEFAULT NULL,
    version INTEGER DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    updated_by INTEGER DEFAULT NULL,
    FOREIGN KEY(updated_by) REFERENCES users(id)
);

CREATE INDEX idx_bot_setting_active ON bot_settings(is_active);
CREATE INDEX idx_bot_setting_section_key ON bot_settings(section, key);
CREATE INDEX ix_bot_settings_id ON bot_settings(id);
CREATE INDEX ix_bot_settings_is_active ON bot_settings(is_active);
CREATE INDEX ix_bot_settings_key ON bot_settings(key);
CREATE INDEX ix_bot_settings_section ON bot_settings(section);
-- Drop backtest_strategies table
DROP TABLE IF EXISTS backtest_strategies;

