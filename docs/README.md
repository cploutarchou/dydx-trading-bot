# Platform Documentation

This `docs/` directory is the wiki-style home for the active monorepo.

## Start Here

1. [Platform Overview](PLATFORM.md)
2. [Development Workflow](DEVELOPMENT.md)
3. [Operations Guide](OPERATIONS.md)
4. Service docs:
   - [Frontend](/home/chris/workspace/dydx-trading-bot/frontend/README.md)
   - [Backend](/home/chris/workspace/dydx-trading-bot/backend/README.md)
   - [Bot](/home/chris/workspace/dydx-trading-bot/bot/README.md)
   - [Config](/home/chris/workspace/dydx-trading-bot/config/README.md)

## Documentation Rules

- Treat the root [README.md](/home/chris/workspace/dydx-trading-bot/README.md) as the fast entry point.
- Treat each service `README.md` as the canonical service contract and operator guide.
- Use specialized docs only when they add value beyond the service README.
- When behavior changes, update the relevant service README and any affected page in this wiki in the same change.

## Scope

This wiki documents:

- how the platform is structured
- how local development works
- how the services communicate
- how operators start, monitor, and troubleshoot the stack

It intentionally does not duplicate low-level API schemas that already live in source code and generated artifacts such as `openapi.json`.
