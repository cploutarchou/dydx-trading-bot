# Restructure Report

Date: 2026-05-28

## Executive Summary

This repository is a multi-service monorepo with a strict integration boundary:

`frontend -> backend -> bot`

Detected services:

| Service | Stack | Pattern Detected | Status |
| --- | --- | --- | --- |
| `frontend/` | React 19, TypeScript, Vite, TanStack Query, Zustand, Tailwind | Multi-portal frontend inside one Vite app, with shared packages and route manifests | Mostly well-structured; shared packages are currently thin re-export facades into `src/` |
| `backend/` | Go, Gin, PostgreSQL, golang-migrate | Layered Go service: `cmd/`, `config/`, `internal/{routes,handlers,services,repository,models}` | Already close to standard Go layout |
| `bot/` | Python, FastAPI, SQLAlchemy, Alembic, Celery, dYdX client | Layered/domain runtime: `api`, `infrastructure`, `trading`, `shared`, worker entrypoints | Mostly structured; a few compatibility wrappers and diagnostics remain at service root |
| root/platform | Make, Dockerfiles, StackForge config, encrypted profile config | Monorepo orchestration and deployment | Intentionally centralized |

Actual structural changes applied:

- Moved `bot/test_comprehensive.py` to `bot/tests/test_comprehensive.py`.
- Updated `bot/tasks.md` references for the moved test file.
- Added root `.env.example` as the conventional dotenv example path while preserving existing `env.example`.

No business logic, function signatures, API routes, database schemas, migrations, or seed files were changed.

## Directory Tree

The full source tree was printed with generated/vendor/runtime artifacts excluded:

```text
.
|-- .github/
|-- backend/
|-- bot/
|-- config/
|-- docker/
|-- docs/
|-- frontend/
|-- platform/
|-- scripts/
|-- AGENTS.md
|-- Makefile
|-- README.md
|-- env.example
`-- stackforge-deployment.yaml
```

Ignored local artifacts observed and intentionally not moved or committed:

- `.env`, `.env.stackforge`, service-local `.env` files
- `.configkey.bin`
- `config/profiles/development.config.json`
- `frontend/node_modules/`, `frontend/dist/`
- `bot/.venv/`, bot state JSON/log/lock files
- backend coverage/build outputs

## Before/After Tree

### Bot Before

```text
bot/
|-- app.py
|-- main.py
|-- start_api.py
|-- worker_entrypoint.py
|-- test_comprehensive.py
|-- tmp_test_auth.py
|-- check_validation.py
|-- config/
|-- migrations/
|-- scripts/
|-- src/
`-- tests/
```

### Bot After

```text
bot/
|-- app.py
|-- main.py
|-- start_api.py
|-- worker_entrypoint.py
|-- tmp_test_auth.py
|-- check_validation.py
|-- config/
|-- migrations/
|-- scripts/
|-- src/
`-- tests/
    `-- test_comprehensive.py
```

Compatibility wrappers stayed in place because repository guidance explicitly says to preserve `app.py`, `start_api.py`, `main.py`, and worker entrypoints.

### Backend Before/After

No file moves were applied. The backend already follows the expected Go service layout:

```text
backend/
|-- cmd/server/
|-- config/
|-- internal/
|   |-- app/
|   |-- auth/
|   |-- db/
|   |-- handlers/
|   |-- middleware/
|   |-- models/
|   |-- repository/
|   |-- routes/
|   |-- services/
|   `-- startup/
|-- migrations/postgres/
|-- scripts/
|-- go.mod
`-- Makefile
```

### Frontend Before/After

No file moves were applied. The frontend already has a recognizable Vite/React layout:

