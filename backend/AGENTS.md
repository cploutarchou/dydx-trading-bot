# AGENTS.md

## Big Picture (Read This First)

- Backend is a layered Gin API: route registration in `cmd/server/main.go`, handlers in `internal/handlers`, business logic in `internal/services`, SQL in `internal/repository`.
- Route wiring is manual dependency injection per feature (example: `internal/routes/key_routes.go` builds repo -> service -> handler).
- Main runtime flow is: Gin middleware -> handler -> service -> repository -> SQL DB; most protected endpoints use `middleware.RequireAuth()`.
- This backend also acts as a proxy to a Python bot API (`BOT_API_URL`, default `http://127.0.0.1:8889`) for backtests/bot runtime endpoints via `internal/routes/bot_api_delegate_routes.go`.

## Start-of-task checklist

1. Read `../.github/copilot-instructions.md`
2. Read `.github/copilot-instructions.md`
3. Read `.github/CUSTOMIZATION_INDEX.md`
4. Prefer `.github/agents/senior-go-defi-backend.agent.md` for backend implementation work

## Critical Runtime Behavior

- `cmd/server/main.go` loads `_FILE`-backed env values via `config.LoadFileEnvValues(true)`, auto-loads structured runtime config from repo-root `run.json` or `config/profiles/{environment}.config(.enc).json`, then re-applies `_FILE` env loading before `config.LoadConfig()`.
- Startup validates DB ownership and security/encryption guardrails (`startup.ValidateDatabaseOwnership`, `startup.ValidateSecurityBaseline`, `services.ValidateEncryptionKeyConfiguration`) before opening request traffic.
- Database startup uses `AutoMigrate: autoMigrateEnabled()` (controlled by `DB_AUTO_MIGRATE`) with `config.Database.MigrationsPath()`; do not assume migrations run automatically unless explicitly enabled.
- After DB init, startup runs `startup.EnsureBootstrapAdmin(conn)` to idempotently provision bootstrap admin access.
- The backend runtime supports PostgreSQL (`postgres`/`postgresql`) only.
- Health endpoint `/health` checks both local DB health and upstream bot API reachability.
- Readiness endpoint `/ready` is stricter than `/health`: it blocks on DB ownership violations, local DB health, and upstream bot `/ready`; `/metrics` exposes local DB stats plus proxied bot metrics.
- Startup and readiness both enforce backend-vs-bot database ownership via `internal/startup/db_ownership.go` using `BOT_DB_CUTOVER_MODE`, `BOT_DATABASE_URL`, and `BOT_DB_*` envs.
- Middleware order in `main.go` is intentional: trace -> error handling -> CORS -> header logging -> request logging -> rate limit.

## Auth and Security Conventions

- Auth middleware (`internal/middleware/auth_middleware.go`) accepts token from `Authorization`, then cookie fallback (`access_token`/`token`/`jwt`), then `access_token` query param.
- `RequireAuth()` injects `user_id`, `username`, `email`, `is_admin`, and `role` into Gin context; session-backed requests also set `session_expires_at`.
- Login/refresh routes in `internal/routes/auth_routes.go` are session-first: they create/refresh opaque auth sessions in `internal/auth/session_store.go` and set the HttpOnly `dydx_session` cookie. Legacy JWT access/refresh tokens are only returned when `AUTH_RETURN_LEGACY_TOKENS=true` (or `APP_ENV=test`).
- Privileged portal/admin routes typically layer `RequireAuth()` -> `RequireMFA(database)` -> `RequirePermission(database, ...)`; MFA enforcement is role-aware and controlled by platform setting `platform.require_privileged_mfa` with production-default fallback.
- dYdX key secrets are encrypted with AES-256-GCM in `internal/services/key_service.go` using `ENCRYPTION_KEY` (padded/truncated to 32 bytes).

## Database and Migrations

- PostgreSQL is the supported SQL database for local and production use.
- Backend migrations run from `migrations/postgres`.
- `internal/db/db.go` wraps connection retries, pool settings, query timeouts, and migration recovery for dirty/already-exists states.
- Repo code currently uses raw `*sql.DB` in many places (for example `repository.NewKeyRepository(database.DB)`), so preserve existing style within a feature unless refactoring broadly.

