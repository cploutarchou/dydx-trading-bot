-- Normalize historical status values to lowercase so status-filtered queries
-- (admission checks, strategy run listings) use the raw column and can use the
-- (user_id, status, created_at) indexes instead of a LOWER() expression scan.
UPDATE backtest_runs SET status = LOWER(status) WHERE status IS NOT NULL AND status <> LOWER(status);
