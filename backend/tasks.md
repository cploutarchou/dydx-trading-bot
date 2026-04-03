# Backend Tasks

## Status Summary
- Completed: `23`
- Pending: `0`
- Last updated: `2026-04-04`
- Note: update these totals whenever any [x] or [ ] task changes.

## Ongoing Update Protocol
- [x] Mirror backend API/auth contract changes into `../bot/tasks.md` and `../frontend/tasks.md`.
- [x] Maintain a structured change entry format (date, endpoint, request/response delta, auth impact, migration/sync impact).
- [x] Enforce this update protocol in PR checklist/review policy.

## Contract-Lock Coverage
- [x] Add/maintain contract tests for `POST /api/v1/backtests/run`.
- [x] Add/maintain contract tests for `GET /api/v1/backtests`.
- [x] Add/maintain contract tests for `GET /api/v1/backtests/:run_id/status`.
- [x] Add/maintain contract tests for `GET /api/v1/backtests/sync-health`.
- [x] Add CI gate to fail merges when contract-lock tests are not updated for contract changes.

## Delegated Backtest DB Sync
- [x] Sync `backtest_runs` from delegated endpoints in near real-time.
- [x] Sync child artifacts into `backtest_trades`, `backtest_positions`, `backtest_candles`.
- [x] Preserve dedupe semantics:
  - trades by `trade_id`
  - positions by `position_id`
  - candles by `(run_id, market, timestamp, resolution)`
- [x] Add protected sync-health endpoint with per-run counts (`runs/trades/positions/candles`).

## Open Improvements
- [x] Add metrics endpoint for sync lag/age per run.
- [x] Add optional force-resync endpoint for a run (`run_id`) from bot upstream.
- [x] Add data quality checks for incomplete child artifacts (missing IDs, invalid timestamps).

## Change Log
- [x] 2026-04-04: Added strict contract-lock tests for delegated high-traffic backtest endpoints.
- [x] 2026-04-04: Implemented delegated run/status DB sync for `backtest_runs`.
- [x] 2026-04-04: Extended sync to child artifacts (`trades`, `positions`, `candles`) with upsert/dedupe.
- [x] 2026-04-04: Added `GET /api/v1/backtests/sync-health` dashboard-style sync count endpoint.
- [x] 2026-04-04: Added cross-repo task governance in backend/bot/frontend task files.
- [x] 2026-04-04: Added governance validator + make targets (`tasks-validate`, `tasks-governance`) and PR checklist template.
- [x] 2026-04-04: Added force-resync endpoint and sync health metrics (`run_age_seconds`, `sync_lag_seconds`, `quality_issues`).
- [x] 2026-04-04: Added strict contract-lock response-shape test for `POST /api/v1/backtests/:run_id/resync`.

## Change Log Template
- Date:
- Endpoint(s):
- Request change:
- Response change:
- Auth/middleware impact:
- DB schema/sync impact:
- Bot tasks updated: yes/no
- Frontend tasks updated: yes/no
