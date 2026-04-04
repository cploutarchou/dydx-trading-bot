# Backend Integration Tasks

## Status Summary
- Completed: `19`
- Pending: `0`
- Last updated: `2026-04-04`
- Note: update these totals whenever any [x] or [ ] task changes.

## Cross-Repo Sync Matrix (Weekly Snapshot)
| Area | Bot Status | Backend Status | Frontend Status | Owner | ETA |
| --- | --- | --- | --- | --- | --- |
| Contract aliases (`progress`, `backtests`, `count`) | complete | pending verification | pending verification | backend + frontend | 2026-04-08 |
| Run-scoped `run_id` payload consistency | complete | pending verification | pending verification | backend + frontend | 2026-04-08 |
| `GET /api/v1/backtests/sync-health` | complete | pending delegation/parsing | pending consumption | backend + frontend | 2026-04-09 |
| Auth token shape lock (`access_token`, `refresh_token`, `token_type`, `expires_in`) | complete (tests added) | pending sync test | pending sync test | backend + frontend | 2026-04-09 |
| Trace propagation (`trace_id`, `X-Trace-Id`) | complete | pending passthrough/logging | pending display/debug tooling | backend + frontend | 2026-04-10 |
| Telegram severity/category throttling | complete | n/a | n/a | bot | done |

Use this matrix as the source of truth for cross-repo handoff status; update statuses, owner, and ETA in all three task files in the same change.

Legend: `complete` = shipped/validated in that repo, `pending` = work not started, `pending verification` = implemented but contract validation still required, `n/a` = not applicable.
Last reviewed by: `bot-team` on `2026-04-04`.

## Ongoing Update Protocol
- [x] Keep this file updated whenever backend or frontend contract-affecting changes are introduced.
- [x] Update all three task files for integration-impacting changes:
  - `../backend/tasks.md`
  - `./tasks.md`
  - `../frontend/tasks.md`
- [x] Use required fields per change (date, endpoint, payload delta, auth impact, implementation owner).

## Contract / API Compatibility
- [x] Verify delegated endpoint payload keys match frontend expectations:
  - `POST /api/v1/backtests/run`
  - `GET /api/v1/backtests`
  - `GET /api/v1/backtests/:run_id/status`
  - `GET /api/v1/backtests/sync-health`
- [x] Keep response key names stable for: `run_id`, `status`, `progress`, `backtests`, `total`, `runs`, `count`.
- [x] Avoid changing auth token response shape (`access_token`, `refresh_token`, `token_type`, `expires_in`).

## Backtest Payload Coverage
- [x] Ensure bot responses include deterministic IDs for child artifacts whenever possible:
  - `trade_id` for trades
  - `position_id` for positions
  - `timestamp + market + resolution` for candles
- [x] Include `run_id` in all run-scoped endpoints to improve DB sync reliability.
- [x] Keep timestamps RFC3339 UTC.

## Analytics Sub-Objects (Recommended)
- [x] Include child arrays in analytics/details where available:
  - `trades`
  - `position_snapshots` (or `positions`)
  - `candles`
- [x] Keep naming consistent (no mixed `entry_zscore`/`entry_z_score` unless both are intentional aliases).

## Operational / Debug
- [x] Add bot-side trace IDs to delegated responses/logs for cross-service debugging.
- [x] Expose lightweight bot health with queue depth/job count for run orchestration visibility.
- [x] Add Telegram delivery resilience (retry/backoff) and duplicate suppression windows for noisy runtime errors.
- [x] Wire explicit Telegram error categories at runtime call sites for configurable throttling (`execution_*`, `lifecycle_*`, `market_data`, `analysis_*`).

## Change Log
- [x] 2026-04-04: Backend standardized delegated backtest details/empty-state payloads and enabled broader CI contract-lock enforcement for frontend-facing backtest routes.
- [x] 2026-04-04: Adopted cross-repo task governance format with backend/frontend linkage.
- [x] 2026-04-04: Added contract aliases (`progress`, `backtests`, `count`), run-scoped `run_id` coverage, `sync-health`, trace-id logging, and runtime queue/job counters.
- [x] 2026-04-04: Synced with backend governance enforcement and new backend sync capabilities (`resync`, `run_age_seconds`, `sync_lag_seconds`, `quality_issues`).
- [x] 2026-04-04: Improved Telegram interaction safety/ops signal with HTML-safe escaping, truncation, severity/category-based dedupe policy, and category-tagged runtime alerts.

## Change Log Template
- Date:
- Endpoint(s):
- Payload changes:
- Sync impact (runs/trades/positions/candles):
- Frontend tasks updated: yes/no
- Backend tasks updated: yes/no
