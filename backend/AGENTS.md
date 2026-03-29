# AGENTS Guide

## Big Picture
- This backend is a layered Gin API: routes -> handlers -> services -> repositories -> SQL (`cmd/server/main.go`, `internal/routes/*`, `internal/handlers/*`, `internal/services/*`, `internal/repository/*`).
- Route registration is centralized in `cmd/server/main.go`; keep new resources registered there, not in init functions.
- Middleware order in `main.go` is significant: error handler, CORS, header/request logging, then rate limit. Follow this order for new global middleware.
- Auth context contract is stable: `RequireAuth()` sets `user_id`, `username`, `email`, `is_admin` (`internal/middleware/auth_middleware.go`). Handlers should read these keys via `c.Get`.

## Data + Infra Boundaries
- Config is env-driven via `config.LoadConfig()`; prefer adding new env vars in `config/config.go` with defaults rather than reading env directly in handlers.
- DB type switching is built-in (`DB_TYPE=sqlite3|postgresql`); DSN and migration path come from `DatabaseSettings.DSN()` and `MigrationsPath()`.
- DB startup uses `db.New(...)` with retry, pool tuning, health checks, and auto-migrate (`internal/db/db.go`).
- Migration directories are split by engine (`migrations/sqlite`, `migrations/postgres`); keep file numbers aligned and use `000XXX_name.{up,down}.sql`.
- `internal/db/db.go` contains recovery logic for dirty/non-idempotent migration states; avoid adding non-idempotent SQL unless absolutely required.

## Project-Specific Coding Patterns
- Route files assemble dependencies explicitly (repo/service/handler construction), e.g. `internal/routes/key_routes.go` and `internal/routes/settings_routes.go`.
- Services own business rules and secret handling; dYdX key encryption/decryption lives in `internal/services/key_service.go` (AES-GCM using `ENCRYPTION_KEY`).
- Repositories use SQL + model structs from `internal/models/models.go`; preserve `db` + `json` tags and nullable pointer/`sql.Null*` fields.
- Handler responses commonly use `{success,data,error,timestamp}` payloads in this repo; mirror existing shape per feature area before introducing new schemas.
- Prefer wrapping errors with context (`fmt.Errorf("...: %w", err)`) as used across services/repos.

## External Integrations
- Backtests/bot instances are delegated to an upstream Python bot API via `BotAPIClient` (`internal/services/bot_api_client*.go`) and proxy routes (`internal/routes/bot_api_delegate_routes.go`).
- Token forwarding behavior depends on env: when `BOT_API_USE_SERVICE_TOKEN=true` and `BOT_API_TOKEN` is set, upstream uses service token; otherwise request token is forwarded.
- WebSocket proxying is implemented in delegate routes (live backtest + strategy streams); keep auth propagation consistent with `extractBotAuthToken`.

## Developer Workflow (Use These First)
- Install tools once: `make install-tools` (air, golangci-lint, migrate, mockgen).
- Day-to-day: `make dev` (hot reload) or `make run`.
- Quality gate: `make verify` (fmt, vet, lint, test) before finalizing substantial changes.
- Tests: `make test` or focused `go test -v ./internal/routes -run Smoke` for delegated-route smoke tests.
- Migrations: `make migrate-up`, `make migrate-down`, `make migrate-create NAME=...`.

## Testing Patterns To Reuse
- API integration tests use `gin.TestMode`, `httptest.NewServer`, and in-memory SQLite setup (`internal/routes/bot_api_delegate_routes_smoke_test.go`).
- For authenticated route tests, initialize middleware once and generate JWTs with `auth.NewManager(...).CreateAccessToken(...)` (`internal/routes/settings_integration_test.go`).
- When adding protected endpoints, add at least one test covering missing token vs valid token behavior and claim extraction.
