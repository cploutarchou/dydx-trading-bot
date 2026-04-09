# Operations Guide

## Health Endpoints

### Backend

- `GET /health`
- `GET /ready`

### Bot

- `GET /health`
- `GET /ready`
- `GET /api/v1/capabilities`
- `GET /api/v1/runtime/db-config`

## Runtime Datastores

The local development baseline is intentionally split:

- backend uses the backend PostgreSQL instance on `5432`
- bot uses the bot-dedicated PostgreSQL instance on `5433`

This mirrors the production ownership model and avoids accidental shared-state coupling.

### Database ownership guardrails

- bot runtime supports cutover modes via `BOT_DB_CUTOVER_MODE`:
  - `shared`
  - `dedicated`
  - `dedicated_with_shared_fallback`
- in `dedicated` mode, startup now blocks if the bot target resolves to the same host/port/name as the shared backend DB target
- backend startup validates DB ownership and rejects dedicated-mode shared-target regressions
- backend `GET /health` and `GET /ready` include `database_ownership` diagnostics (mode, backend target, bot target, separation state, blocking flag)

### Dedicated cutover and rollback playbook

1. **Prepare dedicated bot DB target**
	- set `BOT_DATABASE_URL` (or `BOT_DB_*`) to the bot-owned PostgreSQL instance
	- keep backend `DB_*` / `DATABASE_URL` pointing at backend-owned DB
2. **Enable dedicated mode**
	- set `BOT_DB_CUTOVER_MODE=dedicated`
	- restart bot and backend
3. **Verify separation**
	- backend `GET /ready` returns `ready=true`
	- backend `database_ownership.separated=true`
	- bot `/api/v1/runtime/db-config` shows dedicated source and target metadata
4. **Rollback safely (if needed)**
	- switch bot to `BOT_DB_CUTOVER_MODE=dedicated_with_shared_fallback` for temporary fallback behavior
	- if full rollback is required, switch to `shared` and restart services
	- re-verify `GET /health` / `GET /ready` and runtime behavior after rollback

## Live Data Flow

### Backtests

- bot computes and persists backtest state
- backend proxies and normalizes the contract
- frontend subscribes via backend websocket channels and uses HTTP for bootstrap/recovery

### Strategy runtimes and bot stats

- bot emits runtime state
- backend proxies websocket/state surfaces
- frontend consumes backend-only live channels

## Troubleshooting

### Bot cannot start because port `5433` is unavailable

Start the dev infra:

```bash
make dev-infra
```

### Frontend is hitting the bot directly

Audit the frontend service code and ensure all origin helpers point to the backend origin, not `:8889`.

### Live views are stale

Check:

1. backend websocket proxy health
2. bot websocket emission
3. browser websocket connection in devtools
4. fallback HTTP recovery path

### Config drift

Regenerate `run.json`:

```bash
make dev
```

## Production Readiness Baseline

Before production rollout, validate:

- service-specific credentials are configured correctly
- backend and bot databases are separated
- readiness endpoints are green
- websocket channels are delivering live updates
- frontend is consuming backend-only routes
- strategy runtime preflight is passing for the selected environment
