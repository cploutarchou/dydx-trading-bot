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

## Current Structure

- `frontend/`: React/Vite workspace with portal app shells in `apps/`, shared implementation in `src/`, and shared package exports in `packages/`.
- `backend/`: Go API service with route registration in `internal/routes`, business logic in `internal/services`, persistence in `internal/repository`, and migrations in `migrations/postgres`.
- `bot/`: Python FastAPI and trading runtime with API code in `src/api`, lifecycle/runtime code in `src/bot_instance_manager.py` and `src/main_instance.py`, and runtime state/log artifacts under `bot_states/`.
- `config/`: encrypted profile source for generated root `run.json`.
- `docker/`, `platform/`, and `deploy/`: service images, platform registry data, and rendered deployment output.
- `scripts/`: repo-level config, validation, operations, and backtest helpers.

## Documentation Rules

- Treat the root [README.md](/home/chris/workspace/dydx-trading-bot/README.md) as the fast entry point.
- Treat each service `README.md` as the canonical service contract and operator guide.
- Use specialized docs only when they add value beyond the service README.
- When behavior changes, update the relevant service README and any affected page in this wiki in the same change.
- Follow the [Documentation Governance Policy](DOCUMENTATION_GOVERNANCE.md) checklist for behavior-changing PRs.
- Run `python3 scripts/validate_docs_governance.py` before push when docs or contracts change.
- Archive temporary handoff/task docs under `docs/archive/` using date-prefixed names.

## Scope

This wiki documents:

- how the platform is structured
- how local development works
- how the services communicate
- how operators start, monitor, and troubleshoot the stack

It intentionally does not duplicate low-level API schemas that already live in source code and generated artifacts such as `openapi.json`.
