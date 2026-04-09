# Backend-Only Integration Checklist

This document is the contract lock for frontend integration.

The rule is simple:

- the frontend talks only to the Go backend
- the Go backend talks to the Python bot service
- the frontend must never call the bot service directly over HTTP or websocket

## Required runtime path

```text
React frontend (5173)
  -> Go backend (8888)
  -> Python bot API (8889)
  -> bot runtime / DB / Redis
```

## Non-negotiable rules

1. Frontend HTTP requests must target backend-origin routes only.
2. Frontend websocket connections must target backend-origin websocket routes only.
3. Frontend code must not hardcode bot-service origins such as `localhost:8889`.
4. Frontend auth must be sent only to backend routes. The backend is responsible for forwarding request auth upstream when needed.
5. Backend remains the normalization layer for envelopes, trace IDs, auth propagation, retries, sync, and fallback behavior.

## Canonical frontend origin helpers

Use these files as the only source of truth for origin resolution:

- [origin.ts](/home/chris/workspace/dydx-trading-bot/frontend/src/api/origin.ts)
- [api.ts](/home/chris/workspace/dydx-trading-bot/frontend/src/api.ts)
- [enhancedClient.ts](/home/chris/workspace/dydx-trading-bot/frontend/src/api/enhancedClient.ts)

What they guarantee:

- HTTP resolves against the backend origin
- websocket URLs resolve against the backend origin
- websocket auth uses `access_token`
- local dev can still use the Vite proxy without changing call sites

## Approved frontend websocket routes

These are the only live routes the frontend should open directly:

- `/api/v1/backtests/:run_id/live`
- `/ws/backtests/:run_id`
- `/ws/bots/:instance_id`
- `/ws/strategies`

All of them terminate on the Go backend first. The backend then proxies upstream as needed in [bot_api_delegate_routes.go](/home/chris/workspace/dydx-trading-bot/backend/internal/routes/bot_api_delegate_routes.go).

## Approved frontend HTTP route families

These route families are expected to be frontend-facing:

- `/api/v1/auth/*`
- `/api/v1/backtests/*`
- `/api/v1/bots/*`
- `/api/v1/strategies/*`
- `/api/v1/system/*`
- `/api/v1/settings/*`
- `/health`
- `/ready`

The frontend should never replace these with direct bot URLs even if the bot exposes a similarly named endpoint.

## Backend ownership by domain

### Backtests

- frontend uses backend backtest routes from [api.ts](/home/chris/workspace/dydx-trading-bot/frontend/src/api.ts)
- backend delegates live bot-backed backtest operations in [bot_api_delegate_routes.go](/home/chris/workspace/dydx-trading-bot/backend/internal/routes/bot_api_delegate_routes.go)
- backend syncs selected upstream backtest payloads into local DB tables through [backtest_sync_service.go](/home/chris/workspace/dydx-trading-bot/backend/internal/services/backtest_sync_service.go)

### Bot instances

- frontend uses backend bot routes through [enhancedClient.ts](/home/chris/workspace/dydx-trading-bot/frontend/src/api/enhancedClient.ts)
- backend brokers bot instance operations through [bot_instance_routes.go](/home/chris/workspace/dydx-trading-bot/backend/internal/routes/bot_instance_routes.go) and the delegated bot API client

### Live runtime streams

- frontend opens backend websocket channels only
- backend forwards those channels upstream in [bot_api_delegate_routes.go](/home/chris/workspace/dydx-trading-bot/backend/internal/routes/bot_api_delegate_routes.go)

## Audit checklist for new frontend features

Before shipping a new data surface:

- confirm the UI uses `api.ts`, `enhancedClient.ts`, or shared hooks instead of ad hoc `fetch`
- confirm no code constructs a bot-service URL directly
- confirm websocket URLs come from [origin.ts](/home/chris/workspace/dydx-trading-bot/frontend/src/api/origin.ts)
- confirm backend has the route and normalizes the response shape the UI expects
- confirm the route is authenticated at the backend, not by bypassing to the bot
- confirm trace IDs and upstream error messages survive the backend boundary cleanly

## Red flags

If any of these appear, treat them as integration regressions:

- `localhost:8889` referenced in `frontend/src/**`
- websocket auth using `?token=` instead of backend-standard `access_token`
- new `fetch()` or `WebSocket()` call sites bypassing the shared API/origin helpers
- frontend logic depending on raw bot payload shape without backend normalization
- frontend code assuming the bot is reachable from the browser

## Verification commands

Frontend checks:

```bash
cd frontend
npx vitest run src/api/origin.test.ts src/api/enhancedClient.test.ts
npm run lint
npm run build
```

Backend checks:

```bash
cd backend
go test ./internal/routes ./internal/services
```

## Current lock status

As of the current audit:

- frontend HTTP origin resolution is backend-only
- frontend websocket origin resolution is backend-only
- backend delegated bot routes are the active backtest surface
- legacy direct frontend-to-bot integration was not found in active frontend code paths

Keep this document updated whenever a new live channel or delegated route is added.
