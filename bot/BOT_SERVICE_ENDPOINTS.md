# Bot Service API and WebSocket Endpoints

This file is a backend-integration map for bot runtime control surfaces.
Use it together with `API_CONTRACT.md`, `BACKTEST_ENDPOINTS.md`, and `openapi.json`.

Companion docs:

- `BOT_API_PARITY_MATRIX.md`
- `BACKEND_BOT_INTEGRATION.md`

## Standard Response Envelope

Most non-auth HTTP endpoints return:

```json
{
  "success": true,
  "message": "Human-readable message",
  "data": {}
}
```

## Capability Discovery Endpoint

- **Method/Path**: `GET /api/v1/capabilities`
- **Use**: runtime discovery of bot/backtest HTTP and WS channels for backend bootstrapping and health checks.

Example `data` payload:

```json
{
  "service": "bot",
  "http_endpoints": ["GET /api/v1/bots", "POST /api/v1/backtests"],
  "websocket_channels": ["WS /ws/strategies", "WS /ws/bots/{bot_instance_id}"],
  "http_count": 2,
  "websocket_count": 2,
  "count": 4
}
```

## Bot Lifecycle API

- `POST /api/v1/bots`
- `GET /api/v1/bots`
- `GET /api/v1/bots/{instance_id}`
- `POST /api/v1/bots/{instance_id}/start`
- `POST /api/v1/bots/{instance_id}/stop`
- `POST /api/v1/bots/{instance_id}/restart`
- `DELETE /api/v1/bots/{instance_id}`

## Bot Runtime and Observability API

- `GET /api/v1/bots/{instance_id}/history`
- `GET /api/v1/bots/{instance_id}/jobs`
- `GET /api/v1/bots/{instance_id}/trades`
- `GET /api/v1/bots/{instance_id}/stats`
- `GET /api/v1/bots/{bot_instance_id}/positions/current`
- `GET /api/v1/bots/{bot_instance_id}/positions/{position_id}`
- `GET /api/v1/bots/{bot_instance_id}/market-data`
- `GET /api/v1/bots/{bot_instance_id}/realtime-stats`
- `GET /api/v1/bots/{bot_instance_id}/alerts`
- `GET /api/v1/bots/{bot_instance_id}/position-history/{position_id}`

## Backtest API

Backtest routes are documented in detail in `BACKTEST_ENDPOINTS.md`.

## WebSocket Channels

### Bot realtime channels

- `WS /api/v1/bots/{bot_instance_id}/positions/live`
- `WS /api/v1/bots/{bot_instance_id}/market/live`
- `WS /api/v1/bots/{bot_instance_id}/alerts/live`
- `WS /ws/bots/{bot_instance_id}` (alias channel for backend integrations)

### Backtest channels

- `WS /api/v1/backtests/{run_id}/live`
- `WS /ws/backtests/{run_id}` (alias channel for backend integrations)

### Strategy runtime channel

- `WS /ws/strategies`

## Dedicated PostgreSQL Configuration (Bot Service)

The bot service supports dedicated PostgreSQL settings with bot-specific precedence:

1. `BOT_DATABASE_URL` (preferred)
2. `BOT_DB_*` fields
3. fallback to shared `DB_*` fields

Cutover behavior is controlled by `BOT_DB_CUTOVER_MODE`:

- `shared`
- `dedicated`
- `dedicated_with_shared_fallback`

Supported URL schemes:

- `postgresql://...`
- `postgresql+psycopg2://...`
- `postgres://...` (normalized internally)

Non-PostgreSQL URLs are rejected.

### BOT_DB variables

```env
BOT_DB_TYPE=postgresql
BOT_DB_HOST=localhost
BOT_DB_PORT=5432
BOT_DB_NAME=dydx_bot
BOT_DB_USER=postgres
BOT_DB_PASSWORD=change-me
```

Or explicit URL:

```env
BOT_DATABASE_URL=postgresql://postgres:change-me@localhost:5432/dydx_bot
```

