-- SQLite cannot drop columns without table rebuild; keep down migration as no-op.
-- Quota columns are backward-compatible defaults.
SELECT 1;
