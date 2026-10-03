-- Shared (platform-wide) credentials are stored with user_id = 0: the email
-- API key, the global Telegram bot, shared AI-filter keys, the Codex key.
-- Migration 000052 added a plain foreign key from user_id to users(id), and no
-- user has id 0, so every shared credential insert has failed on PostgreSQL
-- since then with fk_external_api_credentials_user_id.
--
-- Keep the integrity guarantee for user-owned rows and exempt only the shared
-- owner: owner_user_id is NULL for user_id = 0 (a NULL foreign key is not
-- checked) and equals user_id otherwise.

ALTER TABLE external_api_credentials
    DROP CONSTRAINT IF EXISTS fk_external_api_credentials_user_id;

ALTER TABLE external_api_credentials
    ADD COLUMN IF NOT EXISTS owner_user_id INTEGER
    GENERATED ALWAYS AS (NULLIF(user_id, 0)) STORED;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_external_api_credentials_owner_user_id'
    ) THEN
        ALTER TABLE external_api_credentials
            ADD CONSTRAINT fk_external_api_credentials_owner_user_id
            FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_external_api_credentials_user_id_non_negative'
    ) THEN
        ALTER TABLE external_api_credentials
            ADD CONSTRAINT ck_external_api_credentials_user_id_non_negative
            CHECK (user_id >= 0);
    END IF;
END $$;
