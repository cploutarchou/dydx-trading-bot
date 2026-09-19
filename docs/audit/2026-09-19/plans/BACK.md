# Plan — BACK (`backend/`) — 2026-09-19

Evidence, impact and root cause for every ID: `../findings/BACK.md`.
Verification baseline (2026-09-19, go1.26.6): `go build ./...`, `go vet ./...`, `go vet -tags integration ./internal/routes/` clean; `go test -race -count=1 ./...` ok in 12 packages (1m15s).

## P0

### BACK-P0-001 — Deactivating or demoting a user never revokes their sessions
- Root cause: `SessionStore.BumpUserGeneration` is called only from change-password, logout and reset-password; the admin user update path changes `is_active` / role without it, and the refresh path slides the TTL without re-checking either.
- Fix: bump the user's session generation in the admin update path whenever `is_active` becomes false or the role changes (fail the request if revocation fails, so an operator never sees "deactivated" while sessions live on); add an `is_active` re-check on session refresh.
- Verification: new route tests: deactivate → existing session rejected; role change → existing session rejected; `go test -race -count=1 ./internal/routes/... ./internal/auth/...`, then the full suite.
- Effort: S | Blast radius: med | Status: done (pending commit) — admin update/role/status and admin password reset revoke sessions before the write; 4 tests. Refresh-time is_active re-check not added (revocation already invalidates refresh via the generation check)

## P1

### BACK-P1-002 — NATS pending-command reconciler can never republish (envelope lacks the required CorrelationID)
- Fix: build the republish envelope with the stored command's correlation id (generate one when absent); add the missing unit test that runs `Validate()` on the reconciler's envelope.
- Verification: new test in `internal/nats`; `go test -race ./internal/nats/...`.
- Effort: S | Blast radius: low | Status: done (pending commit) — reconciler sets a correlation id and rebuilds the first-publish payload shape via a shared builder; 3 tests

### Proposal-only / deferred
- BACK-P1-001 quick-deploy quota and attribution ineffective — proposal (needs the ownership contract between backend `bot_instances` and the bot API; cross-service change).
- BACK-P1-003 unrehearsed migration 000070 in the live sequence — proposal (migration sequencing on real data is a human decision; never run here). Proposed: gate behind the explicit migrator run, rehearse on a copy, and remove `DB_AUTO_MIGRATE=true` from deployable manifests.
- BACK-P1-004 startup migration recovery calls `Force(version)` outside production labels — proposal (pair with BACK-P1-003; changing recovery behaviour affects every environment).
- BACK-P1-005 trusted proxies hard-coded to loopback; raw `X-Forwarded-For` trusted — deferred (needs the real ingress topology / CIDRs `[CONFIRM]`).

## P2

### BACK-P2-001 — Redis-backed sessions are required only when `APP_ENV == "production"`; the repo also uses `prod`
- Fix: reuse the codebase's existing production-environment predicate (or accept both labels) in `requireRedisSessions`; test both labels.
- Verification: new unit test; `go test -race ./internal/...`.
- Effort: S | Blast radius: low | Status: done (pending commit) — prod and production accepted in APP_ENV or ENVIRONMENT; table test

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
- Effort: S | Blast radius: low | Status: done (pending commit) — quick-deploy and benchmark queries built with url.Values; 2 tests

- BACK-P3-002 Dockerfiles root / tag-only bases / Go version disagreement — merged into INFRA-P2-001, INFRA-P2-006 and REPO-P2-001.
- BACK-P3-003 no `govulncheck`; lint non-gating; `cmd/migrate` untested — merged into REPO-P2-002 (scanner) / deferred (tests).
