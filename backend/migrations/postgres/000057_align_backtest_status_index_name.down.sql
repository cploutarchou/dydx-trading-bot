-- Rollback for 000057: restore legacy index name when present

DO $$
BEGIN
    IF to_regclass('public.idx_backtest_runs_user_status_time') IS NULL
       AND to_regclass('public.idx_backtest_runs_user_status_created') IS NOT NULL THEN
        ALTER INDEX idx_backtest_runs_user_status_created
            RENAME TO idx_backtest_runs_user_status_time;
    END IF;
END $$;
