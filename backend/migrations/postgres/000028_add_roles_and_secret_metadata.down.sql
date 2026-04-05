ALTER TABLE external_api_credentials DROP COLUMN IF EXISTS api_key_masked;
ALTER TABLE external_api_credentials DROP COLUMN IF EXISTS api_key_hash;

ALTER TABLE dydx_keys DROP COLUMN IF EXISTS secret_masked;
ALTER TABLE dydx_keys DROP COLUMN IF EXISTS secret_hash;

ALTER TABLE users DROP COLUMN IF EXISTS role;
