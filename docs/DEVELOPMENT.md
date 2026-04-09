# Development Workflow

## Prerequisites

- Docker
- Node.js 20+
- Go 1.25+
- Python 3.12 with virtualenv support
- repo root `.configkey.bin`

## Structured Config Workflow

Generate the local runtime config from the encrypted development profile:

```bash
make config-keygen
make dev-config
make dev
```

That produces the shared `run.json` file used by the services.

## Recommended Local Modes

### Service-first mode

Use this when working on one service at a time.

```bash
make dev-infra
```

Then start only the service you are editing:

- frontend: `cd frontend && npm install && npm run dev`
- backend: `cd backend && make run`
- bot API: `cd bot && make local-api`
- bot worker: `cd bot && make local-bot`

Stop local infra with:

```bash
make dev-infra-down
```

### Full integration mode

Use this when validating cross-service behavior:

```bash
make stack-up-dev
make stack-ps
make stack-logs
```

Stop the stack with:

```bash
make stack-down
```

## Default Ports

| Component          | Port   |
| ------------------ | ------ |
| frontend           | `5173` |
| backend            | `8888` |
| bot API            | `8889` |
| backend PostgreSQL | `5432` |
| bot PostgreSQL     | `5433` |
| Redis              | `6379` |

## Verification Commands

- frontend: `cd frontend && npm run lint && npm run build`
- backend: `cd backend && make test`
- bot: `cd bot && .venv/bin/pytest`
- docs governance: `python3 scripts/validate_docs_governance.py`

## Development Rules

- frontend changes must keep traffic routed through the backend only
- backend changes must preserve the frontend-facing contract
- bot changes must preserve runtime safety and startup correctness
- documentation updates ship in the same change as behavior updates