```text
frontend/
|-- apps/
|   |-- backoffice/
|   |-- client-portal/
|   `-- ib-portal/
|-- packages/
|   |-- shared-api/
|   |-- shared-auth/
|   |-- shared-types/
|   `-- shared-ui/
|-- public/
|-- scripts/
|-- src/
|   |-- api/
|   |-- app/
|   |-- auth/
|   |-- components/
|   |-- features/
|   |-- hooks/
|   |-- navigation/
|   |-- pages/
|   |-- store/
|   `-- utils/
|-- package.json
|-- tsconfig.json
`-- vite.config.ts
```

## Service Analysis

### Backend

Strengths:

- Standard Go ownership boundaries are present: `cmd/`, `config/`, `internal/`, `migrations/`.
- Layering is mostly explicit: routes register HTTP paths, handlers shape HTTP IO, services hold business logic, repositories own persistence.
- Tests live beside packages, matching normal Go conventions.
- `go list ./...` resolves all backend packages, which also rules out Go import cycles.

Warnings:

- `internal/routes` imports repositories and services directly in many route files. This is acceptable in the current dependency-injection style but keeps route wiring tightly coupled to concrete packages.
- `internal/models/models.go` is a large shared model surface. Over time, feature-specific model files or package-level DTOs would reduce cross-feature coupling.
- `go.mod` still contains `modernc.org/sqlite` while repository instructions say runtime database support is PostgreSQL-only. This may be a stale test/tool dependency and should be reviewed before removal.

Recommended target layout:

```text
backend/
|-- cmd/server/
|-- api/openapi/
|-- config/
|-- internal/
|   |-- app/
|   |-- platform/
|   |   |-- auth/
|   |   |-- db/
|   |   `-- middleware/
|   |-- modules/
|   |   |-- backtests/
|   |   |   |-- handler.go
|   |   |   |-- routes.go
|   |   |   |-- service.go
|   |   |   `-- repository.go
|   |   |-- bots/
|   |   |-- settings/
|   |   `-- portal/
|   `-- startup/
|-- migrations/postgres/
|-- scripts/
`-- tests/
```

This is a future migration proposal only. Moving to package-by-feature would be a broad import rewrite and should be done in feature-sized commits with contract tests.

### Bot

Strengths:

- FastAPI assembly is centralized in `src/api/server.py`.
- Trading runtime code is separated under `src/trading/`.
- Infrastructure, persistence, use cases, workers, and shared utilities have explicit directories.
- Tests are already concentrated in `bot/tests/`; the misplaced comprehensive test was moved there.

Warnings:

- Imports mix `src.*` and `internal.*` namespaces. Example areas: `src/api/websocket_server.py`, `src/bot_instance_manager.py`, persistence repositories, and tests. This increases coupling and makes package ownership harder to reason about.
- `bot/tmp_test_auth.py` and `bot/check_validation.py` are root-level diagnostic scripts. They were not moved because their runtime expectations and operator usage are not documented.
- Root wrappers (`app.py`, `start_api.py`, `main.py`, `worker_entrypoint.py`) look like cleanup candidates but are documented compatibility entrypoints and are used by Docker, Makefile, scripts, and docs.

Recommended target layout:

```text
bot/
|-- config/
|-- migrations/
|-- scripts/
|   |-- diagnostics/
|   `-- operations/
|-- src/
|   |-- api/
|   |   |-- routers/
|   |   |-- schemas/
|   |   `-- server.py
|   |-- domain/
|   |-- infrastructure/
|   |   |-- database.py
|   |   |-- persistence/
|   |   `-- workers/
|   |-- services/
|   |-- shared/
|   `-- trading/
`-- tests/
```

The safe next step is not a bulk move. First consolidate `internal.domain` and `src.infrastructure.domain` into one domain namespace, then update imports with targeted tests.

### Frontend

Strengths:

- Portal shells are separated in `apps/`.
- Shared source has clear API, app routing, auth, components, features, pages, store, and utils folders.
- Dedicated CRM, IB, and client page folders are present.
- `npm run typecheck` completed successfully.

Warnings:

