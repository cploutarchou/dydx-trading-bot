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
- database: PostgreSQL on `localhost:5432` by default in local service-first mode
- supported database envs: `DATABASE_URL` first, then `DB_*` / `POSTGRES_*`
- supported cache envs: `REDIS_URL` / `VALKEY_URL`, or `REDIS_*` / `VALKEY_*`
- optional local NATS contract: `NATS_URL=nats://localhost:4222`, monitoring `NATS_MONITORING_URL=http://localhost:8222`
- upstream bot API: `BOT_API_URL` or default `http://127.0.0.1:8889`

## Key Packages

- `cmd/server` for the service entry point
- `config` for backend environment/config loading
- `internal/routes` for HTTP route registration
- `internal/handlers` for request handling
- `internal/services` for orchestration and bot delegation
- `internal/repository` for persistence
- `internal/middleware` for auth, tracing, CORS, and logging
- `internal/auth` for JWT/session auth helpers
- `migrations/postgres` for the runtime migration set

## Core Commands

```bash
make doctor
make run
make dev
make test
make lint
make verify
```

`make doctor` validates that the active Go binary is a supported install. A Go
binary under `/snap/bin` is not supported for this backend because it can fail
under sandboxed shells with `snap-confine` capability errors before tests start.

## Contract Rules

- the frontend consumes backend routes only
- backend owns the frontend-facing response shape
- delegated bot responses may be normalized before reaching the frontend
- websocket proxying must preserve auth and trace propagation

## Portal API Boundaries

The separated React portals use first-class API namespaces:

- Public bootstrap: `GET /api/v1/public/app-config`
- Client/session: `GET /api/v1/me`, `GET /api/v1/auth/session`
- Backoffice/CRM: `/api/v1/backoffice/*`
- IB Portal: `/api/v1/ib/*`
- Partner/client portal compatibility: `/api/v1/portal/*`
- Legacy CRM compatibility while older clients migrate: `/api/v1/admin/crm/*`

Backoffice routes require authentication, privileged MFA when enabled, and RBAC permissions such as `users.read`, `roles.manage`, `crm.admin.manage`, `finance.manage`, and `audit.read`. IB routes require `ib`, `sub_ib`, or a backoffice/admin role. Admin and super admin retain override access through RBAC mappings, and custom roles are supported by the RBAC tables.

Core Backoffice endpoints:

- `GET|POST /api/v1/backoffice/users`
- `GET|PUT /api/v1/backoffice/users/:id`
- `PUT /api/v1/backoffice/users/:id/role`
- `PUT /api/v1/backoffice/users/:id/status`
- `POST /api/v1/backoffice/users/:id/reset-password`
- `POST /api/v1/backoffice/users/:id/reset-mfa`
- `GET /api/v1/backoffice/access-control`
- `GET|PUT /api/v1/backoffice/registration-policy`
- `GET|PUT /api/v1/backoffice/settings`
- `POST /api/v1/backoffice/roles`
- `PUT /api/v1/backoffice/roles/:role/permissions`
- `DELETE /api/v1/backoffice/roles/:role`
- `GET /api/v1/backoffice/crm/summary`
- `GET /api/v1/backoffice/crm/clients`
- `GET /api/v1/backoffice/crm/clients/:id`
- `GET /api/v1/backoffice/crm/hierarchy`
- `GET /api/v1/backoffice/crm/security-events`
- `POST /api/v1/backoffice/crm/applications/:id/review`
- `PUT /api/v1/backoffice/crm/commission-metrics/:user_id`
- `GET /api/v1/backoffice/audit-logs`
- `GET /api/v1/backoffice/bot-api-stats`

Core IB endpoints:

- `GET /api/v1/ib/profile`
- `GET /api/v1/ib/dashboard`
- `GET|POST /api/v1/ib/sub-ibs`
- `GET|POST /api/v1/ib/clients`
- `GET|POST /api/v1/ib/invitations`
- `GET /api/v1/ib/invitations/:id`
- `POST /api/v1/ib/invitations/:id/revoke`
- `GET /api/v1/ib/referral-links`
- `GET /api/v1/ib/commissions`
- `GET /api/v1/ib/reports`
- `GET /api/v1/ib/invitations/:id/validate`

The legacy dummy CRM seeding route is no longer registered. Production portal flows should use real users, invitation tokens, partner relationships, and commission records.

## Public App Config and Coming Soon

Coming Soon mode is persisted in `bot_settings` as `platform.coming_soon_enabled`.

- Public read contract: `GET /api/v1/public/app-config`
- Admin update contract: `PUT /api/v1/settings` with `{ "platform.coming_soon_enabled": true|false }`
- Admin UI location: Backoffice/Admin Hub -> Settings -> Access Control -> Platform Access

The public config response exposes only safe launch metadata and does not include secrets, internal URLs, admin-only settings, or infrastructure configuration. Mutating the flag remains protected by the existing settings middleware chain: auth, privileged MFA when enabled, and `crm.admin.manage`.

Migration `000060_add_coming_soon_setting` seeds the setting for PostgreSQL deployments.

## Health and Validation

- liveness: `GET /health`
- readiness: `GET /ready`
- tests: `make test`
- local stack dependencies: PostgreSQL, Valkey for existing Redis-compatible flows, and optional NATS via `make infra-up`

## Database Migration Posture

PostgreSQL migrations in `migrations/postgres` are the runtime migration
source of truth. New migrations should be created with
`make migrate-create NAME=...`, which writes to `migrations/postgres`.

Startup never forces a migration version on its own. A dirty or partially applied schema stops the start with the
original error; `DB_MIGRATION_FORCE_RECOVERY=true` enables the legacy `Force(version)` retry for a local database only
and is refused when `APP_CONFIG_ENV`, `CONFIG_ENV`, `APP_ENV` or `ENVIRONMENT` names production. The local compose
stack runs migrations through the one-shot `backend-migrate` service with `DB_AUTO_MIGRATE=false`.

## Client IP, Proxies and Auth Rate Limits

- `TRUSTED_PROXIES` (comma-separated IPs/CIDRs, loopback always included) lists the peers allowed to set
  `X-Forwarded-For`. Behind an ingress controller set it to the cluster pod CIDR; without it every client shares the
  proxy's address for rate limiting and audit logs. An invalid entry, or one that trusts every address, falls back to
  loopback only. Handlers read the client address with `c.ClientIP()` only; raw forwarded headers are never trusted.
- `POST /api/v1/auth/login`, `/register`, `/forgot-password`, `/reset-password` and `/2fa/challenge` share one per-IP
  budget (1 request/second, burst 20) on top of the global limiter. With `TRUSTED_PROXIES` unset behind a proxy that
  budget is shared by all users, so set it before deploying.

## Related Docs

- [Root README](/home/chris/workspace/dydx-trading-bot/README.md)
- [Platform Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
- [Platform Overview](/home/chris/workspace/dydx-trading-bot/docs/PLATFORM.md)
