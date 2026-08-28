# BACKEND_AUDIT.md — dYdX Trading Bot Go Backend

Audit date: 2026-08-26
Scope: `backend/` (Go API gateway/orchestration layer; 220 Go files, 67 PostgreSQL migrations)
Baseline at audit start: `go build ./...` ✓, `go vet ./...` ✓, `go test ./...` ✓ (all green — several severe SQL defects survive CI because tests use sqlmock, which does not validate placeholder dialects against a real PostgreSQL).

Verification method: four parallel deep-audit passes (security, concurrency, database, API/error-handling) followed by direct source verification of every P0 claim and most P1 claims in this document. Findings listed as verified were re-checked line-by-line in source; false positives found during verification were dropped.

---

## 1. Architecture map

```
cmd/server/main.go
  └─ config.LoadFileEnvValues → config.AutoLoadStructuredConfigEnv (run.json / config/profiles) → config.LoadConfig
  └─ startup.ValidateDatabaseOwnership / ValidateSecurityBaseline / services.ValidateEncryptionKeyConfiguration
  └─ db.New(pgx stdlib, golang-migrate, pool settings)  [PostgreSQL-only]
  └─ startup.EnsureBootstrapAdmin
  └─ middleware.InitAuthMiddleware
  └─ app.BuildRouter → app.RunServer (router.Run → default http.Server, NO timeouts/signals)

internal/app/router.go — middleware chain: trace → error handling → CORS → header logging →
  request logging → rate limit → gzip; feature route registration; NATS publisher/consumer wiring;
  ICO email outbox worker; health/ready/metrics; debug routes.

internal/routes/* (26 files) — manual DI per feature. Key trees:
  - auth_routes.go        — session-first login/refresh (dydx_session cookie + Redis/valkey session store),
                            legacy JWT opt-in (AUTH_RETURN_LEGACY_TOKENS or APP_ENV=test)
  - bot_api_delegate_routes.go (~3.2k lines) — proxy to Python Bot API (BOT_API_URL :8889):
    backtests (create/list/status/trades/logs/artifacts/resync), WS /ws/strategies, SSE push,
    bot instance subroutes, celery, arbitrage, admin backtests
  - portal/backoffice/admin/ib routes — RequireAuth + RequireMFA + RequirePermission (DB-backed RBAC)
  - key_routes.go — dYdX credentials; AES-256-GCM encrypted mnemonics

internal/handlers → internal/services → internal/repository (raw *sql.DB; ? placeholders rewritten to $n
  per-repo via bindQuery when driver name contains "postgres").

Background workers: backtest_event_consumer.go (JetStream pull), backtest_push_hub.go (Redis pub/sub → WS),
  nats_command_service.go (async publish goroutines), ico_email_outbox_service.go (ticker loop),
  api_request_events_middleware.go (per-request ClickHouse insert goroutines).

Data stores: PostgreSQL (pgx v5 stdlib), Redis (sessions/cache/pubsub), ClickHouse (telemetry/live reads),
  MinIO (artifact signing), NATS JetStream (commands/backtest events).
```

## 2. Critical workflow map

1. **Browser auth**: login → password check → session cookie (+ refresh JWT cookie); RequireAuth resolves session cookie → bearer session → legacy JWT. Lockout counters maintained in `users` table (currently broken on Postgres — see A5).
2. **Backtest run**: frontend → backend delegated POST /api/v1/backtests/run (admission limits per user) → Python Bot API; run rows synced into backend SQL via BacktestSyncService; status/progress normalized centrally; WS/SSE push via hub.
3. **Privileged portal**: RequireAuth → RequireMFA (role-aware) → RequirePermission (RBAC tables).
4. **Bot runtime delegation**: backend forwards request-scoped tokens upstream; optional service-token mode.

## 3. Findings summary

Severity counts (see BACKEND_IMPROVEMENT_PLAN.md for full task list): **P0: 5 · P1: 12 · P2: 18 · P3: 9** (44 tasks total — 43 DONE as of 2026-08-28: ALL P0s, ALL P1s, all P2s and P3s except TASK-018 (ctx-through-repos), which is deliberately deferred with a phase plan)

### P0 — Critical (verified)

