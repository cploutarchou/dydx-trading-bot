# Plan — BACK (`backend/`) — 2026-09-19

Evidence, impact and root cause for every ID: `../findings/BACK.md`.
Verification baseline (2026-09-19, go1.26.6): `go build ./...`, `go vet ./...`, `go vet -tags integration ./internal/routes/` clean; `go test -race -count=1 ./...` ok in 12 packages (1m15s).

## P0

### BACK-P0-001 — Deactivating or demoting a user never revokes their sessions
- Root cause: `SessionStore.BumpUserGeneration` is called only from change-password, logout and reset-password; the admin user update path changes `is_active` / role without it, and the refresh path slides the TTL without re-checking either.
- Fix: bump the user's session generation in the admin update path whenever `is_active` becomes false or the role changes (fail the request if revocation fails, so an operator never sees "deactivated" while sessions live on); add an `is_active` re-check on session refresh.
- Verification: new route tests: deactivate → existing session rejected; role change → existing session rejected; `go test -race -count=1 ./internal/routes/... ./internal/auth/...`, then the full suite.
- Effort: S | Blast radius: med | Status: done (36723306) — admin update/role/status and admin password reset revoke sessions before the write; 4 tests. Refresh-time is_active re-check not added (revocation already invalidates refresh via the generation check)

## P1

### BACK-P1-002 — NATS pending-command reconciler can never republish (envelope lacks the required CorrelationID)
- Fix: build the republish envelope with the stored command's correlation id (generate one when absent); add the missing unit test that runs `Validate()` on the reconciler's envelope.
- Verification: new test in `internal/nats`; `go test -race ./internal/nats/...`.
- Effort: S | Blast radius: low | Status: done (36723306) — reconciler sets a correlation id and rebuilds the first-publish payload shape via a shared builder; 3 tests

### Proposal-only / deferred
- BACK-P1-001 quick-deploy quota and attribution ineffective — proposal (needs the ownership contract between backend `bot_instances` and the bot API; cross-service change).
- BACK-P1-003 unrehearsed migration 000070 in the live sequence — proposal (migration sequencing on real data is a human decision; never run here). Proposed: gate behind the explicit migrator run, rehearse on a copy, and remove `DB_AUTO_MIGRATE=true` from deployable manifests.
- BACK-P1-004 startup migration recovery calls `Force(version)` outside production labels — proposal (pair with BACK-P1-003; changing recovery behaviour affects every environment).
- BACK-P1-005 trusted proxies hard-coded to loopback; raw `X-Forwarded-For` trusted — deferred (needs the real ingress topology / CIDRs `[CONFIRM]`).

## P2

### BACK-P2-001 — Redis-backed sessions are required only when `APP_ENV == "production"`; the repo also uses `prod`
- Fix: reuse the codebase's existing production-environment predicate (or accept both labels) in `requireRedisSessions`; test both labels.
- Verification: new unit test; `go test -race ./internal/...`.
- Effort: S | Blast radius: low | Status: done (36723306) — prod and production accepted in APP_ENV or ENVIRONMENT; table test

### Deferred to the next run
- BACK-P2-002 commission sums as `float64` — deferred (money arithmetic; needs decimal type decision).
- BACK-P2-003 security controls fail open on schema probe errors — deferred (M; behaviour change on DB errors).
- BACK-P2-004 login enumerates account state — deferred (M).
- BACK-P2-005 raw `err.Error()` returned at 52 sites — deferred (M/L).
- BACK-P2-006 unauthenticated `/health`, `/ready`, `/metrics` disclose internals — deferred (needs the monitoring contract `[CONFIRM]`).
- BACK-P2-007 default Gin logger writes unredacted query strings — deferred (M).
- BACK-P2-008 NATS publisher field read outside the mutex — deferred (M; concurrency change with race tests).
- BACK-P2-009 context-less DB calls; dead `QueryTimeout` — deferred (L).
- BACK-P2-011 integration-tagged route tests never run in CI and 20+ fail — deferred (M; harness repair; found during BACK-P0-001, which is covered by four new tagged tests that pass in isolation: `go test -tags integration -race -run TestAdminUserRoutes ./internal/routes/` → ok).
- BACK-P2-010 WS relays have no read limit — deferred (S/M; needs frame-size expectations).

