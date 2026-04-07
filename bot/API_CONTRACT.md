# API Contract Reference

This document is the quick contract guide for backend/frontend integrations against the bot API.

## Canonical Sources

- Runtime API implementation: `src/api/server.py`
- Runtime Swagger UI: `http://localhost:8889/docs`
- Runtime ReDoc: `http://localhost:8889/redoc`
- Runtime OpenAPI JSON: `http://localhost:8889/openapi.json`
- Workspace OpenAPI snapshot: `openapi.json`
- Contract tests:
  - `tests/test_backtest_api_contract.py`
  - `tests/test_auth_api_contract.py`

## Standard HTTP Response Envelope

Most non-auth HTTP endpoints return:

```json
{
  "success": true,
  "message": "Human-readable status",
  "data": {},
  "timestamp": "2026-04-04T10:22:33.123456",
  "trace_id": "req-abc123def456"
}
```

Notes:
- `trace_id` is also returned as `X-Trace-Id` response header.
- `data` may be an object, array, scalar, or `null`.
- `timestamp` is generated server-side per response.

## Auth Contract Exceptions

Auth routes intentionally use auth-specific payloads instead of the standard envelope:

- `/auth/*`
- `/api/v1/auth/*`

Token response contract (locked by tests):

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## Backtest Compatibility Fields

For backend/frontend compatibility, backtest payloads include stable aliases:

- `GET /api/v1/backtests`
  - canonical list keys plus aliases: `runs`, `backtests`, `count`
- `GET /api/v1/backtests/{run_id}/status`
  - includes `progress_pct` and alias `progress`
  - includes `count: 1`
  - run status is persisted server-side, so polling survives API reload/restart events
- Run-scoped child endpoints include `run_id` in `data`.

## Contract Quick Table

All routes below use the standard envelope unless noted. Required keys are listed for `data`.

| Endpoint | Required `data` keys | Notes |
| --- | --- | --- |
| `POST /api/v1/backtests/run` | `run_id`, `status`, `progress_pct`, `progress`, `count` | Frontend-compatible run route; `count` is `1`. |
| `GET /api/v1/backtests` | `runs`, `backtests`, `total`, `count` | `backtests` is compatibility alias for `runs`. |
| `GET /api/v1/backtests/{run_id}` | `status`, `progress_pct`, `total_pnl`, `win_rate`, `sharpe_ratio`, `max_drawdown_pct`, `total_trades` | Optional metrics may be `null`. |
| `GET /api/v1/backtests/{run_id}/status` | `run_id`, `status`, `progress_pct`, `progress`, `count` | Running-state route used for polling. |
| `GET /api/v1/backtests/{run_id}/trades` | `run_id`, `trades`, `total`, `count` | Trade list is run-scoped. |
| `GET /api/v1/backtests/{run_id}/position-snapshots` | `run_id`, `snapshots`, `position_snapshots`, `total`, `count` | `snapshots` is primary frontend key; alias retained. |
| `GET /api/v1/backtests/sync-health` | `status` plus runtime counters (for example `queue_depth`, `active_jobs`, `total_runs`) | Runtime counters come from backtest service health output. |
| `GET /api/v1/backtests/interrupted` | `interruption_error`, `orphaned_in_progress`, `interrupted_runs`, `orphaned_count`, `interrupted_count`, `count` | Ops visibility for stale in-progress runs and previously reconciled interruption failures. |
| `POST /api/v1/backtests/interrupted/reconcile` | `interruption_error`, `dry_run`, `candidates`, `reconciled`, `candidate_count`, `reconciled_count`, `count` | Default `dry_run=true`; set `dry_run=false` to persist fail-closed reconciliation. |
| `GET /api/v1/admin/backtests/interrupted` | Same as `/api/v1/backtests/interrupted` | Admin-scoped alias for ops dashboards requiring elevated auth. |
| `POST /api/v1/admin/backtests/interrupted/reconcile` | Same as `/api/v1/backtests/interrupted/reconcile` | Admin-scoped alias for explicit reconciliation workflows. |
| `POST /api/v1/bots` | operation payload object (bot lifecycle result) | Wrapped in standard envelope for API consumers. |
| `GET /api/v1/bots` | `bots`, `total` | Bot list endpoint for control plane UI. |
| `GET /health` | `status`, `api_version`, `timestamp`, `backtest_runtime` | Liveness endpoint wrapped in the standard envelope. |
| `GET /ready` | `status`, `bot_manager_ready`, `timestamp`, `backtest_runtime` | Readiness endpoint returns HTTP `503` when the bot manager is unavailable. |

For auth routes (`/auth/*`, `/api/v1/auth/*`), use the auth-specific payload contracts above.

For a full backtest endpoint catalog with example request/response payloads, see `BACKTEST_ENDPOINTS.md`.

## Error and Trace Behavior

- Failures use `success: false` with a descriptive `message`.
- Trace propagation is request-scoped; if client sends `X-Trace-Id`, it is reused.
- Backend now forwards `X-Trace-Id` to both delegated HTTP calls and strategy websocket connections so a single operator action can be correlated across frontend, backend, and bot logs.
- In development mode, request logs include method, path, status, duration, client, and trace id.

## WebSocket Auth

WebSocket routes require bearer auth unless `API_BYPASS_AUTH=true`.

Supported token sources:
- `Authorization: Bearer <token>` header
- `access_token` query parameter

## Strategy Runtime WebSocket

`GET /ws/strategies` is the live strategy-runtime channel consumed through the backend websocket proxy.

Behavior:
- on connect, the channel now sends a `strategy_status_snapshot` message containing the current strategy-managed runtime states
- lifecycle transitions then stream as `strategy_status` messages
- strategy-managed instances are identified by deterministic instance ids of the form `strategy-<user_id>-<strategy_id>`

Realtime payload keys used by the frontend/backend flow:
- `strategyId`
- `instance_id`
- `status`
- `bot_status`
- `updatedAt`
- `network`
- optional `lastError`

This channel is advisory and low-latency; HTTP polling remains the source of truth for recovery and missed-message scenarios.

## Update Rule

If any response shape or required key changes:

1. Update `src/api/server.py`
2. Regenerate `openapi.json`
3. Update contract tests in `tests/test_backtest_api_contract.py` and/or `tests/test_auth_api_contract.py`
4. Sync task files when integration contracts change:
   - `tasks.md`
   - `../backend/tasks.md`
   - `../frontend/tasks.md`
