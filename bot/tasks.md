# Backend Integration Tasks

## Status Summary
- Completed: `40`
- Pending: `0`
- Last updated: `2026-04-10`
- Note: update these totals whenever any [x] or [ ] task changes.

## Cross-Repo Status Snapshot

| Repo | Completed | Pending | Focus |
| --- | --- | --- | --- |
| backend | 54 | 0 | Delegated contract parity and contract-lock coverage shipped |
| bot | 28 | 0 | Canonical API contract and runtime envelope/documentation stability |
| frontend | 56 | 5 | Remaining responsive evidence + medium-priority backend integration asks |

Snapshot date: `2026-04-04`.

## Cross-Repo Sync Matrix (Weekly Snapshot)
| Area | Bot Status | Backend Status | Frontend Status | Owner | ETA |
| --- | --- | --- | --- | --- | --- |
| Contract aliases (`progress`, `backtests`, `count`) | complete | complete | pending verification | backend + frontend | 2026-04-08 |
| Run-scoped `run_id` payload consistency | complete | complete | pending verification | backend + frontend | 2026-04-08 |
| `GET /api/v1/backtests/sync-health` | complete | complete | pending consumption | backend + frontend | 2026-04-09 |
| Auth token shape lock (`access_token`, `refresh_token`, `token_type`, `expires_in`) | complete (tests added) | complete | pending sync test | backend + frontend | 2026-04-09 |
| Trace propagation (`trace_id`, `X-Trace-Id`) | complete | complete | complete | backend + frontend | done |
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
- [x] 2026-04-08: Added a staging-to-production handoff pointer in `LOCAL_SETUP.md` directing engineers to `BACKEND_HANDOFF_CHECKLIST.md` for backend/bot production sign-off.
- [x] 2026-04-08: Added `BACKEND_HANDOFF_CHECKLIST.md` as a production-only backend rollout sign-off checklist (readiness, capabilities, runtime DB diagnostics, websocket checks, reconciliation, and GO/NO-GO fields).
- [x] 2026-04-08: Expanded backend-team onboarding docs with a startup quick path, required control-plane surface table, and authenticated smoke command examples in `BACKEND_BOT_INTEGRATION.md`; synced discovery-first guidance in `BOT_SERVICE_ENDPOINTS.md` and `API_CONTRACT.md`.
- [x] 2026-04-08: Added admin-only `GET /api/v1/runtime/db-config` endpoint for sanitized runtime DB diagnostics (cutover mode/source/host/port/pool/timeout/SSL metadata without secret values) to simplify deployment verification.
- [x] 2026-04-08: Hardened database config compatibility for shared-mode deployments using `DB_*` + `POSTGRES_*` keys and runtime tuning flags (`DB_TIMEOUT`, `DB_POOL_SIZE`, `DB_MAX_CONNECTIONS`, `DB_MAX_OVERFLOW`, `SSL_MODE`) so existing database blocks can be used without refactor.
- [x] 2026-04-08: Added backend-facing integration docs (`BOT_API_PARITY_MATRIX.md`, `BACKEND_BOT_INTEGRATION.md`) and introduced explicit bot DB cutover modes (`shared`, `dedicated`, `dedicated_with_shared_fallback`) for safer PostgreSQL isolation rollout/rollback.
- [x] 2026-04-08: Added `GET /api/v1/capabilities` for backend runtime discovery, websocket alias channels (`/ws/bots/{bot_instance_id}`, `/ws/backtests/{run_id}`), and bot-dedicated PostgreSQL env support (`BOT_DATABASE_URL` / `BOT_DB_*` with `DB_*` fallback).
- [x] 2026-04-08: Added admin-scoped interrupted backtest ops aliases (`GET /api/v1/admin/backtests/interrupted`, `POST /api/v1/admin/backtests/interrupted/reconcile`) and published `BACKTEST_ENDPOINTS.md` with endpoint-by-endpoint request/response payload examples for operators.
- [x] 2026-04-08: Added ops-focused interrupted backtest visibility/reconciliation endpoints (`GET /api/v1/backtests/interrupted`, `POST /api/v1/backtests/interrupted/reconcile`) with dry-run-first behavior and explicit persisted fail-closed reconciliation reporting.
- [x] 2026-04-08: Backtest run state now persists in PostgreSQL (`backtest_runtime_runs`) and status polling endpoints (`/api/v1/backtests/{run_id}/status`, related run-scoped reads) survive API reloads/restarts; orphaned in-progress runs fail closed as `failed` with interruption reason on service restart.
- [x] 2026-04-08: Bot startup now safely normalizes legacy `bot_instances.status` values before ORM reads, backend runtime metadata persistence now stores credential-bearing bot config for future DB recovery, and noisy dYdX node-prefix stderr warnings are filtered during API import/startup.
- [x] 2026-04-08: Local TTY runs now use colored structured Loguru formatting, and `src/` runtime modules were migrated off direct `logging.getLogger(...)` usage while keeping plain-text subprocess log files under `bot_states/`.
- [x] 2026-04-08: Development-mode logging now forces verbose API request traces (`request_started` / `request_completed`) with trace id, safe query context, duration, and status-based warning/error severity for faster local debugging.
- [x] 2026-04-04: Centralized 5xx response sanitization in `api_response(...)` so all internal errors return a safe generic message and never leak raw exception/SQL details to clients.
- [x] 2026-04-04: Hardened `/api/v1/backtests` + `/api/v1/backtests/run` strategy-lookup path to fall back to manual payload when strategy persistence is temporarily unavailable; removed raw DB error leakage from these internal-error responses.
- [x] 2026-04-04: Backend completed delegated bot-instance parity follow-ups (stop `force` passthrough, trades `status` query alignment, realtime numeric ID guardrails) and added bot contract-lock integration coverage; backend task backlog now reports pending `0`.
- [x] 2026-04-04: Backend delegated passthrough routes now preserve upstream status and include upstream-safe message in both `error` and `message` fields for operator debugging consistency.
- [x] 2026-04-04: Backend resync endpoint now returns deterministic run/job state fields to stabilize cross-service retry and UI manual-resync flows.
- [x] 2026-04-04: Backend unified delegated non-stream backtest success envelopes and now preserves status/sync-health compatibility aliases within the canonical response shape.
- [x] 2026-04-04: Backend standardized delegated backtest details/empty-state payloads and enabled broader CI contract-lock enforcement for frontend-facing backtest routes.
- [x] 2026-04-04: Adopted cross-repo task governance format with backend/frontend linkage.
- [x] 2026-04-05: Added strict `/ready` readiness probe and completed cross-service trace passthrough from frontend -> backend -> bot HTTP/websocket paths for production triage.
- [x] 2026-04-04: Added contract aliases (`progress`, `backtests`, `count`), run-scoped `run_id` coverage, `sync-health`, trace-id logging, and runtime queue/job counters.
- [x] 2026-04-04: Synced with backend governance enforcement and new backend sync capabilities (`resync`, `run_age_seconds`, `sync_lag_seconds`, `quality_issues`).
- [x] 2026-04-04: Improved Telegram interaction safety/ops signal with HTML-safe escaping, truncation, severity/category-based dedupe policy, and category-tagged runtime alerts.
- 2026-04-05: Added strategy runtime websocket snapshot/lifecycle events, per-instance subprocess log files, and a continuous dead-process monitor so backend/frontend integrations receive truthful bot state without relying on manual polling alone.

## Change Log Template
- Date:
- Endpoint(s):
- Payload changes:
- Sync impact (runs/trades/positions/candles):
- Frontend tasks updated: yes/no
- Backend tasks updated: yes/no