- `frontend/packages/*` currently re-export from `frontend/src` using deep relative paths. This makes the packages facades rather than independent shared libraries.
- Some feature-specific components still sit in the broad `src/components/` folder. Examples include backtest, strategy, bot, AI, Telegram, and settings components.
- API access is intentionally mixed today: React Query hooks exist, but several screens still use direct polling/fetch flows. This is documented in repo instructions and should not be mass-changed during restructuring.

Recommended target layout:

```text
frontend/
|-- apps/
|-- packages/
|   |-- shared-api/
|   |-- shared-auth/
|   |-- shared-types/
|   `-- shared-ui/
|-- src/
|   |-- app/
|   |-- features/
|   |   |-- backtests/
|   |   |   |-- api/
|   |   |   |-- components/
|   |   |   |-- pages/
|   |   |   `-- model/
|   |   |-- bots/
|   |   |-- strategies/
|   |   |-- settings/
|   |   |-- crm/
|   |   `-- ib/
|   |-- shared/
|   |   |-- api/
|   |   |-- components/
|   |   |-- hooks/
|   |   `-- utils/
|   `-- main.tsx
`-- tests/
```

The safe next step is to extract one feature at a time, starting with low-risk pure UI components, while preserving route manifest ownership and backend-only API access.

### Root, Config, And Infrastructure

Strengths:

- Root `Makefile`, `config/`, `docker/`, `docs/`, `platform/`, and `scripts/` make monorepo operations discoverable.
- Encrypted profiles under `config/profiles/*.config.enc.json` remain the documented source of truth.
- Dockerfiles are centralized under `docker/`, matching the current deployment flow.

Warnings:

- Root scripts are a mix of bot operations, config rendering, testing helpers, and deployment helpers. This is workable but should eventually split into `scripts/config/`, `scripts/deploy/`, `scripts/bot/`, and `scripts/test/`.
- `.env.stackforge` is ignored and local-only. Keep it that way because it contains deployment secret placeholders.
- A root `env.example` existed but the conventional `.env.example` path was missing; this report added `.env.example` without removing `env.example`.

Recommended target layout:

```text
.
|-- config/
|-- deploy/
|-- docker/
|-- docs/
|-- platform/
|-- scripts/
|   |-- bot/
|   |-- config/
|   |-- deploy/
|   `-- test/
|-- backend/
|-- bot/
`-- frontend/
```

## Circular Dependency And Coupling Notes

- Backend: `go list ./...` passed, so no Go import cycles were detected.
- Bot: Python compilation passed for `src`, `config`, and `tests`. Static import review found tight coupling between API/websocket modules and trading/realtime services, plus mixed `src.*` and `internal.*` imports.
- Frontend: TypeScript type checking passed. Static import review found deep relative re-exports from `packages/*` into `src/*`, which is a coupling risk if those packages are intended to be independently consumable.

## Validation

Completed:

- `python3 -m compileall -q src config tests` from `bot/`
- `go list ./...` from `backend/`
- `go test ./...` from `backend/`
- `npm run typecheck` from `frontend/`
- `npm run build` from `frontend/`

Blocked or incomplete:

- `bot/.venv/bin/python -m pytest tests/test_comprehensive.py -q` produced no output for several minutes and was stopped. The moved file compiles successfully, but this targeted pytest needs follow-up because importing `src.api.server` may trigger slow API startup behavior in this environment.

## Manual Review Items

1. Decide whether `bot/tmp_test_auth.py` should become `bot/scripts/diagnostics/create_test_auth_token.py`.
2. Decide whether `bot/check_validation.py` should move under `bot/scripts/diagnostics/`.
3. Decide whether root Python scripts should be grouped under `scripts/bot/`, `scripts/config/`, `scripts/deploy/`, and `scripts/test/`.
4. Review whether backend `modernc.org/sqlite` is still required.
5. Plan frontend package extraction only if `frontend/packages/*` are meant to be real standalone libraries instead of local facades.
6. Avoid moving documented bot wrappers until Docker, Makefile, scripts, docs, and operator workflows are updated together.
