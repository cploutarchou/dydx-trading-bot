# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
- `make doctor` - Validate Go toolchain (rejects `/snap/bin/go`) and print runtime dependency hints
- `make dev` - Run with hot-reload using `air`
- `make run` - Run directly without hot-reload
- `make build` - Build binary to `bin/dydx-bot`

### Testing & Verification
- `make test` - Run all tests with race detection and coverage
- `make verify` - Full pipeline: fmt, vet, lint, test
- `make lint` - Run golangci-lint (uses `.golangci.release.yml`)
- `make lint-full` - Run with `.golangci.yml` (legacy backlog profile)
- `make lint-fix` - Auto-fix lint issues

### Database Migrations
- `make migrate-create NAME=description` - Create new migration in `migrations/postgres`
- `make migrate-up` - Apply pending migrations
- `make migrate-down` - Rollback last migration
- `make migrate-status` - Show current migration version

### Tooling
- `make install-tools` - Install golangci-lint, air, golang-migrate, mockgen

## Architecture

This is a **layered Go REST API** using explicit dependency injection per feature. The backend is the only service the frontend talks to directly.

### Layer Structure
```
cmd/server/main.go (entry point)
    ↓
internal/routes/ (route registration with manual DI: repo → service → handler)
    ↓
internal/handlers/ (HTTP request/response)
    ↓
internal/services/ (business logic, encryption)
    ↓
internal/repository/ (database operations)
    ↓
PostgreSQL
```

### Key Packages
- `cmd/server` - Service entry point with middleware chain
- `config` - Environment/config loading (env vars + `run.json` + `config/profiles/{environment}.config(.enc).json`)
- `internal/routes` - Route registration; pattern is manual DI per feature
- `internal/handlers` - Request handling
- `internal/services` - Business logic and bot delegation
- `internal/repository` - Persistence layer
- `internal/middleware` - Auth, tracing, CORS, logging, rate limiting
- `internal/auth` - JWT/session helpers (`session_store.go`)
- `internal/models` - Shared models with `db` and `json` tags
- `internal/startup` - Startup validation (DB ownership, security, encryption)
- `internal/db` - Connection pooling, retries, migration recovery
- `migrations/postgres` - Runtime migration source of truth

## Bot API Delegation

The backend proxies to a Python bot API (`BOT_API_URL`, default `http://127.0.0.1:8889`) for:
- Backtest runtime endpoints
- Bot control flows
- WebSocket proxying (`/ws/strategies`)

**Delegation patterns:**
- `internal/routes/bot_api_delegate_routes.go` - HTTP+WS delegation with request-scoped token forwarding
- `BOT_API_USE_SERVICE_TOKEN=true` + `BOT_API_TOKEN` disables user-JWT forwarding
- Backtest reads/writes sync to local SQL via `BacktestSyncService`
- Frontend sees `/api/v1/backtests/*` as backend-owned routes

**Key delegated routes:**
- `/api/v1/backtests/run` - backtest creation with per-user admission limits
- `/api/v1/backtests/:run_id/*` - status, trades, progress (DB-backed via sync)
- `/ws/strategies` - bi-directional WebSocket relay

## Auth & Security

**Auth flow:**
1. Login routes (`internal/routes/auth_routes.go`) create opaque auth sessions in `internal/auth/session_store.go`
2. Sets HttpOnly `dydx_session` cookie as primary browser contract
3. Legacy JWT tokens returned only when `AUTH_RETURN_LEGACY_TOKENS=true` or `APP_ENV=test`

**Middleware chain (`main.go`):**
```
trace → error handling → CORS → header logging → request logging → rate limit
```

**Protected routes:**
- `RequireAuth()` - Extracts `user_id`, `username`, `email`, `is_admin`, `role` into Gin context
- `RequireMFA(database)` - Privileged MFA for portal/admin routes (role-aware, controlled by `platform.require_privileged_mfa`)
- `RequirePermission(database, ...)` - RBAC permissions (`users.read`, `roles.manage`, `crm.admin.manage`, etc.)

