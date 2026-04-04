# dYdX Trading Bot Monorepo

This repository contains the active dYdX trading stack split across three service directories:

- `frontend/` — React + TypeScript + Vite dashboard
- `backend/` — Go API gateway/orchestration layer on `:8888`
- `bot/` — Python Bot API on `:8889` plus the worker runtime in `bot/src/main_instance.py`

The primary request path is:

`frontend` → `backend` → `bot` API → worker/runtime

PostgreSQL and Redis provide shared state, persistence, and caching.

## Shared environment

Use the repo-root `.env` as the shared development environment file for `frontend/`, `backend/`, and `bot/`.

- `frontend` reads `VITE_*` variables from the repo root
- `backend` loads the repo-root `.env`
- `bot` entrypoints and config load the repo-root `.env`

Normal local development should not require `backend/.env`, `bot/.env`, or `frontend/.env.local`.

## Quick start

### Service-first development

1. Create the shared env file if needed:
   - `make stack-env`
2. Start shared infrastructure only:
   - `make infra-up`
3. Run the service you are working on:
   - Frontend: `cd frontend && npm install && npm run dev`
   - Backend: `cd backend && make run` or `make dev`
   - Bot API: `cd bot && python3 -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload`
   - Bot worker: `cd bot && python3 src/main_instance.py --instance-id bot-1`
4. Stop shared infrastructure when finished:
   - `make infra-down`

### Full integration stack

Use this when validating the whole stack together:

1. `make stack-env`
2. `make stack-up-dev`
3. `make stack-ps`
4. `make stack-logs`
5. `make stack-down`

### Prod-like local stack

Use the split app stack with the proxy profile:

- `make stack-up-prod`

Default proxy entry point: `http://localhost:8080`

## Service roles

### Frontend (`frontend/`)

The dashboard handles:

- authentication and session UX
- bot instance management
- backtest execution and results inspection
- monitoring and operator workflows

### Go backend (`backend/`)

The backend is the active UI-facing API layer. It:

- authenticates UI requests
- proxies/orchestrates bot actions
- exposes backtest and bot routes to the frontend
- coordinates DB-backed and delegated responses

### Python bot API (`bot/`)

The bot API is the control plane for:

- auth/session routes used by bot-side services
- bot instance lifecycle
- backtest compatibility endpoints
- runtime coordination with the worker layer

### Worker runtime (`bot/src/main_instance.py`)

The worker executes trading logic, including:

- market data polling
- signal generation
- position lifecycle management
- per-instance state handling under `bot/bot_states/`

## Useful commands

- `make stack-env` — create `.env` from `.env.example` if missing
- `make infra-up` / `make infra-down` — start or stop shared Postgres + Redis
- `make infra-ps` / `make infra-logs` — inspect infra state
- `make stack-up-dev` / `make stack-down` — start or stop the integration stack
- `make stack-ps` / `make stack-logs` — inspect integration services
- `cd backend && make test` — backend tests
- `cd frontend && npm run lint` — frontend lint
- `cd bot && python3 -m pytest tests/ -v` — bot tests

## VS Code notes

This repository currently includes root-level VS Code launch/task configuration in `.vscode/` for integration workflows.
There are no committed service-specific `.code-workspace` files in this checkout, so prefer opening the repo directly and using the root tasks/launch profiles.

## Troubleshooting

### Docker stack issues

- Confirm Docker is running: `docker info`
- Check port conflicts: `lsof -i :5173,8888,8889,5432,6379`
- Review logs with `make stack-logs` or `make infra-logs`

### Missing `.env`

- Run `make stack-env`, then fill in any required secrets before non-local use

### Port already in use

- Frontend: `kill $(lsof -ti :5173)`
- Backend: `kill $(lsof -ti :8888)`
- Bot API: `kill $(lsof -ti :8889)`

## Notes

- The Go backend in `backend/` is active and should not be documented as legacy.
- Trading-safety-sensitive Python changes should follow the conventions in `.github/copilot-instructions.md` and `bot/.github/copilot-instructions.md`.
