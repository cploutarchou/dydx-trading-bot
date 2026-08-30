-- Salt columns for stored secret hashes (audit: unsalted SHA-256 hashes are
-- brute-forceable from a database dump and correlate identical secrets
-- across rows). New/rewritten rows store sha256(salt:secret); legacy rows
-- keep the unsalted form until their secret is rewritten.
ALTER TABLE dydx_keys ADD COLUMN IF NOT EXISTS secret_salt TEXT NOT NULL DEFAULT '';
ALTER TABLE external_api_credentials ADD COLUMN IF NOT EXISTS api_key_salt TEXT NOT NULL DEFAULT '';