| ID | Finding | Evidence |
|----|---------|----------|
| A1 | Invitation-only registration is dead: `Redeem` has 5 placeholders / 3 args; `RevokeByTokenCode` 3/2 | invitation_token_repo.go:236-261, 210-232 (verified) |
| A5 | Brute-force lockout + security event logging silently dead: raw `?` placeholders sent to pgx (`UPDATE users ... WHERE id = ?` etc.) in login lockout helpers, CRM security events, backoffice audit logs, bootstrap-admin lock reset, debug migrations route | auth_routes.go:677-735; portal_routes.go:557-560; backoffice_routes.go:329-336; bootstrap_admin.go:91-95; app/router.go:279-299 (verified) |
| S1 | Bootstrap admin: hardcoded `admin123` default, `PasswordChangeRequired=false`, and **resets the admin's password/email/role on every restart** when env unset | startup/bootstrap_admin.go:14-98 (verified) |
| S2 | JWT verification fails open to repo-public default secret whenever `JWT_SECRET_KEY`/`SECRET_KEY` unset and `APP_ENV != production` (baseline check only fires in prod) → forgeable admin claims | middleware/auth_middleware.go:18-33; startup/security_baseline.go; config.go defaults (`change-me-*`) (verified) |
| S3 | MFA is never challenged at login: password → session directly; `/2fa/verify` is enrollment-only; `RequireMFA` checks enrollment existence, not session step-up → TOTP is decorative | auth_routes.go loginHandler; mfa_middleware.go:43-81 (verified) |

### P1 — High (verified unless noted)

- **A6** `UpdateTradeLog` uses `?0..?5` placeholders → bindQuery emits `$100/$111/...` → `PUT /api/v1/trade-logs/:id` 100% broken (tradelog_repo.go:148-166, verified).
- **A3/A4** `PartnerRelationshipRepository.Upsert` uses `ON CONFLICT (sponsor_user_id, partner_user_id)` but only `partner_user_id UNIQUE` exists → partner approval always 500s; `List` references `$2/$3` with 2 args → IB hierarchy listing broken (partner_relationship_repo.go:16-43, 64-74; migrations 000035/000046, verified).
- **C1** Partner application approval performs 3 writes (role promotion → relationship upsert → application update) with no transaction (portal_routes.go:325-353).
- **B1/BOLA** Delegated backtest routes: `ensureBacktestRunAccess` applied to only ~3 of ~40 `/api/v1/backtests/:run_id/*` endpoints and fails open when run owner is NULL or sync repo is nil (bot_api_delegate_routes.go:1112-1170).
- **B2/BOLA** Delegated `/api/v1/bots/:instance_id/*` routes have no Go-side ownership check; `POST /backtests/:run_id/create-strategy` copies any run's strategy snapshot without ownership (strategy_routes.go:62-185; bot_api_delegate_routes.go:2953-3145).
- **B3/BOLA** Trade-log CRUD entirely unscoped by user (tradelog_handler/service/repo); `CreateTradeLog` returns fields it never persisted (tradelog_handler.go:53-79).
- **S4** Bot API client silently retries user-initiated calls with the all-powerful service token on upstream 401 → per-user upstream authz bypass; fallback path also returns upstream 401 as success and blind-retries non-idempotent POSTs on transport errors (bot_api_client.go:444-511).
- **R1** No graceful shutdown anywhere: no signal handling, `router.Run` (no server timeouts), 5 background workers never stopped, deferred DB close unreachable (cmd/server/main.go; app/router.go:317-328).
- **R2** JetStream consumer NAKs poison messages immediately in an infinite hot loop (no backoff/MaxDeliver/DLQ); ack errors ignored; no AckWait config (backtest_event_consumer.go:112-166).
- **R3** Push hub writes to the same WS conn from two goroutines (Redis subscriber + JetStream projector) → gorilla/websocket concurrent-writer protocol corruption (backtest_push_hub.go:65-108).
- **D1** Unbounded queries: backtest candles SELECT without LIMIT when handler omits one (full run history into RAM); per-user audit-log listing has no LIMIT (backtest_handler.go:214-221; backtest_repo.go:229-233; auditlog_repo.go:116-124).
- **D2** Upstream path params not URL-escaped (path/query injection into bot API; e.g. `..%2F` rewrites upstream path); `io.ReadAll` unbounded on upstream bodies (bot_api_client.go:608-788, extended; :557).
- **R4** WS relay (both the delegate proxy and the backtest status push handler) has no read deadlines/ping-pong → goroutine leaks on silently dead peers (bot_api_delegate_routes.go:1230-1380).

### P2 — Medium (selection)

