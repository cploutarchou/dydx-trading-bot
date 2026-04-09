# dYdX Trading Platform Monorepo

This repository contains the active dYdX trading platform across three runtime services and shared infrastructure.

`frontend -> backend -> bot -> exchange/runtime`

## Services

| Service | Purpose | Default port |
| --- | --- | --- |
| `frontend/` | public website, auth flows, operator workspace | `5173` |
| `backend/` | public application API, auth, orchestration, bot proxy | `8888` |
| `bot/` | Python bot API, trading runtime, backtests, live workers | `8889` |

Supporting local infrastructure:

- backend PostgreSQL: `5432`
- bot PostgreSQL: `5433`
- Redis: `6379`

## Quick Start

### 1. Generate runtime config

```bash
make config-keygen
make dev-config
make dev
```

### 2. Start local infrastructure

```bash
make dev-infra
```

### 3. Start the service you are working on

- frontend: `cd frontend && npm install && npm run dev`
- backend: `cd backend && make run`
- bot API: `cd bot && make local-api`

## Full Integration Stack

```bash
make stack-up-dev
make stack-ps
make stack-logs
make stack-down
```

## Documentation Map

- [Platform Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
- [Platform Overview](/home/chris/workspace/dydx-trading-bot/docs/PLATFORM.md)
- [Development Workflow](/home/chris/workspace/dydx-trading-bot/docs/DEVELOPMENT.md)
- [Operations Guide](/home/chris/workspace/dydx-trading-bot/docs/OPERATIONS.md)
- [Frontend Service Doc](/home/chris/workspace/dydx-trading-bot/frontend/README.md)
- [Backend Service Doc](/home/chris/workspace/dydx-trading-bot/backend/README.md)
- [Bot Service Doc](/home/chris/workspace/dydx-trading-bot/bot/README.md)
- [Shared Config Doc](/home/chris/workspace/dydx-trading-bot/config/README.md)

## Core Rules

- the frontend communicates with the backend only
- the backend owns the frontend-facing contract
- the bot owns runtime execution and exchange connectivity
- structured config in `config/profiles/` is the source of truth for local and deployed startup

## Development Notes

- use the root `Makefile` for stack workflows
- use each service `README.md` for service-specific commands and responsibilities
- treat generated artifacts such as `bot/openapi.json` as canonical contracts when detailed schema accuracy matters
