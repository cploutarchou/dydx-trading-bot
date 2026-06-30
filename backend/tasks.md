# Backend Tasks

## Status Summary
- Completed: `58`
- Pending: `0`
- Last updated: `2026-06-30`
- Note: update these totals whenever any [x] or [ ] task changes.

## Cross-Repo Status Snapshot

| Repo | Completed | Pending | Focus |
| --- | --- | --- | --- |
| backend | 58 | 0 | Artifact-backed trade flow shipped; sync-health/resync semantics completed |
| bot | 26 | 0 | Canonical API contract and runtime envelope/documentation stability |
| frontend | 61 | 4 | Remaining responsive evidence + artifact-backed trade/sync-health follow-up |

Snapshot date: `2026-06-30`.

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
- [x] Sync child artifacts into `backtest_positions` and `backtest_candles`; delegated trade reads stay on the bot/artifact path instead of mirroring `backtest_trades`.
- [x] Preserve dedupe semantics:
  - positions by `position_id`
  - candles by `(run_id, market, timestamp, resolution)`
- [x] Add protected sync-health endpoint with per-run counts (`runs/trades/positions/candles`).

## Open Improvements
- [x] Add metrics endpoint for sync lag/age per run.
- [x] Add optional force-resync endpoint for a run (`run_id`) from bot upstream.
- [x] Add data quality checks for incomplete child artifacts (missing IDs, invalid timestamps).
- [x] Reconcile `GET /api/v1/backtests/sync-health` trade counters with the MinIO-backed trade path so new runs do not imply backend DB trade mirroring.
- [x] Reconcile `POST /api/v1/backtests/:run_id/resync` response semantics (`trades_synced`) with the artifact-backed trade flow to avoid misleading operator state.

## Frontend-Driven Backend Backlog

### Backtest Details Contract Stability
- [x] Ensure `GET /api/v1/backtests/:run_id` always returns stable keys used by UI (`status`, `progress_percent|progress_pct|progress`, `total_pnl`, `win_rate`, `sharpe_ratio`, `max_drawdown_pct`, `total_trades`).
- [x] Normalize optional metrics to explicit `null` values instead of omitting keys.
- [x] Ensure `GET /api/v1/backtests/:run_id/logs` returns `200` with `data.logs: []` when no logs are available (avoid repetitive `404` for active-run polling).
- [x] Standardize `GET /api/v1/backtests/:run_id/analytics` payload to always include `data.daily_pnl` as an array.
- [x] Standardize `GET /api/v1/backtests/:run_id/positions/snapshots` payload to always include `data.snapshots` as an array.
- [x] Standardize `GET /api/v1/backtests/:run_id/trades/detailed` payload to always include `data.trades` and `data.total`.

### Progress + Sync Guarantees
- [x] Ensure `GET /api/v1/backtests/:run_id/status` exposes near-real-time `progress_pct` plus `current_pair/current_task` for running jobs.
- [x] For pending jobs, return `progress_pct: 0` and `current_task: null`.
- [x] Extend `GET /api/v1/backtests/sync-health` to always provide per-run counts (`trades`, `positions`, `candles`) plus lag/age fields.
- [x] Keep `POST /api/v1/backtests/:run_id/resync` idempotent and include deterministic job/run state in response envelope.

### Error Semantics + Contract-Lock
- [x] Preserve response envelope `{ success, message, data, timestamp }` across all non-stream `/api/v1/backtests/*` routes.
- [x] Preserve upstream passthrough status/message for delegated bot/strategy endpoints where safe.
- [x] Add contract-lock tests for the standardized empty-state shapes above (logs/analytics/snapshots/trades-detailed).
- [x] Add CI failure conditions for required-key omissions on high-traffic payloads consumed by frontend.

### Bot Instance Delegation + Payload Parity (Audit Follow-up)
- [x] Align `/api/v1/bots/:instance_id/trades` query contract with bot upstream (`status` filter) and remove/rework legacy `limit/offset/winning_only` passthrough in `internal/services/bot_api_client.go` + `internal/services/bot_instance_service.go`.
- [x] Pass through `force` on `POST /api/v1/bots/:instance_id/stop` by wiring handler query parsing to `StopBotInstanceWithForce(...)`.
- [x] Resolve bot identifier type mismatch for delegated realtime routes that upstream defines with integer `bot_instance_id` (`/positions/{position_id}`, `/market-data`, `/realtime-stats`, `/alerts`, `/position-history/{position_id}`), including deterministic mapping from external `instance_id` where required.
- [x] Add contract-lock tests for bot lifecycle endpoints (`GET/POST /api/v1/bots`, `GET/DELETE /api/v1/bots/:instance_id`, start/stop/restart) to verify upstream payload parity and stable envelope fields.
- [x] Add contract-lock tests for bot trade/stat/history delegated payloads to ensure required keys and query semantics stay aligned with `src/api/server.py` and `openapi.json`.
- [x] Deprecate or refactor unused legacy client methods with stale query semantics (`GetBotInstanceHistory`, `GetBotInstanceTrades`) to prevent accidental contract regression.
- [x] Add one backend integration test suite that compares delegated route responses against bot OpenAPI-required payload keys for high-traffic bot endpoints.