## Bot API Delegation Pattern

- Delegated HTTP+WS endpoints live in `internal/routes/bot_api_delegate_routes.go`; request-scoped token forwarding uses `apiClient.WithToken(...)`.
- `BOT_API_USE_SERVICE_TOKEN=true` with `BOT_API_TOKEN` disables user-JWT forwarding and forces service-token auth upstream.
- WebSocket proxy behavior is bi-directional relay (backend upgrades client WS, dials upstream WS, forwards both directions).
- Keep frontend compatibility routes intact, especially `/api/v1/backtests/run` and `/ws/strategies`.
- `RegisterBotAPIDelegateRoutesWithSync(...)` wires delegated backtest reads/writes through `BacktestSyncService`, so detail/status/trade fetches can hydrate local SQL state while the frontend still talks to backend-owned routes.
- Delegated backtest creation enforces per-user active-run admission limits from `users.max_active_backtests` (fallback envs `BACKTEST_MAX_ACTIVE_RUNS_PER_USER` / `BACKEND_BACKTEST_MAX_ACTIVE_RUNS_PER_USER`) and exposes local sync diagnostics like `GET /api/v1/backtests/sync-health` and `POST /api/v1/backtests/:run_id/resync`.

## Developer Workflows That Matter

- Use the Unix-like `Makefile` targets in `backend/` for local development on macOS/Linux.
- Run `make doctor` early when setting up/debugging local dev: it validates Go toolchain requirements (including the unsupported `/snap/bin/go` case) and prints required runtime dependency/env hints.
- First-time local setup: `make install-tools` and `make deps`; `make dev-env` is deprecated because the backend now reads structured config profiles directly.
- Core verification command is `make verify`; use `make test` (or `go test -v -race -coverprofile=coverage.out ./...`) for focused backend confidence.
- Useful integration confidence tests: `internal/routes/bot_api_delegate_routes_smoke_test.go`, `internal/routes/contract_lock_integration_test.go`, `internal/routes/bot_instance_contract_lock_test.go`, and `internal/routes/settings_integration_test.go`.

## Project-Specific Implementation Patterns

- JSON response shapes are feature-specific (not globally uniform); mirror existing handler response envelopes in the same domain file.
- Delegated/non-stream backtest routes are contract-locked to `{ success, message, data, timestamp }`; keep legacy compatibility aliases (for example top-level `error` on delegated upstream failures) where existing routes already expose them.
- Time values in API output are typically RFC3339-formatted (`time.RFC3339`), often using UTC.
- Models are centralized in `internal/models/models.go` with both `db` and `json` tags; nullable DB fields use pointers or `sql.NullString`.
- Route grouping convention is `/api/v1/...`; protected groups apply `RequireAuth()` at group level, then define sub-routes.
- Portal-facing APIs now use several first-class namespaces with shared handler logic: `/api/v1/backoffice/*`, `/api/v1/admin/*`, `/api/v1/admin/crm/*`, `/api/v1/admin/ib/*`, `/api/v1/portal/*`, and `/api/v1/ib/*`.
- RBAC/user-role handling is normalized through `models.NormalizeUserRole(...)`; built-in roles live in `internal/models/user_utils.go`, while custom assignable roles come from RBAC tables and admin routes.

## Latest backend context (2026-05)

- Backtest list endpoint (`GET /api/v1/backtests`) is DB-backed through `BacktestRepository.GetRunsByUserID` and `CountRunsByUserID`.
- Delegated status/progress normalization is centralized in `internal/routes/bot_api_delegate_routes.go` (`normalizeBacktest*` helpers).
- Migration posture expects transaction-safe SQL in startup migration flow; avoid statements that require non-transaction execution.
- Session auth is now the primary browser contract (`dydx_session` cookie + session store); keep JWT compatibility behavior opt-in and do not assume bearer tokens are always present.
- Backoffice/admin portal flows depend on database-backed RBAC, privileged MFA, invitation tokens, partner relationships, and commission metrics rather than dummy seed-only handlers.
- Recent index migration hardening touched PostgreSQL migration files in `migrations/postgres/`.
