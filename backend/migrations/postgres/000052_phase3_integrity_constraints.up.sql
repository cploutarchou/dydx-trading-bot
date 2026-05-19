-- Migration 000052: Phase 3 — Data integrity constraints
-- Source: DBA audit report 2026-05-01
--
-- ⚠️  REQUIRES DBA APPROVAL before applying to production.
-- ⚠️  Run orphan-check queries (Section 4.5 of audit report) BEFORE applying.
--     Any orphan rows will cause FK constraint additions to fail.
--
-- Changes applied in safe dependency order:
--   1. FK: bot_instances.user_id → users(id)
--   2. FK: external_api_credentials.user_id → users(id)
--   3. FK: bot_alerts.bot_instance_id → bot_instances(id)  (Go-managed alerts table)
--   4. NOT NULL + DEFAULT on users.is_active / users.is_admin
--   5. CHECK constraint on bot_instances.status (Go-managed text column)
--   6. NOT NULL defaults on jobs retry columns (applied via bot Alembic migration — see
--      bot/migrations/versions/b3c4d5e6f7a8_phase3_integrity_constraints.py)
--
-- Rollback: 000052_phase3_integrity_constraints.down.sql

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1: Orphan checks (informational — application must verify zero rows before
-- proceeding). These are left as comments; run them manually on the live DB.
-- ─────────────────────────────────────────────────────────────────────────────
--
--  -- bot_instances with no matching user:
--  SELECT bi.id, bi.user_id FROM bot_instances bi
--  LEFT JOIN users u ON u.id = bi.user_id WHERE u.id IS NULL;
--
--  -- external_api_credentials with no matching user:
--  SELECT eac.id, eac.user_id FROM external_api_credentials eac
--  LEFT JOIN users u ON u.id = eac.user_id WHERE u.id IS NULL;
--
--  -- bot_alerts with no matching bot_instance:
--  SELECT ba.id, ba.bot_instance_id FROM bot_alerts ba
--  LEFT JOIN bot_instances bi ON bi.id = ba.bot_instance_id WHERE bi.id IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 2: FK — bot_instances.user_id → users(id)
-- Risk: MEDIUM — fails if any bot_instance.user_id has no matching users.id row.
-- Constraint: RESTRICT on delete (never silently orphan bot financial history).
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_bot_instances_user_id'
    ) THEN
        ALTER TABLE bot_instances
            ADD CONSTRAINT fk_bot_instances_user_id
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT
            NOT VALID;
    END IF;
END $$;

-- Validate separately (allows concurrent DML during validation):
ALTER TABLE bot_instances
    VALIDATE CONSTRAINT fk_bot_instances_user_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 3: FK — external_api_credentials.user_id → users(id)
-- The existing NOT NULL on user_id makes this safe once orphans are cleaned.
-- Credentials without an owner are a security risk — restrict deletion.
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_external_api_credentials_user_id'
    ) THEN
        ALTER TABLE external_api_credentials
            ADD CONSTRAINT fk_external_api_credentials_user_id
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT
            NOT VALID;
    END IF;
END $$;

ALTER TABLE external_api_credentials
    VALIDATE CONSTRAINT fk_external_api_credentials_user_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 4: NOT NULL + DEFAULT on users.is_active / users.is_admin
-- Safe: backfill NULLs first, then set NOT NULL.
-- ─────────────────────────────────────────────────────────────────────────────
UPDATE users SET is_active = TRUE  WHERE is_active IS NULL;
UPDATE users SET is_admin  = FALSE WHERE is_admin  IS NULL;

ALTER TABLE users
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ALTER COLUMN is_active SET NOT NULL,
    ALTER COLUMN is_admin  SET DEFAULT FALSE,
    ALTER COLUMN is_admin  SET NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 5: CHECK constraint on bot_instances.status (text column, Go-managed schema)
-- Validates status values match the botstatusenum set used by the Python bot.
-- NOT VALID + VALIDATE pattern avoids lock escalation on large tables.
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_bot_instances_status'
    ) THEN
        ALTER TABLE bot_instances
            ADD CONSTRAINT chk_bot_instances_status
            CHECK (status::text IN ('CREATED','STARTING','RUNNING','PAUSED','STOPPING','STOPPED',
                                    'FAILED','ERROR','RECOVERING','DEGRADED','SAFEGUARDED'))
            NOT VALID;
    END IF;
END $$;

ALTER TABLE bot_instances
    VALIDATE CONSTRAINT chk_bot_instances_status;

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 6: UNIQUE constraint on market_data_realtime (bot_instance_id, symbol)
-- Only apply after deduplicating any existing duplicate rows.
-- Guarded by a check — uncomment once duplicate cleanup is confirmed.
-- ─────────────────────────────────────────────────────────────────────────────
-- CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_market_data_bot_symbol
--     ON market_data_realtime (bot_instance_id, symbol);
-- ALTER TABLE market_data_realtime
--     ADD CONSTRAINT uq_market_data_bot_symbol UNIQUE USING INDEX idx_market_data_bot_symbol;