## P3

### BACK-P3-001 — `url.PathEscape` used for query values
- Fix: use `url.QueryEscape` / `url.Values` for the quick-deploy and benchmark query parameters; test a value containing `&` and `=`.
- Verification: new unit test; `go test -race ./internal/...`.
- Effort: S | Blast radius: low | Status: done (36723306) — quick-deploy and benchmark queries built with url.Values; 2 tests

- BACK-P3-002 Dockerfiles root / tag-only bases / Go version disagreement — merged into INFRA-P2-001, INFRA-P2-006 and REPO-P2-001.
- BACK-P3-003 no `govulncheck`; lint non-gating; `cmd/migrate` untested — merged into REPO-P2-002 (scanner) / deferred (tests).

## Queue 2 — unblocked by the owner's decisions (2026-09-19)

### BACK-P1-003 — Migrations run through the explicit migrator only
- Decision: 000070 has not been applied anywhere that matters. `DB_AUTO_MIGRATE=false` in compose/deployable config; the migrator image/job is the only path; 000070 is rehearsed on a copy before it runs anywhere.
- Verification: `docker compose config` shows the flag off for deployable stacks; backend starts without migrating (test); docs updated.
- Effort: S | Blast radius: med | Status: done (pending commit) — local stack gets a one-shot backend-migrate service; backend-api waits for it; DB_AUTO_MIGRATE=false in both stack files

### BACK-P1-004 — Remove the `Force(version)` startup recovery
- Decision: a dirty or mismatched schema stops the start with a clear error in every environment; no automatic `Force`.
- Verification: unit test on the recovery path; `go test -race ./...`.
- Effort: S | Blast radius: med | Depends on: BACK-P1-003 | Status: done (pending commit) — Force(version) recovery is explicit opt-in only and refused for production labels (CONFIG_ENV included); table test

### BACK-P1-005 — Trusted proxies and client IP
- Decision: Traefik ingress in k3s. Configurable `TRUSTED_PROXIES` (default loopback; the deployment sets the pod CIDR), client IP only through Gin's trusted-proxy logic, dedicated limiter on auth endpoints.
- Verification: tests: spoofed `X-Forwarded-For` from an untrusted peer is ignored; per-IP buckets differ behind a trusted proxy; auth limiter trips; `go test -race ./...`.
- Effort: M | Blast radius: med | Status: done (pending commit) — validated TRUSTED_PROXIES, raw X-Forwarded-For helper removed, shared per-IP limiter on credential endpoints; 3 tests. Deployment must set TRUSTED_PROXIES to the pod CIDR

### BACK-P1-001 — Quick-deploy must create an owned backend row and honour the quota (moved from proposal at the owner's request)
- Fix: after a successful upstream quick-deploy, insert the `bot_instances` row for the caller using the same create-then-rollback sequence as `BotInstanceService.CreateBotInstanceWithConfig` (or route quick-deploy through that service); make the count-and-insert atomic; delete the upstream instance when the insert fails; drop the `requested_by_user_id` injection the bot ignores.
- Verification: `go test -race -count=1 ./internal/routes/ -run QuickDeploy`: a row owned by the caller exists after 200; the N+1th quick-deploy returns 429; upstream delete is called when the insert fails. Full backend suite.
- Effort: M | Blast radius: med | Status: done (pending commit) — quick-deploy writes an owned bot_instances row (no credentials), rolls the upstream runtime back when that fails, and re-checks the quota after the insert; the unused requested_by_user_id injection is removed; 5 tests