- Telemetry: `user_id` asserted as `string` but stored as `int` → user attribution always nil; per-request goroutine + single-row ClickHouse INSERT; production-grade batch writer exists but is unwired (api_request_events_middleware.go:62-66, 75-104).
- Singleflight in news/codex services not panic-safe → one panic permanently wedges that key (news_service.go:249-254; codex_service.go:948-953).
- No context/deadlines through the entire repository layer (~15 repos, non-context `Query/Exec`); `QueryTimeout` config is dead.
- `user_repo` runs up to ~9 schema-probe queries per user read (uncached column detection); same pattern in backtest repos.
- Sync-health endpoint N+1: ~13 queries per run × limit 200 (~2,600 queries/request) (backtest_sync_repo.go:654-753).
- `bot_instance_repository` Postgres fallback uses `CAST(... AS CHAR)` (length-1) → silently corrupts status/config JSON on drifted schema.
- Task commands: duplicate idempotency key returned as error instead of existing row; async publish goroutines unbounded/untracked; `pending` commands have no reconciler → stuck forever on failure.
- Partner commission metrics derive default periods from `time.Now()` at µs precision → duplicate rows per ingest; `AggregateByUsers` SUMs all → inflated (money) reporting.
- db.go `Query/QueryRow` wrappers cancel ctx before rows are consumed (latent — unused today); migration recovery `Force()` can mark half-applied migrations complete outside production.
- No request body size limit anywhere (`MaxBytesReader` absent); pagination params lack shared clamping (negative/oversized limits pass on multiple delegated endpoints).
- Query-string `access_token` accepted (token leakage via logs/history/Referer); CORS reflects credentials for any origin when unconfigured in non-prod.
- Analytics endpoints (`/api/v1/analytics/*`) expose platform-wide live positions/trades/worker metrics to any authenticated user.
- Password change does not revoke sessions/refresh tokens; refresh rotation does not invalidate the old token.
- Cache stampedes: realtime-stats lacks singleflight (codex/news have it); candle prefetch spawns ~11 untracked goroutines per resync, each materializing full candle history in RAM.
- Money as float: `backtest_runs`/`trades`/`positions` use REAL/float; partner commissions use DOUBLE PRECISION; SUM aggregation loses cents (NUMERIC/decimal migration recommended, phased).

### P3 — Low (selection)

Unwired dead route file `backtest_routes.go` (would panic gin on duplicate registration; carries IDOR-prone handlers); `InitAuthMiddleware` nil-cfg deref (line 40) despite nil-tolerant guard; response envelope inconsistency (3+ shapes); internal error strings leaked to clients on 500s; `time.Now()` vs UTC inconsistencies; candle end-date boundary excludes end day; mailgun webhook timestamp window one-sided (future-dated replays pass); telegram preflight `http.Post` without timeout; `hashSecretValue` unsalted SHA-256 of mnemonic + 8-char mask disclosure; rate-limiter bucket map growth between cleanups; in-process `sync.Map` lock maps grow forever; ICO outbox at-least-once duplicates undocumented; `GetCacheStats` always reports "operational".

### False positives rejected during verification

- `BacktestRun.EndingBalance` NULL scan failure — model field is `*float64` (models.go:185), NULL scans safely. Not a bug.
- WS relay goroutine leak on clean client disconnect — handled via `done` channel; only *silent* peer death leaks (tracked as R4).

## 4. Areas found sound

SQL injection surface (parameterized queries throughout; dynamic fragments are static literals); Mailgun webhook HMAC (constant-time, fails closed); path traversal/SSRF in outbound fetchers; log redaction middleware; cookie flags (HttpOnly, scoped paths, Secure in prod); `rows.Err()` checked in all 19 repos; response bodies closed at all HTTP call sites; delegation worker pool WaitGroup correctness; RBAC/portal route gating; migration index discipline (000047-000057); ICO outbox/event idempotency design.

## 5. Remaining risks after fixes (to track)

- MFA is now enforced at login (TASK-005 DONE): pending sessions are rejected everywhere except POST /api/v1/auth/2fa/challenge. FRONTEND FOLLOW-UP: the login page must handle `mfa_required: true` (prompt for TOTP, POST /auth/2fa/challenge); until then, TOTP-enrolled users cannot complete browser login.
- Refresh-token path does not re-challenge MFA (legacy refresh cookies issued before the change, or bearer fallback mode, still exchange without TOTP) — pair with TASK-031 session/refresh revocation work.
- `POST /api/v1/backtests/compare` accepts run ids in its body (upstream-defined shape); ownership not enforced there.
- Runs created before backend-sync existed (unknown local owner) are now admin-only on delegated routes — intentional fail-closed; may surface as 404s for legacy tenant users.
- Encryption-key KDF hardening deferred: changing derivation would make existing stored credentials undecryptable; requires a re-encryption migration (pair with TASK-039 NUMERIC work).
- Full ctx-through-repos refactor (TASK-018) is the largest outstanding reliability item.
- NUMERIC money migration Phase 1 landed (migration 000069, commission columns); Phase 2 (backtest_runs/bot_trades REAL columns) needs staging rehearsal.
- Response envelopes remain intentionally non-uniform (TASK-037 envelope unification deferred as frontend-breaking); 500s no longer leak internal detail.
- The Postgres critical-path harness needs POSTGRES_TEST_DSN to execute in CI.
- Password change now revokes all sessions via generation counters (TASK-031); legacy refresh-JWT revocation still needs a server-side registry.
- Query-string access_token is now accepted only on WebSocket upgrade requests (frontend WS URLs depend on it); CORS defaults to loopback-only when unconfigured.
- Analytics routes now require the analytics.read permission (admins have it by default).
- Multi-replica rate limiting and lockout require shared storage (Redis) — design decision pending.
