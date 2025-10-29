-- Migration 000022: Enhance DYDX Key Settings with all fields
-- Synchronize with Python SQLModel DYDXKeySettings schema

ALTER TABLE dydx_key_settings ADD COLUMN IF NOT EXISTS default_network VARCHAR(50) NULL;
ALTER TABLE dydx_key_settings ADD COLUMN IF NOT EXISTS auto_switch_testnet BOOLEAN DEFAULT TRUE NOT NULL;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_dydx_key_settings_user_id ON dydx_key_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_dydx_key_settings_default_network ON dydx_key_settings(default_network);

