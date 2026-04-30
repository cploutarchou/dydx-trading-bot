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

## Portal API Boundaries

The separated React portals use first-class API namespaces:

- Client/session: `GET /api/v1/me`, `GET /api/v1/auth/session`
- Backoffice/CRM: `/api/v1/backoffice/*`
- IB Portal: `/api/v1/ib/*`

Backoffice routes require authentication, privileged MFA when enabled, and RBAC permissions such as `users.read`, `roles.manage`, `crm.admin.manage`, `finance.manage`, and `audit.read`. IB routes require `ib`, `sub_ib`, or a backoffice/admin role. Admin and super admin retain override access through RBAC mappings.

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
- `GET /api/v1/backoffice/crm/summary`
- `GET /api/v1/backoffice/crm/clients`
- `GET /api/v1/backoffice/crm/clients/:id`
- `GET /api/v1/backoffice/audit-logs`

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

The legacy dummy CRM seeding route is no longer registered. Production portal flows should use real users, invitation tokens, partner relationships, and commission records.

## Health and Validation

- liveness: `GET /health`
- readiness: `GET /ready`
- tests: `make test`

## Related Docs

- [Root README](/home/chris/workspace/dydx-trading-bot/README.md)
- [Platform Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
- [Platform Overview](/home/chris/workspace/dydx-trading-bot/docs/PLATFORM.md)
