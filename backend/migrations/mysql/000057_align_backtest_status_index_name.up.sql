-- Migration 000057: align backtest status index name with contract expectations
--
-- Goal: ensure the canonical index name exists without creating duplicate
-- indexes when older migrations already created the same key under a
-- different name.

DO $$
BEGIN
    IF to_regclass('public.idx_backtest_runs_user_status_created') IS NULL THEN
        IF to_regclass('public.idx_backtest_runs_user_status_time') IS NOT NULL THEN
            ALTER INDEX idx_backtest_runs_user_status_time
                RENAME TO idx_backtest_runs_user_status_created;
        ELSE
            CREATE INDEX IF NOT EXISTS idx_backtest_runs_user_status_created
                ON backtest_runs (user_id, status, created_at DESC);
        END IF;
    END IF;
END $$;
