# Backend -> Bot Integration Guide

This guide describes how backend services should integrate with the bot service as the single runtime control plane.

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
3. Connect `WS /ws/strategies`
4. For each active instance, connect `WS /ws/bots/{bot_instance_id}`
5. For each active backtest, connect `WS /ws/backtests/{run_id}`
6. Reconcile from HTTP snapshots if any websocket events are missed

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

