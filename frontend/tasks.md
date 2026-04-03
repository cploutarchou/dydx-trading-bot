# Frontend Integration Tasks

## API Contract Guardrails
- Add client contract tests/snapshots for high-traffic endpoints:
  - `POST /api/v1/backtests/run`
  - `GET /api/v1/backtests`
  - `GET /api/v1/backtests/:run_id/status`
  - `GET /api/v1/backtests/sync-health`
- Treat missing required keys as hard failures and log payload for diagnostics.

## Sync Health Dashboard
- Add a small run sync status panel using:
  - `GET /api/v1/backtests/sync-health`
  - optional `run_id` filter query
- Display counts per run:
  - `trades`
  - `positions`
  - `candles`
- Add warning badges when expected counts are zero while run is active/completed.

## UX / Error Handling
- Preserve backend passthrough errors for delegated endpoints (show upstream message where safe).
- Distinguish transport failures (`502/504`) from validation/business failures (`4xx`).
- Retry polling endpoints with capped backoff.

## Data Consistency
- Prefer server-run IDs as source of truth.
- Avoid deriving IDs client-side for persisted entities.
- Keep all date formatting UTC and RFC3339-compatible.

