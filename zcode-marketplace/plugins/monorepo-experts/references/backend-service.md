# Service Profile — backend/ (Go API gateway)

Read before any change under `backend/`.

## Scope and responsibility

Gin HTTP gateway (:8888) for the frontend: authn/authz (JWT + sessions +
MFA), tenancy and quotas, backtest delegation/normalization, bot-instance
lifecycle delegation, platform settings, CRM/portal surfaces. Owns
platform PostgreSQL schema.

## Stack

Go 1.27, Gin, database/sql + PostgreSQL (placeholder rewrite via
`internal/repository/schema_cache.go`), golangci-lint v2 config.

## Entry points

- `backend/cmd/server/main.go` (bootstrap: config, DB, migrations context, auth middleware, password-change gate lookup)
- Routes: `internal/app/router.go` + `internal/routes/*` (delegation concentrated in `bot_api_delegate_routes.go`)

## Important files

- `internal/routes/auth_routes.go` — login/MFA/logout/refresh (generation-based revocation)
- `internal/middleware/` — auth, MFA step-up, password-change gate, rate limits, redaction
- `internal/services/bot_api_client*.go` — upstream transport (timeouts, 16 MiB caps, 502/504 classification)
- `internal/services/mfa_service.go` — TOTP window-burn + backup codes + attempt bounding
- `internal/services/secret_crypto.go`, `key_service.go` — encrypted secrets, salted hashes
- `migrations/postgres/NNN_*.sql` — numbered SQL migrations (deployment-driven)

## Dependencies and interfaces

- Inbound: frontend (browser) on :8888; WS proxies under `/ws/*`.
- Outbound: bot API :8889 (service-token or user token), PostgreSQL, Redis (sessions in prod).
- Public contract surface: `/api/v1/*` JSON envelopes; ownership middleware
  on instance-scoped routes; admin variants under `/api/v1/admin/*`.

## Local development and validation

```
cd backend
go build ./... && go vet ./...
go test -race -count=1 ./...
golangci-lint run ./...     # config v2; ~2.1k findings, reporting-only today
```

CI also runs `go vet -tags integration ./internal/routes/`.

## Testing strategy

Table-driven unit tests + sqlite-backed route tests (modernc.org/sqlite) +
pg-critical-path harness behind `POSTGRES_TEST_DSN`. Tests pin security
semantics (ownership 404s, quota 429s, MFA flows) — treat them as contracts.

## Deployment

`make build` (backend/Makefile) -> image via root `make images-build`.
Migrations are explicit: never rely on startup schema changes; create with
root `make create-migration MSG=...` where applicable and keep
up/down pairs symmetric.

## Security and reliability concerns

- Auth tests are load-bearing; do not relax gates (password-change gate,
  MFA step-up on secrets, ownership fail-closed for user_id=0 rows,
  quick-deploy quota + attribution).
- Error responses must stay generic for internal failures (details logged).
- Placeholder credentials rejected for every non-dev environment label
  (`internal/startup/security_baseline.go`).
- Seeded accounts (admin/user/officer/ib) carry repo-known passwords until
  rotated; `password_change_required` is enforced server-side.

## Generated/protected files

`coverage.out`, vendor-free module cache, `migrations/postgres/*.sql`
(hand-authored but deployment-executed — never destructive without a plan).

## Common failure modes

Forgetting `working-directory` semantics when moving route files; sqlite/pg
SQL dialect drift in tests (placeholder rewrite handles `?` -> `$n`);
reintroducing raw `err.Error()` into client responses; adding broad CORS or
wildcard origins in non-dev environments.

## Cross-service coordination

Delegated bot contracts: keep `normalizeBacktestRunStatus` and envelope
aliases stable or coordinate bot+frontend changes in the same set. WS proxy
paths mirror bot channels one-to-one.

## Evidence sources

`backend/README.md`, `backend/AGENTS.md`, `backend/Makefile`, `go.mod`,
`internal/routes/*_test.go`, `cmd/server/main.go`.
