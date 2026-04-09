# Frontend Integration Tasks

## Status Summary
- Completed: `60`
- Pending: `3`
- Last updated: `2026-04-10`
- Note: update these totals whenever any [x] or [ ] task changes.

## Cross-Repo Status Snapshot

| Repo     | Completed | Pending | Focus                                                                    |
| -------- | --------- | ------- | ------------------------------------------------------------------------ |
| backend  | 54        | 0       | Delegated contract parity and contract-lock coverage shipped             |
| bot      | 26        | 0       | Canonical API contract and runtime envelope/documentation stability      |
| frontend | 58        | 3       | Remaining responsive evidence + medium-priority backend integration asks |

Snapshot date: `2026-04-05`.

## Responsive QA
- [x] Deliver route-by-route responsive QA matrix (375/768/1024/1440) in `docs/RESPONSIVE_QA_STATUS.md`.
- [x] Add screenshot review helper/checklist doc: `docs/RESPONSIVE_SCREENSHOT_SIGNOFF.md`.
- [x] Add Unix-friendly screenshot capture helper + route manifest (`scripts/capture-responsive-screenshots.mjs`, `scripts/responsive-screenshot-routes.json`).
- [x] Add one-page exact filename checklist for the 12 expected responsive PNGs: `docs/RESPONSIVE_SCREENSHOT_CHECKLIST.md`.
- [x] Add checklist sync helper to auto-check existing PNG evidence: `scripts/update-responsive-screenshot-checklist.mjs`.
- [ ] Capture screenshot sign-off evidence for key routes at 375/768/1024/1440 and attach file paths in `docs/RESPONSIVE_QA_STATUS.md`.

## Ongoing Update Protocol
- [x] Keep this file updated whenever backend/bot contract changes affect frontend behavior.
- [x] For each integration change, update all three task files:
  - `../backend/tasks.md`
  - `../bot/tasks.md`
  - `./tasks.md`
- [x] Use required fields per change (date, endpoint, UI impact, fallback behavior, owner).

## API Contract Guardrails
- [x] Add client contract tests/snapshots for high-traffic endpoints:
  - `POST /api/v1/backtests/run`
  - `GET /api/v1/backtests`
  - `GET /api/v1/backtests/:run_id/status`
  - `GET /api/v1/backtests/sync-health`
- [x] Treat missing required keys as hard failures and log payload for diagnostics.

## Sync Health Dashboard
- [x] Add a small run sync status panel using:
  - `GET /api/v1/backtests/sync-health`
  - optional `run_id` filter query
- [x] Display counts per run:
  - `trades`
  - `positions`
  - `candles`
- [x] Add warning badges when expected counts are zero while run is active/completed.

## UX / Error Handling
- [x] Preserve backend passthrough errors for delegated endpoints (show upstream message where safe).
- [x] Distinguish transport failures (`502/504`) from validation/business failures (`4xx`).
- [x] Propagate `X-Trace-Id` on both Axios and `fetch` API calls and retain backend trace IDs in client-side error classification for operator debugging.
- [x] Retry polling endpoints with capped backoff.
- [x] Prevent app lock on auth bootstrap by adding timeout fallback and a recover-to-login action from `Restoring session...`.

## Data Consistency
- [x] Prefer server-run IDs as source of truth.
- [x] Avoid deriving IDs client-side for persisted entities.
- [x] Keep all date formatting UTC and RFC3339-compatible.

## Backend Team Task Pack (copy to ../backend/tasks.md)

### A) Backtest Detail Reliability (high priority)
- [x] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id`
  - UI impact: `src/pages/BacktestDetailsV2.tsx` requires stable fields (`status`, `progress_percent|progress_pct|progress`, `total_pnl`, `win_rate`, `sharpe_ratio`, `max_drawdown_pct`, `total_trades`).
  - Fallback behavior: if optional fields are missing, return `null` consistently instead of omitting keys.
  - Owner: Backend
- [x] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/logs`
  - UI impact: live task feed and progress task line for active runs.
  - Fallback behavior: if logs are unsupported, return `200` with `data.logs: []` (avoid repeated `404`).
  - Owner: Backend
