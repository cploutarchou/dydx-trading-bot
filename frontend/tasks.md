# Frontend Integration Tasks

## Status Summary
- Completed: `7`
- Pending: `27`
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

## Backend Team Task Pack (copy to ../backend/tasks.md)

### A) Backtest Detail Reliability (high priority)
- [ ] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id`
  - UI impact: `src/pages/BacktestDetailsV2.tsx` requires stable fields (`status`, `progress_percent|progress_pct|progress`, `total_pnl`, `win_rate`, `sharpe_ratio`, `max_drawdown_pct`, `total_trades`).
  - Fallback behavior: if optional fields are missing, return `null` consistently instead of omitting keys.
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/logs`
  - UI impact: live task feed and progress task line for active runs.
  - Fallback behavior: if logs are unsupported, return `200` with `data.logs: []` (avoid repeated `404`).
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/analytics`
  - UI impact: equity and summary charts require `daily_pnl[]` with timestamp/date and pnl/cumulative values.
  - Fallback behavior: return empty array with success envelope, never mixed object/array shape.
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/positions/snapshots`
  - UI impact: positions tab and PnL-by-pair cards.
  - Fallback behavior: stable `data.snapshots: []` when no records.
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/trades/detailed`
  - UI impact: trades tab table and aggregate metrics.
  - Fallback behavior: stable `data.trades: []` and `data.total`.
  - Owner: Backend

### B) Progress + Sync Health (high priority)
- [ ] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/:run_id/status`
  - UI impact: dashboard + details progress bar needs near-real-time `progress_pct` and `current_pair/current_task`.
  - Fallback behavior: include `progress_pct: 0` and `current_task: null` for pending runs.
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint: `GET /api/v1/backtests/sync-health`
  - UI impact: upcoming sync panel and stale-data warning badges.
  - Fallback behavior: always include run-level counters (`trades`, `positions`, `candles`) and lag fields.
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint: `POST /api/v1/backtests/:run_id/resync`
  - UI impact: manual resync action for stale runs.
  - Fallback behavior: idempotent response with job/run state.
  - Owner: Backend

### C) Error Semantics + Contracts (high priority)
- [ ] Date: 2026-04-04 | Endpoint(s): all `/api/v1/backtests/*`
  - UI impact: toasts and inline errors should distinguish transport vs business errors.
  - Fallback behavior: keep envelope `{ success, message, data, timestamp }` for all non-stream endpoints.
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint(s): all delegated bot/strategy passthrough routes
  - UI impact: show upstream message where safe for operator debugging.
  - Fallback behavior: preserve upstream status code when possible.
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint(s): contract-lock tests
  - UI impact: prevents silent UI regressions on payload shape changes.
  - Fallback behavior: CI should fail on missing required keys and shape drift.
  - Owner: Backend

### D) Strategy Runtime Stability (medium priority)
- [ ] Date: 2026-04-04 | Endpoint: `WS /ws/strategies`
  - UI impact: Strategy Runtime status tiles (`running/stopped/error`) and counters.
  - Fallback behavior: heartbeat/ping and reconnect-safe payloads.
  - Owner: Backend
- [ ] Date: 2026-04-04 | Endpoint(s): strategy control APIs (start/stop/update)
  - UI impact: replace frontend-local toggles with persisted runtime truth.
  - Fallback behavior: return current effective state after action.
  - Owner: Backend

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
- [x] 2026-04-04: Added cross-repo task governance process and endpoint backlog alignment.
- [x] 2026-04-04: Backend added `POST /api/v1/backtests/:run_id/resync` and sync-health metrics fields (`run_age_seconds`, `sync_lag_seconds`, `quality_issues`) for dashboard consumption.
- [x] 2026-04-04: Backend added contract-lock test coverage for `POST /api/v1/backtests/:run_id/resync` response shape.
- [x] 2026-04-04: Frontend added responsive container standardization and mock backtest detail fallback for `/backtest/mock-run-*` in `BacktestDetailsV2`.
- [ ] Add first frontend implementation entry after sync-health panel and contract checks are implemented.

## Change Log Template
- Date:
- Endpoint(s):
- UI/state impact:
- Error handling impact:
- Backend tasks updated: yes/no
- Bot tasks updated: yes/no
