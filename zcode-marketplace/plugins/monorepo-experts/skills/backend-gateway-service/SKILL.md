---
name: backend-gateway-service
description: Implement and review the Go API gateway under backend/ — auth (JWT/sessions/MFA), tenancy and quotas, bot-API delegation, settings, and platform persistence. Use for any change inside backend/, especially auth, delegation, or SQL.
---

# backend/ service implementation (Go gateway)

## When to use
- Any code change under `backend/` (routes, middleware, services,
  repositories, models, tests).

## When NOT to use
- Frontend or bot code; cross-service contract design
  (`monorepo-architecture`); migration authoring (`db-migrations`).

## Hard rules
- Auth/security tests are contracts (ownership 404s, quota 429s, MFA flows,
  password-change gate, fail-closed for user_id=0). Do not relax them.
- Keep client-facing error messages generic for internal failures; log
  details server-side with trace ids.
- All SQL through the placeholder-rewriting repositories; parameterize
  everything user-influenced.
- Secrets: salted hashes only; never return stored secrets in responses.

## Procedure
1. Read `references/backend-service.md` first.
2. Inspect the route + middleware chain your change touches; note which tests
   pin the behavior.
3. Smallest complete change; table-driven tests for new behavior, including
   negative paths.
4. Update sqlite test schemas when columns change.

## Verification (run all; quote real results)
```
cd backend
go build ./... && go vet ./... && go vet -tags integration ./internal/routes/
go test -race -count=1 ./...
```
Optionally `golangci-lint run ./...` (reporting-only today; do not introduce
new classes of findings). Report files changed, contracts preserved, risks.
