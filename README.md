# dYdX Trading Bot Monorepo

This repository contains the active dYdX trading stack across three services plus shared infrastructure.

`frontend` → `backend` → `bot` API → worker/runtime

PostgreSQL and Redis provide shared persistence, state, and caching.

## Services

| Service     | Role                                   | Default port |
| ----------- | -------------------------------------- | ------------ |
| `frontend/` | React + TypeScript + Vite dashboard    | `5173`       |
| `backend/`  | Go API gateway and orchestration layer | `8888`       |
| `bot/`      | Python Bot API and trading runtime     | `8889`       |

## Shared environment

Use the repo-root `.env` for all three services, generated from the root `example.env` template.

- `frontend` reads `VITE_*` values from the repo root
- `backend` loads the repo-root `.env`
- `bot` entrypoints and config load the repo-root `.env`

You generally should not need `backend/.env`, `bot/.env`, or `frontend/.env.local` for normal local development.

## Quick start

### Service-first development

```bash
make stack-env
make infra-up
```

Then run the service you are working on:

- Frontend: `cd frontend && npm install && npm run dev`
- Backend: `cd backend && make run` or `make dev`
- Bot API: `cd bot && python3 -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload`
- Bot worker: `cd bot && python3 src/main_instance.py --instance-id bot-1`

When finished:

```bash
make infra-down
```

### Full integration stack

```bash
make stack-env
make stack-up-dev
make stack-ps
make stack-logs
make stack-down
```

### Prod-like local stack

```bash
make stack-up-prod
```

Default proxy entry point: <http://localhost:8080>

## Service roles

### Frontend

- authentication and session UX
- bot instance management
- backtest execution and results inspection
- monitoring and operator workflows

### Backend

- authenticates UI requests
- proxies and orchestrates bot actions
- exposes backtest and bot routes to the frontend
- coordinates DB-backed and delegated responses

### Bot API and worker

- auth and session routes used by bot-side services
- bot instance lifecycle management
- backtest compatibility endpoints
- runtime trading execution in `bot/src/main_instance.py`
- per-instance state under `bot/bot_states/`

## Common commands

```bash
make stack-env
make infra-up
make infra-down
make stack-up-dev
make stack-down
make stack-logs
cd frontend && npm run lint
cd backend && make test
cd bot && python3 -m pytest tests/ -v
```

## Where to read next

- Root instructions: [`.github/copilot-instructions.md`](.github/copilot-instructions.md)
- Frontend guide: [`frontend/README.md`](frontend/README.md)
- Backend tasks and guidance: [`backend/tasks.md`](backend/tasks.md)
- Bot local setup: [`bot/LOCAL_SETUP.md`](bot/LOCAL_SETUP.md)

## VS Code notes

This repository includes root-level VS Code launch/task configuration in `.vscode/` for integration workflows.
There are no committed service-specific `.code-workspace` files in this checkout, so prefer opening the repo directly and using the root tasks and launch profiles.

## Troubleshooting

### Missing `.env`

Run `make stack-env`, then fill in any required secrets before non-local use.

### Docker or stack issues

- Confirm Docker is running: `docker info`
- Check port conflicts: `lsof -i :5173,8888,8889,5432,6379`
- Review logs with `make stack-logs` or `make infra-logs`

### Port already in use

- Frontend: `kill $(lsof -ti :5173)`
- Backend: `kill $(lsof -ti :8888)`
- Bot API: `kill $(lsof -ti :8889)`

## Notes

- The Go backend in `backend/` is active and should not be documented as legacy.
- Trading-sensitive Python changes should follow `.github/copilot-instructions.md` and `bot/.github/copilot-instructions.md`.
