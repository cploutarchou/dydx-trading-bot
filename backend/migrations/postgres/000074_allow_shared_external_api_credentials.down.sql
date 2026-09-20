-- Restores the 000052 shape. Shared rows (user_id = 0) cannot satisfy the plain
-- foreign key, so they are removed first; re-enter those keys after a rollback.

DELETE FROM external_api_credentials WHERE user_id = 0;

ALTER TABLE external_api_credentials
    DROP CONSTRAINT IF EXISTS ck_external_api_credentials_user_id_non_negative;

ALTER TABLE external_api_credentials
    DROP CONSTRAINT IF EXISTS fk_external_api_credentials_owner_user_id;

ALTER TABLE external_api_credentials
    DROP COLUMN IF EXISTS owner_user_id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_external_api_credentials_user_id'
    ) THEN
        ALTER TABLE external_api_credentials
            ADD CONSTRAINT fk_external_api_credentials_user_id
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT;
    END IF;
END $$;
