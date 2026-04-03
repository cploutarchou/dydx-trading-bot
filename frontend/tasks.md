# Frontend Integration Tasks

## Status Summary
- Completed: `6`
- Pending: `12`
- Last updated: `2026-04-04`
- Note: update these totals whenever any [x] or [ ] task changes.

## Ongoing Update Protocol
- [x] Keep this file updated whenever backend/bot contract changes affect frontend behavior.
- [x] For each integration change, update all three task files:
  - `../backend/tasks.md`
  - `../bot/tasks.md`
  - `./tasks.md`
- [x] Use required fields per change (date, endpoint, UI impact, fallback behavior, owner).

## API Contract Guardrails
- [ ] Add client contract tests/snapshots for high-traffic endpoints:
  - `POST /api/v1/backtests/run`
  - `GET /api/v1/backtests`
  - `GET /api/v1/backtests/:run_id/status`
  - `GET /api/v1/backtests/sync-health`
- [ ] Treat missing required keys as hard failures and log payload for diagnostics.

## Sync Health Dashboard
- [ ] Add a small run sync status panel using:
  - `GET /api/v1/backtests/sync-health`
  - optional `run_id` filter query
- [ ] Display counts per run:
  - `trades`
  - `positions`
  - `candles`
- [ ] Add warning badges when expected counts are zero while run is active/completed.

## UX / Error Handling
- [ ] Preserve backend passthrough errors for delegated endpoints (show upstream message where safe).
- [ ] Distinguish transport failures (`502/504`) from validation/business failures (`4xx`).
- [ ] Retry polling endpoints with capped backoff.

## Data Consistency
- [ ] Prefer server-run IDs as source of truth.
- [ ] Avoid deriving IDs client-side for persisted entities.
- [ ] Keep all date formatting UTC and RFC3339-compatible.

## Change Log
- [x] 2026-04-04: Added cross-repo task governance process and endpoint backlog alignment.
- [x] 2026-04-04: Backend added `POST /api/v1/backtests/:run_id/resync` and sync-health metrics fields (`run_age_seconds`, `sync_lag_seconds`, `quality_issues`) for dashboard consumption.
- [x] 2026-04-04: Backend added contract-lock test coverage for `POST /api/v1/backtests/:run_id/resync` response shape.
- [ ] Add first frontend implementation entry after sync-health panel and contract checks are implemented.

## Change Log Template
- Date:
- Endpoint(s):
- UI/state impact:
- Error handling impact:
- Backend tasks updated: yes/no
- Bot tasks updated: yes/no
