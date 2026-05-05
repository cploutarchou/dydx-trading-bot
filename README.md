# dYdX Trading Platform Monorepo

This repository contains the active dYdX trading platform across three runtime services and shared infrastructure.

`frontend -> backend -> bot -> exchange/runtime`

## Services

| Service     | Purpose                                                  | Default port |
| ----------- | -------------------------------------------------------- | ------------ |
| `frontend/` | public website, auth flows, operator workspace           | `5173`       |
| `backend/`  | public application API, auth, orchestration, bot proxy   | `8888`       |
| `bot/`      | Python bot API, trading runtime, backtests, live workers | `8889`       |

Supporting local infrastructure:

- backend PostgreSQL: `5432`
- bot PostgreSQL: `5433`
- Redis: `6379`

## Quick Start

### 1. Prepare runtime config

```bash
make config-keygen
make dev-config
make dev
```

### 2. Choose your local workflow

#### Service-first development (recommended for daily work)

```bash
make infra-up
make infra-ps
make infra-logs
```

Then start the service you are actively developing:

- frontend: `cd frontend && npm install && npm run dev`
- backend: `cd backend && make run`
- bot API: `cd bot && make local-api`

When finished:

- stop infra: `make infra-down`

#### Full integration stack (frontend + backend + bot + infra)

```bash
make stack-up-dev
make stack-ps
make stack-logs
```

When finished:

- stop stack: `make stack-down`

## Documentation Map

- [Platform Wiki Home](docs/README.md)
- [Platform Overview](docs/PLATFORM.md)
- [Development Workflow](docs/DEVELOPMENT.md)
- [Operations Guide](docs/OPERATIONS.md)
- [Documentation Governance](docs/DOCUMENTATION_GOVERNANCE.md)
- [Frontend Service Doc](frontend/README.md)
- [Backend Service Doc](backend/README.md)
- [Bot Service Doc](bot/README.md)
- [Shared Config Doc](config/README.md)

## Core Rules

- the frontend communicates with the backend only
- the backend owns the frontend-facing contract
- the bot owns runtime execution and exchange connectivity
- structured config in `config/profiles/` is the source of truth for local and deployed startup

## Development Notes

- use the root `Makefile` for stack workflows
- use each service `README.md` for service-specific commands and responsibilities
- treat generated artifacts such as `bot/openapi.json` as canonical contracts when detailed schema accuracy matters
- run `python3 scripts/validate_docs_governance.py` before merge for doc/contract changes
