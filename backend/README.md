# Backend Service

The backend is the public application API for the platform. It is the only service the frontend should talk to directly.

## Responsibilities

- authenticate and authorize frontend traffic
- expose the stable app-facing HTTP contract
- proxy and normalize bot HTTP and websocket traffic
- persist app-owned state in backend PostgreSQL
- coordinate strategy, bot, and backtest control flows

## Entry Point

- [cmd/server/main.go](/home/chris/workspace/dydx-trading-bot/backend/cmd/server/main.go)

## Local Runtime

- default port: `8888`
- database: backend PostgreSQL on `5432`
- upstream bot API: `BOT_API_URL` or default `http://127.0.0.1:8889`

## Key Packages

- `internal/routes` for HTTP route registration
- `internal/handlers` for request handling
- `internal/services` for orchestration and bot delegation
- `internal/repository` for persistence
- `internal/middleware` for auth, tracing, CORS, and logging

## Core Commands

```bash
make run
make dev
make test
make lint
make verify
```

## Contract Rules

- the frontend consumes backend routes only
- backend owns the frontend-facing response shape
- delegated bot responses may be normalized before reaching the frontend
- websocket proxying must preserve auth and trace propagation

## Health and Validation

- liveness: `GET /health`
- readiness: `GET /ready`
- tests: `make test`

## Related Docs

- [Root README](/home/chris/workspace/dydx-trading-bot/README.md)
- [Platform Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
- [Platform Overview](/home/chris/workspace/dydx-trading-bot/docs/PLATFORM.md)
