ALTER TABLE dydx_keys DROP COLUMN IF EXISTS secret_salt;
ALTER TABLE external_api_credentials DROP COLUMN IF EXISTS api_key_salt;
