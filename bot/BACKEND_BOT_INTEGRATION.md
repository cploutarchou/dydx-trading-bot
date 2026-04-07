# Backend -> Bot Integration Guide

This guide describes how backend services should integrate with the bot service as the single runtime control plane.

For production rollout sign-off only, use `BACKEND_HANDOFF_CHECKLIST.md`.

## Backend Team Quick Path

Use this sequence for day-1 integration:

1. Verify readiness via `GET /ready` (require HTTP `200`).
2. Discover surface contract via `GET /api/v1/capabilities`.
3. Verify runtime DB mode/source (admin token) via `GET /api/v1/runtime/db-config`.
4. Connect websocket channels in this order:
   - `WS /ws/strategies`
   - `WS /ws/bots/{bot_instance_id}`
   - `WS /ws/backtests/{run_id}`
5. Reconcile with HTTP snapshots on reconnect/missed events.

## Backend Control-Plane Surface (must-use)

| Purpose | Endpoint/channel |
| --- | --- |
| Readiness gate | `GET /ready` |
| API/WS contract discovery | `GET /api/v1/capabilities` |
| Runtime DB diagnostics (admin) | `GET /api/v1/runtime/db-config` |
| Bot lifecycle control | `POST/GET/DELETE /api/v1/bots*` |
| Backtest orchestration | `POST/GET /api/v1/backtests*` |
| Strategy lifecycle stream | `WS /ws/strategies` |
| Bot runtime stream | `WS /ws/bots/{bot_instance_id}` |
| Backtest progress stream | `WS /ws/backtests/{run_id}` |

## 1) Base URLs

- HTTP: `http://<bot-host>:8889`
- WebSocket: `ws://<bot-host>:8889`

## 2) Auth and trace

- Send `Authorization: Bearer <token>` for HTTP and WS.
- Send `X-Trace-Id: <trace-id>` on HTTP calls.
- WS can pass token via `Authorization` header or `access_token` query parameter.

## 3) Startup capability handshake

Call:

- `GET /api/v1/capabilities`

Use the returned `http_endpoints`, `websocket_channels`, and grouped `command_endpoints` / `query_endpoints` / `event_channels` to verify contract compatibility at startup.

## 4) Suggested bootstrap flow

1. `GET /ready` and require HTTP `200`
2. `GET /api/v1/capabilities`
3. `GET /api/v1/runtime/db-config` (admin path; optional but recommended for deployment verification)
4. Connect `WS /ws/strategies`
5. For each active instance, connect `WS /ws/bots/{bot_instance_id}`
6. For each active backtest, connect `WS /ws/backtests/{run_id}`
7. Reconcile from HTTP snapshots if any websocket events are missed

## 5) Dedicated PostgreSQL for bot service

Bot service supports dedicated DB cutover controls:

- `BOT_DB_CUTOVER_MODE=shared`
  - Use shared `DB_*` / `DATABASE_URL` only
- `BOT_DB_CUTOVER_MODE=dedicated`
  - Require `BOT_DATABASE_URL` or full `BOT_DB_*`
- `BOT_DB_CUTOVER_MODE=dedicated_with_shared_fallback`
  - Prefer bot-dedicated target; fallback to shared DB when bot target is unset

### Preferred dedicated URL

```env
BOT_DB_CUTOVER_MODE=dedicated
BOT_DATABASE_URL=postgresql://bot_user:bot_password@bot-db-host:5432/dydx_bot
```

### Dedicated fields alternative

```env
BOT_DB_CUTOVER_MODE=dedicated
BOT_DB_TYPE=postgresql
BOT_DB_HOST=bot-db-host
BOT_DB_PORT=5432
BOT_DB_NAME=dydx_bot
BOT_DB_USER=bot_user
BOT_DB_PASSWORD=bot_password
```

### Shared DB keys supported directly

When running in `BOT_DB_CUTOVER_MODE=shared`, the bot uses these keys directly:

- `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `DB_TIMEOUT`, `DB_POOL_SIZE`, `DB_MAX_CONNECTIONS`, `DB_MAX_OVERFLOW`, `DB_ECHO_SQL`, `SSL_MODE`

Compatibility aliases are also supported when `DB_*` values are absent:

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

## 6) Recovery behavior to depend on

- Backtest run polling state is persisted in `backtest_runtime_runs`.
- Interrupted in-progress runs are detectable via:
  - `GET /api/v1/backtests/interrupted`
  - `GET /api/v1/admin/backtests/interrupted`
- Reconciliation can be triggered with dry run first:
  - `POST /api/v1/backtests/interrupted/reconcile?dry_run=true`

## 7) Minimal smoke commands

```bash
curl -sS http://localhost:8889/ready
curl -sS http://localhost:8889/api/v1/capabilities
curl -sS http://localhost:8889/api/v1/backtests/sync-health
```

Authenticated smoke example (service token/JWT):

```bash
BOT_TOKEN="<token>"
curl -sS -H "Authorization: Bearer ${BOT_TOKEN}" http://localhost:8889/api/v1/capabilities
curl -sS -H "Authorization: Bearer ${BOT_TOKEN}" http://localhost:8889/api/v1/runtime/db-config
```