- [x] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/analytics`
  - UI impact: equity and summary charts require `daily_pnl[]` with timestamp/date and pnl/cumulative values.
  - Fallback behavior: return empty array with success envelope, never mixed object/array shape.
  - Owner: Backend
- [x] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/positions/snapshots`
  - UI impact: positions tab and PnL-by-pair cards.
  - Fallback behavior: stable `data.snapshots: []` when no records.
  - Owner: Backend
- [x] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/trades/detailed`
  - UI impact: trades tab table and aggregate metrics.
  - Fallback behavior: stable `data.trades: []` and `data.total`.
  - Owner: Backend

### B) Progress + Sync Health (high priority)
- [x] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/status`
  - UI impact: dashboard + details progress bar needs near-real-time `progress_pct` and `current_pair/current_task`.
  - Fallback behavior: include `progress_pct: 0` and `current_task: null` for pending runs.
  - Owner: Backend
- [x] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/sync-health`
  - UI impact: upcoming sync panel and stale-data warning badges.
  - Fallback behavior: always include run-level counters (`trades`, `positions`, `candles`) and lag fields.
  - Owner: Backend
- [x] Date: 2026-04-04 | Endpoint: `POST /api/v1/backtests/:run_id/resync`
  - UI impact: manual resync action for stale runs.
  - Fallback behavior: idempotent response with job/run state.
  - Owner: Backend

### C) Error Semantics + Contracts (high priority)
- [x] Date: 2026-04-04 | Endpoint(s): all `/api/v1/backtests/*`
  - UI impact: toasts and inline errors should distinguish transport vs business errors.
  - Fallback behavior: keep envelope `{ success, message, data, timestamp }` for all non-stream endpoints.
  - Owner: Backend
- [x] Date: 2026-04-04 | Endpoint(s): all delegated bot/strategy passthrough routes
  - UI impact: show upstream message where safe for operator debugging.
  - Fallback behavior: preserve upstream status code when possible.
  - Owner: Backend
- [x] Date: 2026-04-04 | Endpoint(s): contract-lock tests
  - UI impact: prevents silent UI regressions on payload shape changes.
  - Fallback behavior: CI should fail on missing required keys and shape drift.
  - Owner: Backend

### D) Strategy Runtime Stability (medium priority)
- [x] Date: 2026-04-05 | Endpoint: `WS /ws/strategies`
  - UI impact: Strategy Runtime status tiles (`running/stopped/error`) and counters.
  - Fallback behavior: reconnect-safe snapshot + lifecycle event handling, with HTTP polling retained as truth-source recovery.
  - Owner: Backend + Bot + Frontend
- [x] Date: 2026-04-05 | Endpoint(s): strategy control APIs (start/stop/update)
  - UI impact: replace frontend-local toggles with persisted runtime truth.
  - Fallback behavior: return current effective state after action and reconcile against runtime polling if websocket events are missed.
  - Owner: Backend + Bot + Frontend

### E) Ops / Observability (medium priority)
- [ ] Date: 2026-04-04 | Endpoint(s): all high-traffic routes
  - UI impact: better incident triage when user reports missing data.
  - Fallback behavior: include request-id/correlation-id in response headers.
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint(s): backtest worker and sync jobs
  - UI impact: UI can surface delayed-sync warnings with confidence.
  - Fallback behavior: expose run freshness and last-sync timestamps.
  - Owner: Backend

## Change Log
- [x] 2026-04-04: Bot API now sanitizes all 5xx envelope messages globally via `api_response`, preventing raw internal exception/SQL leakage into frontend error surfaces while preserving generic failure UX.
- [x] 2026-04-04: Bot API hardened backtest strategy lookup path to fall back gracefully when strategy DB is unavailable and now suppresses raw DB SQL error strings in internal-error responses consumed by frontend toasts/modals.
- [x] 2026-04-04: Backend completed bot-route parity follow-ups for frontend integration (`/bots/:id/stop?force`, `/bots/:id/trades?status`, numeric realtime delegated IDs) and added delegated bot contract-lock tests for lifecycle + high-traffic payload required keys.
- [x] 2026-04-04: Backend updated `POST /api/v1/backtests/:run_id/resync` to include deterministic run/job state fields for stable manual-resync UI handling.
- [x] 2026-04-04: Backend passthrough routes now preserve upstream status and expose upstream-safe message in both `error` and `message` response keys.
- [x] 2026-04-04: Backend standardized non-stream `/api/v1/backtests/*` success responses on a canonical envelope and locked status/sync-health fields for UI polling.
- [x] 2026-04-04: Backend stabilized `GET /api/v1/backtests/:run_id` keys/nullability and expanded CI-backed contract locks for details and empty-state backtest payloads.
- [x] 2026-04-04: Added cross-repo task governance process and endpoint backlog alignment.
- [x] 2026-04-04: Backend added `POST /api/v1/backtests/:run_id/resync` and sync-health metrics fields (`run_age_seconds`, `sync_lag_seconds`, `quality_issues`) for dashboard consumption.
- [x] 2026-04-04: Backend added contract-lock test coverage for `POST /api/v1/backtests/:run_id/resync` response shape.
- [x] 2026-04-04: Frontend added responsive container standardization and mock backtest detail fallback for `/backtest/mock-run-*` in `BacktestDetailsV2`.
- [x] 2026-04-04: Frontend added dashboard `SyncHealthPanel` with run-level counters and warning badges using `GET /api/v1/backtests/sync-health`.
- [x] 2026-04-04: Frontend added capped backoff polling in `BacktestList`, `useBacktestProgress`, and `BacktestDetailsV2` status/log polling.
- [x] 2026-04-04: Added route-by-route responsive QA checklist artifact in `docs/RESPONSIVE_QA_STATUS.md`.
- [x] 2026-04-04: Added screenshot reviewer helper `docs/RESPONSIVE_SCREENSHOT_SIGNOFF.md` and linked it from responsive QA status.
- [x] 2026-04-04: Hardened auth bootstrap (`App.tsx`, `store/auth.ts`) with timeout fallback so session restore cannot block indefinitely.
- [x] 2026-04-04: Added frontend contract guard tests in `src/api/contractGuards.test.ts` and wired `npm run test:contracts`.
- [x] 2026-04-04: Improved frontend error semantics by preserving upstream `message/detail/error` and classifying transport vs business failures in bot UX.
- [x] 2026-04-04: Enforced data consistency by avoiding client-generated persisted IDs and rendering operational timestamps in UTC/RFC3339-friendly format.
- [x] 2026-04-04: Added responsive screenshot capture automation/playbook (`scripts/capture-responsive-screenshots.mjs`, route manifest, docs playbook, output scaffold).
- [x] 2026-04-04: Audited `tasks.md` against current workspace artifacts; no additional pending items could be honestly marked complete.
- [x] 2026-04-04: Attempted real responsive screenshot capture; task remains pending because Edge authenticated profile capture failed before producing PNG evidence.
- [x] 2026-04-04: Added one-page exact screenshot filename checklist in `docs/RESPONSIVE_SCREENSHOT_CHECKLIST.md` to speed up manual evidence capture.
- [x] 2026-04-04: Added `npm run qa:screenshots:sync` to auto-refresh screenshot checklist checkboxes from files present in `docs/screenshots/responsive/`.
- [x] Added first frontend implementation entries for sync-health panel and polling backoff updates.
- [x] 2026-04-05: Strategy runtime controls are now live in `StrategyManager`; the UI consumes backend start/stop/runtime endpoints and safely handles bot websocket snapshots/lifecycle updates.

## Change Log Template
- Date:
- Endpoint(s):
- UI/state impact:
- Error handling impact:
- Backend tasks updated: yes/no
- Bot tasks updated: yes/no