**Key encryption:**
- dYdX key secrets: AES-256-GCM in `services/key_service.go` using `ENCRYPTION_KEY`

## Portal Namespaces & RBAC

Separate React portals use first-class API namespaces:

- **Backoffice/CRM**: `/api/v1/backoffice/*` - Requires auth, privileged MFA, RBAC permissions
- **IB Portal**: `/api/v1/ib/*` - Requires `ib`, `sub_ib`, or backoffice/admin role
- **Partner/client**: `/api/v1/portal/*`
- **Legacy CRM compatibility**: `/api/v1/admin/crm/*`

**Core Backoffice endpoints:**
- User management: `GET|POST /api/v1/backoffice/users`, `GET|PUT /api/v1/backoffice/users/:id`
- Role/permissions: `POST /api/v1/backoffice/roles`, `PUT /api/v1/backoffice/roles/:role/permissions`
- CRM: `GET /api/v1/backoffice/crm/*` (clients, hierarchy, security-events, commission-metrics)
- Settings: `GET|PUT /api/v1/backoffice/settings`, `GET|PUT /api/v1/backoffice/registration-policy`

## Database

- **PostgreSQL-only** runtime database
- Migrations in `migrations/postgres` are source of truth
- Startup uses `AutoMigrate: autoMigrateEnabled()` (controlled by `DB_AUTO_MIGRATE`)
- Connection retries, pool settings, query timeouts in `internal/db/db.go`
- Repo code uses `*sql.DB` directly (preserve existing style within a feature)
- Migration naming: `000XXX_description.{up,down}.sql`

**DB ownership validation:**
- `startup.ValidateDatabaseOwnership` enforces backend-vs-bot ownership separation
- Uses `BOT_DB_CUTOVER_MODE`, `BOT_DATABASE_URL`, `BOT_DB_*` envs

## Health & Readiness

- `GET /health` - Local DB health + upstream bot API reachability
- `GET /ready` - Stricter: blocks on DB ownership violations, local DB health, upstream bot `/ready`
- `/metrics` - Local DB stats + proxied bot metrics

## Environment Variables

**Database:** `DATABASE_URL` first, then `DB_*` / `POSTGRES_*`
**Cache:** `REDIS_URL` / `VALKEY_URL`, or `REDIS_*` / `VALKEY_*`
**NATS (optional):** `NATS_URL=nats://localhost:4222`, monitoring `NATS_MONITORING_URL=http://localhost:8222`
**Bot API:** `BOT_API_URL` (default `http://127.0.0.1:8889`)

## Development Notes

- Route wiring is manual dependency injection per feature (see `internal/routes/key_routes.go` for pattern)
- JSON response shapes are feature-specific; mirror existing envelopes in the same domain
- Time values in API output are typically RFC3339-formatted (`time.RFC3339`)
- Nullable DB fields use pointers or `sql.NullString`
- `models.NormalizeUserRole(...)` normalizes user-role handling
- Session auth is now primary browser contract; JWT is opt-in compatibility

## Important Implementation Details

1. **File-backed env loading**: `main.go` loads `_FILE`-backed env values via `config.LoadFileEnvValues(true)` before structured config
2. **Bootstrap admin**: `startup.EnsureBootstrapAdmin(conn)` runs after DB init for initial admin provisioning
3. **Coming Soon mode**: Persisted in `bot_settings` as `platform.coming_soon_enabled`; public read via `GET /api/v1/public/app-config`
4. **Migration posture**: Assume transaction-safe SQL; avoid patterns requiring non-transactional `CONCURRENTLY` operations
5. **Middleware order**: Intentional - modify with care
6. **Contract-locked delegated routes**: Backtest routes normalize to `{ success, message, data, timestamp }` envelope
