# AGENTS.md

## Big Picture (Read This First)
- Backend is a layered Gin API: route registration in `cmd/server/main.go`, handlers in `internal/handlers`, business logic in `internal/services`, SQL in `internal/repository`.
- Route wiring is manual dependency injection per feature (example: `internal/routes/key_routes.go` builds repo -> service -> handler).
- Main runtime flow is: Gin middleware -> handler -> service -> repository -> SQL DB; most protected endpoints use `middleware.RequireAuth()`.
- This backend also acts as a proxy to a Python bot API (`BOT_API_URL`, default `http://127.0.0.1:8889`) for backtests/bot runtime endpoints via `internal/routes/bot_api_delegate_routes.go`.

## Critical Runtime Behavior
- `cmd/server/main.go` loads `.env` from repo-root candidates, then `config.LoadConfig()`, then starts DB with `AutoMigrate: true` using `config.Database.MigrationsPath()`.
- DB driver normalization matters: `postgresql` is normalized to `postgres` before `db.New(...)`.
- Health endpoint `/health` checks both local DB health and upstream bot API reachability.
- Middleware order in `main.go` is intentional: error handling -> CORS -> header logging -> request logging -> rate limit.

## Auth and Security Conventions
- Auth middleware (`internal/middleware/auth_middleware.go`) accepts token from `Authorization`, then cookie fallback (`access_token`/`token`/`jwt`), then `access_token` query param.
- `RequireAuth()` injects `user_id`, `username`, `email`, `is_admin` into Gin context; handlers expect these exact keys.
- Login/refresh routes in `internal/routes/auth_routes.go` issue JWTs and also set HttpOnly cookies.
- dYdX key secrets are encrypted with AES-256-GCM in `internal/services/key_service.go` using `ENCRYPTION_KEY` (padded/truncated to 32 bytes).

## Database and Migrations
- Dual DB support is real: SQLite for local (`DB_TYPE=sqlite3`) and Postgres for production (`DB_TYPE=postgres`/`postgresql`).
- Migration trees are split by engine: `migrations/sqlite` and `migrations/postgres`; selection is in `config/config.go` (`MigrationsPath()`).
- `internal/db/db.go` wraps connection retries, pool settings, query timeouts, and migration recovery for dirty/already-exists states.
- Repo code currently uses raw `*sql.DB` in many places (for example `repository.NewKeyRepository(database.DB)`), so preserve existing style within a feature unless refactoring broadly.

## Bot API Delegation Pattern
- Delegated HTTP+WS endpoints live in `internal/routes/bot_api_delegate_routes.go`; request-scoped token forwarding uses `apiClient.WithToken(...)`.
- `BOT_API_USE_SERVICE_TOKEN=true` with `BOT_API_TOKEN` disables user-JWT forwarding and forces service-token auth upstream.
- WebSocket proxy behavior is bi-directional relay (backend upgrades client WS, dials upstream WS, forwards both directions).
- Keep frontend compatibility routes intact, especially `/api/v1/backtests/run` and `/ws/strategies`.

## Developer Workflows That Matter
- Cross-platform task runners exist: `Makefile` (Unix-like) and `make.ps1` (Windows). Prefer `make.ps1` on this repo's Windows setup.
- First-time local setup on Windows is streamlined with `./make.ps1 first-run -Mode development` (creates `.env`, runs doctor checks, downloads modules).
- Core verification command is `./make.ps1 test` (or `go test -v -race -coverprofile=coverage.out ./...`).
- Useful integration confidence tests: `internal/routes/bot_api_delegate_routes_smoke_test.go` and `internal/routes/settings_integration_test.go`.

## Project-Specific Implementation Patterns
- JSON response shapes are feature-specific (not globally uniform); mirror existing handler response envelopes in the same domain file.
- Time values in API output are typically RFC3339-formatted (`time.RFC3339`), often using UTC.
- Models are centralized in `internal/models/models.go` with both `db` and `json` tags; nullable DB fields use pointers or `sql.NullString`.
- Route grouping convention is `/api/v1/...`; protected groups apply `RequireAuth()` at group level, then define sub-routes.

