-- Migration 000022 Down: Revert DYDX Key Settings enhancements

DROP INDEX IF EXISTS idx_dydx_key_settings_default_network;
DROP INDEX IF EXISTS idx_dydx_key_settings_user_id;

ALTER TABLE dydx_key_settings DROP COLUMN IF EXISTS auto_switch_testnet;
ALTER TABLE dydx_key_settings DROP COLUMN IF EXISTS default_network;

