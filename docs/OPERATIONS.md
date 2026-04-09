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