## Change Log

- [x] 2026-04-04: Validated delegated backend compatibility after bot-wide 5xx message sanitization (`api_response`) to ensure backend passthrough contracts remain stable while upstream internal details stay redacted.
- [x] 2026-04-04: Validated delegated backend contract compatibility after bot backtest strategy-lookup fallback hardening; no backend route contract changes required for this bot-side resilience fix.
- [x] 2026-04-04: Added bot contract-lock coverage in `internal/routes/bot_instance_contract_lock_test.go` for lifecycle envelope stability, stop-force passthrough, trades `status` query forwarding, and required-key checks on delegated high-traffic bot endpoints; removed stale legacy client history method.
- [x] 2026-04-05: Added request-trace middleware (`X-Trace-Id`) with passthrough to delegated bot HTTP/websocket calls, response echoing for operators, and a strict `/ready` endpoint for deploy/readiness checks.
- [x] 2026-04-04: Implemented bot-instance parity fixes in backend routes/services for stop-force passthrough, trades `status` query contract alignment, and numeric `instance_id` validation on delegated realtime endpoints requiring upstream integer path params.
- [x] 2026-04-04: Audited backend delegated bot endpoint parity vs bot OpenAPI/server contract; added pending follow-ups for stop-force passthrough, trades query semantics, bot ID mapping on realtime routes, and bot-route contract-lock coverage.
- [x] 2026-04-04: Extended `POST /api/v1/backtests/:run_id/resync` response with deterministic run/job state (`run_id`, `status`, progress aliases, `current_task`, `current_pair`, `sync_state`) and added contract tests.
- [x] 2026-04-04: Preserved delegated bot/strategy upstream error passthrough semantics by keeping upstream status and surfacing message via both `error` and `message` keys.
- [x] 2026-04-04: Standardized delegated non-stream `/api/v1/backtests/*` responses on `{ success, message, data, timestamp }` while preserving legacy top-level aliases for compatibility.
- [x] 2026-04-04: Hardened `GET /api/v1/backtests/:run_id` normalization for nested envelopes, explicit `null` metrics, progress aliases, and expanded contract-lock CI coverage.
- [x] 2026-04-04: Added strict contract-lock tests for delegated high-traffic backtest endpoints.
- [x] 2026-04-04: Implemented delegated run/status DB sync for `backtest_runs`.
- [x] 2026-04-04: Extended sync to child artifacts (`trades`, `positions`, `candles`) with upsert/dedupe.
- [x] 2026-04-04: Added `GET /api/v1/backtests/sync-health` dashboard-style sync count endpoint.
- [x] 2026-04-04: Added cross-repo task governance in backend/bot/frontend task files.
- [x] 2026-04-04: Added governance validator + make targets (`tasks-validate`, `tasks-governance`) and PR checklist template.
- [x] 2026-04-04: Added force-resync endpoint and sync health metrics (`run_age_seconds`, `sync_lag_seconds`, `quality_issues`).
- [x] 2026-04-04: Added strict contract-lock response-shape test for `POST /api/v1/backtests/:run_id/resync`.
- [x] 2026-04-04: Added frontend-driven backend backlog section for backtest details contracts, progress guarantees, and empty-state response normalization.
- [x] 2026-06-30: Stopped mirroring delegated backtest trade payloads into backend `backtest_trades`; delegated trade reads stay on the bot/artifact path while positions/candles continue syncing locally.
- [x] 2026-06-30: Bot-side backtest status persistence now refreshes DB-backed runs after cross-process worker completion, so delegated backend status reads receive truthful terminal states from the upstream bot API without contract changes.
- 2026-04-05: Added real strategy runtime control endpoints (`GET /api/v1/strategies/:id/runtime`, `POST /api/v1/strategies/:id/start`, `POST /api/v1/strategies/:id/stop`) backed by deterministic bot-instance orchestration and verified route coverage.

## Change Log Template
- Date:
- Endpoint(s):
- Request change:
- Response change:
- Auth/middleware impact:
- DB schema/sync impact:
- Bot tasks updated: yes/no
- Frontend tasks updated: yes/no
