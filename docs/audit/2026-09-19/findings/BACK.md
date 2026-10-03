# Findings — BACK (`backend/`, Go / Gin API gateway)

Audit date: 2026-09-19. Scope: `backend/` (code, tests, config, `migrations/postgres`), `docker/Dockerfile.backend`, `docker/Dockerfile.backend-migrator`. Read-only investigation; no files other than this one were changed. IDs are provisional.

Route wiring was checked before any authorization claim: every `/api/v1/*` and `/ws/*` group registers `middleware.RequireAuth()` (see `internal/app/router.go:218-248` and each `internal/routes/*_routes.go`); the only unauthenticated surfaces are `/auth/{login,register,refresh,logout,forgot-password,reset-password,registration-status}`, `/api/v1/public/*`, `/api(/v1)/public/ico/*`, `/version`, `/health`, `/ready`, `/metrics`. SQL is parameterised throughout (the `fmt.Sprintf` SQL sites interpolate only constant table/column names). The upstream bot client (`internal/services/bot_api_client.go`) has timeouts, a 16 MiB response cap, `url.PathEscape` on path segments, and no retry of non-idempotent calls. Those areas are not reported.

---

### BACK-P0-001 — Deactivating or demoting a user does not revoke live sessions; session refresh renews them indefinitely
- Priority: P0 | Type: security | Area: auth/sessions
- Evidence: backend/internal/routes/auth_routes.go:1413-1419 (session refresh path: no DB lookup, no `is_active`/role re-check, sliding TTL with no absolute lifetime)
  ```go
  sessionData, err := store.Refresh(c.Request.Context(), sessionToken, sessionTTL())
  if err == nil && sessionData != nil {
  	setSessionCookie(c, sessionToken, int(sessionTTL().Seconds()))
  	sessionRefreshResponse := TokenResponse{
  		TokenType:        "session",
  ```
  backend/internal/routes/admin_user_routes.go:757-769 (admin update writes role / `is_admin` / `is_active` and never touches the session store)
  ```go
  user.Role = nextRole
  user.IsAdmin = nextRole == "admin"
  user.IsActive = nextIsActive
  ...
  if err := userRepo.Update(user); err != nil {
  ```
  `BumpUserGeneration` has exactly three callers (`grep -rn BumpUserGeneration`): `auth_routes.go:1362` (change-password), `auth_routes.go:1586` (logout), `password_reset_routes.go:148`. None of `PUT /admin/users/:id`, `/role`, `/status`, `/reset-password`, `/reset-mfa` call it. `RequireAuth` (`internal/middleware/auth_middleware.go:127-139`) trusts `IsAdmin`/`Role` from the stored session, and the bearer-JWT path (`auth_middleware.go:181-199`) trusts the claims with no DB or generation check at all.
- Impact: a disabled account (offboarded staff, compromised client) keeps full API access; a demoted admin keeps `is_admin=true` and therefore bypasses every ownership check (`requireBotInstanceOwnership`, `ensureBacktestRunAccess`, trade logs) and can start/stop other users' live bots. Because `/auth/refresh` slides the TTL without re-reading the user, access never expires as long as the client refreshes once per 24 h. An admin-initiated password reset likewise leaves the attacker's existing session alive.
- Root cause: authorization state is snapshotted into the session at login; revocation (generation bump) was only wired to self-service password flows.
- Fix: (1) call `store.BumpUserGeneration` in the admin status/role/update/reset-password/reset-mfa handlers whenever `is_active`, role, password or MFA changes; (2) in the session branch of `refreshHandler`, load the user and reject when missing/inactive, and rewrite `Role`/`IsAdmin` from the DB row; (3) extend the per-request lookup already performed by `enforcePasswordChangeCleared` (`cmd/server/main.go:100-109`) to also return `is_active` and fail the request when false; (4) add an absolute session lifetime (`CreatedAt` + max age) in `SessionStore.Refresh`; (5) reject bearer access JWTs whose user generation has moved (add `sess_gen` to access tokens as is already done for refresh tokens).
- Verification: `cd backend && go test -race -count=1 ./internal/routes/ ./internal/auth/ ./internal/middleware/` with new tests `TestAdminDeactivateRevokesSessions`, `TestAdminDemoteRevokesAdminSession`, `TestSessionRefreshRejectsInactiveUser`, `TestSessionAbsoluteLifetime`.
- Effort: M | Blast radius: med | Depends on: —

### BACK-P1-001 — Quick-deploy quota and attribution are ineffective: no backend row is created and the bot ignores `requested_by_user_id`
- Priority: P1 | Type: security | Area: routes/bot delegation
- Evidence: backend/internal/routes/bot_api_delegate_routes.go:3316-3325
  ```go
  // Force server-side attribution; a caller-supplied value is
  // ignored so the spawned instance is attributable to this user.
  config["requested_by_user_id"] = userID

  result, err := requestClient.QuickDeployBot(instanceName, autoStart, config)
  ...
  c.JSON(200, result)
  ```
  The quota a few lines above counts backend rows (`botInstanceRepo.CountBotInstancesByUserID(userID)`, line 3290), but this handler never calls `botInstanceRepo.CreateBotInstance` (only `handlers/bot_instance_handler.go:460` does). Upstream, `bot/src/api/v1/bot_lifecycle.py:812-821` declares only `instance_name`, `credentials`, `trading_params`, `auto_start` and does `_ = current_user`; `bot/src/bot_instance_manager.py:755-756` only updates existing rows (`if record is None: continue`).
- Impact: every quick-deploy spawns a real, auto-started trading process that is never counted, so the per-user instance quota can be exceeded without limit through this endpoint; the resulting instance has no owner row, so its creator receives 404 from every `/api/v1/bots/:instance_id/*` route and cannot stop it — only an admin can. An unowned live bot trading real funds is a money-safety problem, not only a quota problem.
- Root cause: parity with `CreateBotInstance` was implemented as a pre-check only; the persistence half (insert owner row, rollback upstream on failure) was not ported, and the attribution field is not part of the upstream contract.
- Fix: after a successful upstream quick-deploy, insert the `bot_instances` row (`UserID=userID`, returned `instance_id`) using the same create-then-rollback sequence as `BotInstanceService.CreateBotInstanceWithConfig`; or route quick-deploy through that service. Make count+insert atomic (see BACK-P2-009). Remove the misleading `requested_by_user_id` injection or add it to the bot contract in the same change set.
- Verification: `cd backend && go test -race -count=1 ./internal/routes/ -run QuickDeploy` with new tests asserting (a) a row owned by the caller exists after 200, (b) the N+1th quick-deploy returns 429, (c) upstream delete is called when the insert fails.
- Effort: M | Blast radius: med | Depends on: —

### BACK-P1-002 — NATS pending-command reconciler can never re-publish: envelope is built without `CorrelationID`, which `Validate()` requires
- Priority: P1 | Type: bug | Area: services/nats
- Evidence: backend/internal/services/nats_command_service.go:412-426
  ```go
  envelope := nats.Envelope{
  	MessageID:       taskCmd.ID,
  	IdempotencyKey:  taskCmd.IdempotencyKey,
  	OwnerType:       taskCmd.OwnerType,
  	...
  if err := envelope.Validate(); err != nil {
  	log.Printf("NATS reconciler: skipping invalid command %s: %v", taskCmd.ID, err)
  ```
  backend/internal/nats/publisher.go:87-89
  ```go
  if strings.TrimSpace(e.CorrelationID) == "" {
  	return errors.New("envelope correlation_id is required")
  }
  ```
  The primary publish path sets it (`nats_command_service.go:254`); the reconciler literal does not. `grep -rn ReconcilePendingCommands --include=*_test.go` returns nothing — the path is untested.
- Impact: when the command bus is enabled, any backtest command whose first publish failed (NATS outage, restart, concurrency limiter at line 192 "left pending") stays `pending` forever; the reconciler started in `internal/app/router.go:183-199` logs "skipping invalid command" for the same oldest 50 rows every minute and recovers nothing. Users see a backtest accepted that never runs. The ticker also hardcodes the subject to `backtest.command.start` regardless of `command_type`.
- Root cause: the reconciler envelope was written by hand instead of reusing the builder used by `publishToNATSAsync`; no test covers it.
- Fix: extract one `buildEnvelope(taskCmd, correlationID)` used by both paths; persist the correlation id on `task_commands` (or fall back to `taskCmd.ID`); derive the subject from `CommandType`; mark commands that fail validation as `failed` so they stop occupying the LIMIT window.
- Verification: `cd backend && go test -race -count=1 ./internal/services/ -run Reconcile` with a fake publisher asserting one publish and status `published` for a stale pending row.
- Effort: S | Blast radius: low | Depends on: —

### BACK-P1-003 — Migration 000070 rewrites the largest tables under ACCESS EXCLUSIVE lock, is self-declared "not rehearsed", yet sits in the live sequence and runs at startup where `DB_AUTO_MIGRATE=true`
- Priority: P1 | Type: migration | Area: migrations/postgres
- Evidence: backend/migrations/postgres/000070_backtest_money_numeric_phase2.up.sql:4-9
  ```sql
  -- STATUS: WRITTEN BUT NOT REHEARSED — this migration rewrites the largest
  -- tables in the system (backtest_runs/backtest_trades/backtest_positions).
  -- Rehearse against a production-sized snapshot before enabling in
  -- deployment: measure ALTER duration, lock time, and disk headroom, and run
  ```
  There is no gate: the file is an ordinary numbered migration followed by 000071–000073, so `migrate up` (and `cmd/server` when `DB_AUTO_MIGRATE` is truthy, `cmd/server/main.go:21-31,73`) applies it. `DB_AUTO_MIGRATE: "true"` is set in `docker-compose.stack.yml:204`, `docker-compose.stack.arm64.yml:211`, `deploy/k8s/dydx-trading-bot-production.yaml:88` and `...-staging.yaml:90`, while `docker/Dockerfile.backend-migrator:4-5` states "never at application startup (DB_AUTO_MIGRATE stays false)".
- Impact: `ALTER COLUMN ... TYPE NUMERIC(20,8)` on `backtest_trades`/`backtest_positions`/`backtest_runs` is a full table rewrite holding ACCESS EXCLUSIVE for its duration and needing ~2x disk; run at pod start it blocks every backtest read/write and can fail readiness → crash-loop, leaving `schema_migrations` dirty. `NUMERIC(20,8)` also truncates sub-1e-8 precision for low-priced perpetual markets, and the down migration (`...down.sql:1-2`) admits values are lost on the way back, so the step is effectively irreversible.
- Root cause: a deferred, unrehearsed migration was committed into the executable sequence instead of being held out until rehearsed; deployment manifests and the migrator image disagree about who runs migrations.
- Fix: proposal (needs a human decision): if 000070 has not been applied anywhere shared, move it out of `migrations/postgres` (or replace with expand → backfill → swap using new columns) until rehearsed; if it has been applied, record that and drop the warning. Set `DB_AUTO_MIGRATE=false` in all non-dev manifests and run `backend-migrator` as the explicit Job; add a `lock_timeout`/`statement_timeout` preamble to table-rewriting migrations.
- Verification: `SELECT version, dirty FROM schema_migrations` on each environment (read-only) to learn whether 000070 already ran; rehearsal timing on a production-sized snapshot; `grep -rn DB_AUTO_MIGRATE docker-compose*.yml deploy/` shows `false` outside dev.
- Effort: M | Blast radius: high | Depends on: —

### BACK-P1-004 — Startup migration "recovery" force-marks a failed migration as applied (all environments except labels `prod`/`production`)
- Priority: P1 | Type: migration | Area: internal/db
- Evidence: backend/internal/db/db.go:436-456
  ```go
  isRecoverable := strings.Contains(errLower, "dirty") ||
  	strings.Contains(errLower, "no migration found") ||
  	isAlreadyExistsMigrationError(errLower)
  ...
  if fErr := m.Force(int(ver)); fErr != nil {
  ```
  backend/internal/db/db.go:483-489 — the guard checks only `APP_CONFIG_ENV`, `APP_ENV`, `ENVIRONMENT` for `production`/`prod`; `config.ResolveAppConfigEnvironment` (`config/structured_env.go:25`) also honours `CONFIG_ENV`, so a deployment labelled through `CONFIG_ENV=production`, or any `staging` environment, gets automatic forcing.
- Impact: when migration N fails half-way (dirty) or hits "already exists", `Force(N)` records N as cleanly applied and `Up()` continues with N+1; the remaining statements of N never run. The result is silent schema drift (missing columns/indexes/constraints) that the code then papers over with `isSchemaEvolutionError` fallbacks (see BACK-P2-003). Up to 10 forced retries per boot.
- Root cause: convenience recovery for non-idempotent historical migrations was made the default instead of an explicit operator action.
- Fix: default `migrationForceRecoveryAllowed()` to false everywhere; allow only with explicit `DB_MIGRATION_FORCE_RECOVERY=true`, and use `ResolveAppConfigEnvironment()` for the label so both code paths agree. Make historical migrations idempotent (`IF NOT EXISTS`) instead.
- Verification: `cd backend && go test -race -count=1 ./internal/db/` with a test asserting a dirty state returns an error when the env var is unset under `APP_ENV=staging`.
- Effort: S | Blast radius: med | Depends on: —

### BACK-P1-005 — Client IP is always the ingress/proxy address: per-IP rate limiting collapses into one shared bucket and audit IPs are wrong; one helper trusts raw `X-Forwarded-For`
- Priority: P1 | Type: security | Area: app/router, middleware/rate_limit
- Evidence: backend/internal/app/router.go:91 and :107
  ```go
  if err := router.SetTrustedProxies([]string{"127.0.0.1", "::1"}); err != nil {
  ...
  router.Use(middleware.RateLimitMiddleware(100, 200))
  ```
  backend/internal/middleware/rate_limit.go:109-117 keys the bucket on `c.ClientIP()`. The trusted-proxy list is hard-coded (no env/config: `grep -rn "TRUSTED_PROXIES\|TrustedProxies"` finds only this line) while the service is deployed behind an Ingress (`deploy/k8s-next/applications.yaml`, `deploy/k8s/*.yaml`), whose pod IP is not loopback, so Gin ignores `X-Forwarded-For`. Conversely backend/internal/routes/password_reset_routes.go:18-23 takes the first `X-Forwarded-For` element verbatim:
  ```go
  forwarded := strings.TrimSpace(c.GetHeader("X-Forwarded-For"))
  if forwarded != "" {
  	return strings.TrimSpace(strings.Split(forwarded, ",")[0])
  ```
- Impact: all users share a single 100 rps / burst 200 bucket — one noisy client (or an attacker) rate-limits the whole platform, and the limiter offers no per-attacker throttling of `/auth/login`, `/auth/forgot-password`, `/auth/register`. `security_login_events.ip_address` and `audit_logs.ip_address` record the proxy IP, destroying forensic value; the password-reset token record stores an attacker-chosen IP. There is also no stricter limiter on the unauthenticated auth endpoints (the only brake is the per-account lockout, see BACK-P2-004).
- Root cause: proxy trust is a constant rather than deployment configuration; a second, ad-hoc client-IP helper was added instead of fixing `ClientIP()`.
- Fix: read trusted proxy CIDRs from config (`TRUSTED_PROXIES`, validated at startup by `ValidateSecurityBaseline` for non-dev), delete `clientIPOf` in favour of `c.ClientIP()`, and add a dedicated low-rate limiter (per IP and per username/email) on the unauthenticated `/api/v1/auth/*` POST routes.
- Verification: `cd backend && go test -race -count=1 ./internal/app/ ./internal/middleware/` with tests that send `X-Forwarded-For` from a configured proxy CIDR and assert distinct buckets / recorded IP; manual: `curl -H 'X-Forwarded-For: 1.2.3.4'` through the ingress and inspect `security_login_events`.
- Effort: M | Blast radius: med | Depends on: —

### BACK-P2-001 — Production-only session hardening keys on the literal `APP_ENV == "production"`; `prod` silently gets in-memory sessions
- Priority: P2 | Type: security | Area: auth/session_store
- Evidence: backend/internal/auth/session_store.go:119-125
  ```go
  func requireRedisSessions() bool {
  	value := strings.TrimSpace(strings.ToLower(os.Getenv("AUTH_REQUIRE_REDIS_SESSIONS")))
  	...
  	return strings.EqualFold(os.Getenv("APP_ENV"), "production")
  }
  ```
  Elsewhere the code documents that the label in use is `prod`: backend/internal/routes/auth_routes.go:169-171 `// Accept both 'production' and 'prod' (platform.yml uses 'prod').`; `config/structured_env.go:17` normalises both; `docker/Dockerfile.worker:27` sets `APP_ENV=prod`.
- Impact: with `APP_ENV=prod` (or the environment expressed via `APP_CONFIG_ENV`/`ENVIRONMENT`), a Redis outage at boot downgrades to the per-process in-memory store with only a log line: sessions and the revocation generation counter are lost on every restart and are not shared across replicas; the in-memory map also never evicts expired entries except on lookup (`session_store.go:175-183`), so every login / abandoned MFA-pending session leaks until restart. After such a restart `CurrentUserGeneration` returns 0, and `refreshHandler` (`auth_routes.go:1487`, `currentGen > 0 && ...`) accepts refresh JWTs that had been revoked by a password change.
- Root cause: environment detection is re-implemented with different accepted labels in at least six places (`session_store.go:124`, `auth_routes.go:171`, `middleware.go:125`, `db.go:485`, `security_baseline.go:62`, `structured_env.go:17`).
- Fix: use `config.ResolveAppConfigEnvironment() == "production"` in `requireRedisSessions` and the other sites (single helper); add a janitor or lazy sweep to the memory store; persist the generation counter in PostgreSQL (`users.session_generation`) so revocation survives cache loss.
- Verification: `cd backend && go test -race -count=1 ./internal/auth/` with `t.Setenv("APP_ENV","prod")` asserting `requireRedisSessions()` is true; test that a revoked refresh token stays revoked after constructing a fresh `SessionStore`.
- Effort: S | Blast radius: low | Depends on: —

### BACK-P2-002 — Commission money is scanned and summed as `float64` after the columns were migrated to NUMERIC; summary endpoint also does N+1 queries and drops errors
- Priority: P2 | Type: data | Area: routes/portal, models
- Evidence: backend/internal/routes/portal_routes.go:255-263
  ```go
  totalCommission := 0.0
  for _, user := range users {
  	...
  	metric, metricErr := commissionRepo.GetLatestByUser(user.ID)
  	if metricErr == nil && metric != nil {
  		totalCommission += metric.NetCommissionUSD
  ```
  backend/internal/routes/portal_routes.go:237-238 `pending, _ := appRepo.CountPending()` / `relationships, _ := relationshipRepo.List(5000, 0)`. backend/migrations/postgres/000069_commission_metrics_numeric.up.sql:1-4 states the columns are "payout-critical" and that "Go models continue scanning into float64". `grep shopspring go.mod` → no decimal library; 117 `float64` money/price fields across models/repository/services (e.g. `internal/models/models.go:179-189`).
- Impact: payout-relevant totals (`net_commission_usd`) are accumulated in binary floating point, reintroducing the cent drift the NUMERIC migration was meant to remove; one SQL round-trip per IB user (up to 1000) per dashboard load; a failing commission/relationship query yields a silently smaller total rather than an error — a wrong number on a finance screen.
- Root cause: phase 1 changed storage only; the Go side has no decimal type.
- Fix: aggregate in SQL (`SELECT COALESCE(SUM(net_commission_usd),0)::text` over the latest-per-user CTE that already exists at `partner_commission_metric_repo.go:187-193`) and carry the value as a decimal string (or a vetted decimal type) through the API; return 500 when any component query fails. Treat backtest/bot P&L fields as a follow-up.
- Verification: `cd backend && go test -race -count=1 ./internal/routes/ -run CRMSummary` with amounts such as 0.1+0.2 and a failing repo; `POSTGRES_TEST_DSN` harness for the SQL aggregate.
- Effort: M | Blast radius: med | Depends on: —

### BACK-P2-003 — Security controls fail open on schema/DB probe errors (lockout, MFA enforcement, security-event logging)
- Priority: P2 | Type: security | Area: auth, repository/schema_cache
- Evidence: backend/internal/routes/auth_routes.go:995-1001
  ```go
  ).Scan(&failedAttempts, &lockedUntil)
  if isSchemaEvolutionError(err) {
  	return 0, nil, nil
  }
  ```
  backend/internal/repository/user_repo.go:82-86
  ```go
  columns, err := cachedTableColumns(r.db, "users")
  if err != nil {
  	return false
  }
  ```
  backend/internal/middleware/mfa_middleware.go:53-56 `if !userRepo.SupportsMFA() { c.Next(); return }`. `loginHandler` also only logs a lock-state read error and continues (`auth_routes.go:1115-1118`). Error classification is substring matching on driver text (31 sites: `grep -rn "isSchemaEvolutionError\|isUndefinedColumnError\|no such table\|does not exist"`).
- Impact: if the `users` probe fails (transient DB error before the first successful probe, or code deployed ahead of the explicit migration Job), `selectUserColumns()` emits `FALSE AS mfa_enabled`, so login issues a full session without the TOTP challenge and `RequireMFA` waves privileged routes through; brute-force lockout and `security_login_events` become silent no-ops. Successful probes are cached for the process lifetime (`schema_cache.go:19-24`), so a pod started before a migration never notices the new columns until restarted.
- Root cause: backwards-compatibility shims for old schemas were applied to security-critical columns and treat "cannot tell" as "feature absent".
- Fix: the required schema version is known — assert it at startup (fail readiness when `schema_migrations.version` is below the minimum the binary needs) and delete the optional-column branches for `mfa_enabled`, `failed_login_attempts`, `locked_until`, `password_change_required`; make remaining probes return an error (fail closed) instead of `false`.
- Verification: `cd backend && go test -race -count=1 ./internal/routes/ ./internal/middleware/ ./internal/repository/` with a stub `SQLRunner` whose probe errors: login must return 5xx, not a session.
- Effort: M | Blast radius: med | Depends on: BACK-P1-004

### BACK-P2-004 — Login leaks account state and the lockout is an account-level DoS lever
- Priority: P2 | Type: security | Area: auth/login
- Evidence: backend/internal/routes/auth_routes.go:1106-1112 (checked before the password is verified)
  ```go
  if !user.IsActive {
  	logSecurityLoginEvent(database, &user.ID, user.Username, "login", "failure", "account_inactive", requestIP, userAgent)
  	c.JSON(http.StatusForbidden, gin.H{
  		"success": false,
  		"error":   "Account is inactive",
  ```
  Same pattern for the lock state at :1119-1128 (429 + `locked_until`), and unknown usernames return before any bcrypt work (:1086-1104) while known ones pay `bcrypt.CompareHashAndPassword` (:1133). `forgotPasswordHandler` sends mail synchronously only for existing active accounts (`password_reset_routes.go:55-63`), giving the same timing oracle for emails despite the identical response body. :1064-1068 also returns `"details": err.Error()` from the JSON binder.
- Impact: usernames/emails and their active/locked status are enumerable without credentials; five wrong passwords lock any known account (including the only admin) for 15 minutes, repeatable forever, with no per-source throttle because of BACK-P1-005.
- Root cause: status checks precede credential verification; no constant-time path for unknown users; lockout is purely per-account.
- Fix: verify the password (against a fixed dummy hash for unknown users) before revealing inactive/locked state, return the same 401 body for all pre-auth failures, queue reset mail asynchronously (an outbox worker pattern already exists for ICO mail), and combine account lockout with per-IP/per-username throttling and exponential back-off rather than a hard lock.
- Verification: `cd backend && go test -race -count=1 ./internal/routes/ -run 'Login|ForgotPassword'` asserting identical status/body for unknown, inactive and wrong-password cases.
- Effort: M | Blast radius: low | Depends on: BACK-P1-005

### BACK-P2-005 — Raw internal error strings are returned to clients (52 sites), contrary to the service's own rule
- Priority: P2 | Type: security | Area: routes, app/analytics, app/health
- Evidence: backend/internal/routes/bot_api_delegate_routes.go:1186-1191
  ```go
  ownerID, err := backtestRepo.GetRunOwnerIDContext(c.Request.Context(), runID)
  if err != nil {
  	c.JSON(http.StatusInternalServerError, gin.H{
  		"success":   false,
  		"message":   "failed to verify backtest access",
  		"error":     err.Error(),
  ```
  Count: `grep -rn '"\(error\|details\|message\)": *err\.Error()' --include=*.go internal | grep -v _test | wc -l` → 52 (16 in `bot_api_delegate_routes.go`, 12 in `app/analytics_routes.go`, 10 in `auth_routes.go`, 6 in `backoffice_routes.go`). Also `admin_user_routes.go:772` (`fmt.Sprintf("Failed to update user: %v", err)`), `handlers/bot_instance_handler.go:412`, `handlers/tradelog_handler.go:56`, `app/router.go:347`. Separately `respondBotAPIError` (`bot_api_delegate_routes.go:73-84`) forwards the upstream status code and message verbatim, so an upstream 401 (e.g. a rejected service token) reaches the browser as a 401, which a session-based frontend treats as "logged out".
- Impact: PostgreSQL/driver messages (table, column, constraint names, DSN host on connection errors), ClickHouse errors and upstream bot internals are disclosed to any authenticated user; upstream auth faults masquerade as end-user auth faults.
- Root cause: `references/backend-service.md` lists "reintroducing raw `err.Error()` into client responses" as a known failure mode; there is no shared helper enforcing generic 5xx bodies outside `respondBotAPIError`'s unclassified branch.
- Fix: one `respondInternalError(c, err, publicMsg)` helper that logs with trace id and returns a generic body; replace the 5xx sites first (binder 400s may keep a sanitised validation message). Map upstream 401/403 from the bot to 502 when the service-token model is active.
- Verification: the grep above returns only reviewed 4xx validation sites; `go test -race -count=1 ./internal/routes/` with a failing repo stub asserting the body does not contain the driver text.
- Effort: M | Blast radius: med | Depends on: —

### BACK-P2-006 — Unauthenticated `/health`, `/ready`, `/metrics` disclose topology and proxy an upstream call per hit
- Priority: P2 | Type: security | Area: app/health
- Evidence: backend/internal/app/health.go:326-339 and :402-404
  ```go
  "database_ownership": dbOwnership,
  "bot_api":            botSnapshot,
  "bot_recovery":       botRecovery,
  "database": gin.H{
  	"healthy":             dbHealthy,
  	"error":               dbError,
  ```
  `dbOwnership` is `startup.DatabaseOwnershipDiagnostics` (`internal/startup/db_ownership.go:24-31`: backend and bot DB host, port, name, cutover mode); `botSnapshot` carries `base_url`, `probe_url` and the upstream `/health` | `/ready` | `/metrics` JSON payload (`health.go:116-124`). Routes are registered on the bare router with no middleware (`health.go:295-402`).
- Impact: anyone who can reach :8888 (it is the browser-facing origin) learns internal hostnames, database names, pool statistics, bot recovery state and bot metrics; each request triggers a synchronous upstream probe with a 3 s timeout, a cheap amplification path toward the trading bot.
- Root cause: liveness, readiness and diagnostics share one public handler.
- Fix: keep `/health` and `/ready` minimal (`status` only, cached upstream result for a few seconds); move the detailed payload and `/metrics` behind `RequireAuth` + admin, or bind them to an internal listener.
- Verification: `curl -s localhost:8888/health | jq 'keys'` shows only status fields; `go test -race -count=1 ./internal/app/`.
- Effort: S | Blast radius: med | Depends on: —

### BACK-P2-007 — Gin's default access logger writes unredacted query strings (WS `access_token`, ICO `token`) and every request's headers are logged
- Priority: P2 | Type: security | Area: app/router, middleware/logging
- Evidence: backend/internal/app/router.go:90 `router := gin.Default()` (installs `gin.Logger()`, which logs `path?rawquery` verbatim) alongside the custom `RequestLoggingMiddleware`, which does redact (`internal/middleware/request_validation.go:450`). Tokens do travel in queries: backend/internal/middleware/auth_token.go:29-31
  ```go
  if isBrowserWebSocketUpgrade(c.Request) {
  	if queryToken := strings.TrimSpace(c.Query("access_token")); queryToken != "" {
  		return "Bearer " + queryToken, "query:access_token"
  ```
  and `internal/handlers/ico_whitelist_handler.go:49,88` (`c.Query("token")`). `RedactSensitiveRawQuery` returns the raw query unchanged when parsing fails (`internal/middleware/redaction.go:44-46`). `HeaderLoggingMiddleware` (`header_logging.go:12-18`) logs all headers of every request, masking only `Authorization`/`Cookie`/`Set-Cookie`. `RunServer` additionally logs every registered route on each boot (`router.go:401-403`).
- Impact: bearer/session tokens and single-use verification tokens land in container logs and any log aggregation; three log lines per request (gin logger + header dump + request log) is noise that hides real events and costs storage.
- Root cause: `gin.Default()` kept while custom logging was added on top.
- Fix: `gin.New()` + `gin.Recovery()`; keep only the redacting request logger; make header logging opt-in via a debug env flag and extend the mask list (`Proxy-Authorization`, `X-Api-Key`, `X-CSRF-Token`, `Sec-WebSocket-Protocol`); on parse failure log `<unparseable>` instead of the raw query.
- Verification: `cd backend && go test -race -count=1 ./internal/middleware/ ./internal/app/` with a log-capture test requesting `/ws/strategies?access_token=SECRET` and asserting `SECRET` is absent.
- Effort: S | Blast radius: low | Depends on: —

### BACK-P2-008 — `Publisher.js` is read outside the mutex; a concurrent reconnect can nil it and panic the reconciler goroutine (process exit)
- Priority: P2 | Type: reliability | Area: internal/nats
- Evidence: backend/internal/nats/publisher.go:195 (no lock held)
  ```go
  ack, err := p.js.Publish(env.Subject, data, natsclient.MsgId(env.IdempotencyKey), natsclient.Context(ctx))
  ```
  while `ensureConnected` under `p.mu` does (`publisher.go:235-239`)
  ```go
  if p.conn != nil {
  	p.conn.Close()
  	p.conn = nil
  	p.js = nil
  }
  ```
  and returns an error if the re-dial fails, leaving `p.js == nil`. Callers are concurrent: request goroutines (`publishToNATSAsync`) and the minute ticker in `internal/app/router.go:184-199`, which has no `recover`. `Publisher.Close()` is never called on shutdown (no reference in `router.go`/`main.go`).
- Impact: during a NATS flap, goroutine A passes `ensureConnected`, goroutine B tears the connection down and fails to re-dial, A dereferences a nil `JetStreamContext` → panic. In the ticker goroutine that terminates the whole API gateway. Also a data race by construction (not currently exercised by tests, so `-race` is silent).
- Root cause: connection state is guarded for writes but not for the publish read path; `IsConnected()==false` during the client's own auto-reconnect (`MaxReconnects(-1)`) triggers a needless teardown.
- Fix: snapshot `js` under the lock (`js := p.js`) and return `ErrPublisherClosed`/unavailable when nil; rely on nats.go auto-reconnect instead of closing on `!IsConnected()`; add `defer recover` + logging in the reconciler loop; close the publisher from the root-context shutdown hook.
- Verification: `cd backend && go test -race -count=1 ./internal/nats/` with a test that runs `Publish` concurrently with forced reconnect failures (fake dialer) — must not panic and must be race-clean.
- Effort: S | Blast radius: low | Depends on: —

### BACK-P2-009 — Request context is not propagated on most DB calls; configured `QueryTimeout` is dead; quota checks are check-then-act
- Priority: P2 | Type: reliability | Area: repository, db
- Evidence: backend/internal/db/db.go:383-385 sets `cfg.QueryTimeout = 30 * time.Second`, and `grep -rn QueryTimeout --include=*.go .` shows no other reader. Context-less calls: 182 `.Query(`/`.QueryRow(`/`.Exec(`/`.Begin(` sites vs 65 context-aware ones (grep counts in "Checks run"). Hot-path examples: the ownership gate for every `/api/v1/bots/:instance_id/*` and `/ws/bots/*` request, backend/internal/repository/bot_instance_repository.go:201
  ```go
  err := r.db.QueryRow(r.bindQuery(query), instanceID).Scan(
  ```
  and the per-request password-change gate, backend/cmd/server/main.go:102 `conn.QueryRow(...)`. Quota: backend/internal/handlers/bot_instance_handler.go:407-416 counts, then creates at :460 with no transaction or constraint (same in quick-deploy and backtest admission).
- Impact: a slow or locked PostgreSQL (e.g. during BACK-P1-003) pins handler goroutines and pool connections with no deadline even after the client disconnects, and the 15 s shutdown drain cannot cancel them; two concurrent create requests both pass the count and exceed the quota.
- Root cause: repositories predate context plumbing; only some were converted (`*Context` variants exist next to legacy ones).
- Fix: set a server-side `statement_timeout` in the DSN/connection init as a backstop; convert the authorization hot paths first (`GetBotInstanceByInstanceID`, password-change lookup, RBAC `HasPermission`) to `QueryRowContext(c.Request.Context())`; enforce quota atomically (`INSERT ... SELECT ... WHERE (SELECT COUNT(*) ...) < $max` or an advisory lock per user). Remove or wire `QueryTimeout`.
- Verification: `cd backend && go test -race -count=1 ./internal/repository/ ./internal/handlers/`; a concurrency test firing N parallel creates asserts at most `max` rows; lint rule `noctx`/`sqlclosecheck` enabled for the converted packages.
- Effort: L | Blast radius: med | Depends on: —

### BACK-P2-010 — WebSocket relays set no read limit and one unbounded background prefetch goroutine is spawned per sync
- Priority: P2 | Type: perf | Area: routes/bot delegation
- Evidence: `grep -rn ReadLimit internal --include=*.go` → no matches; the relay reads whole frames into memory, backend/internal/routes/bot_api_delegate_routes.go:1446 `messageType, payload, readErr := src.ReadMessage()` (both directions) and :1307 for the push socket. Global `http.MaxBytesReader` (`router.go:100-103`) does not apply after hijack. backend/internal/routes/bot_api_delegate_routes.go:1380-1384
  ```go
  go func(runPK int) {
  	if prefetchErr := candleCache.PrefetchCandlesForRun(runPK, 0); prefetchErr != nil {
  ```
  is started on every `syncChildren` call for a completed run, with no context, deduplication or concurrency bound.
- Impact: any authenticated client can stream arbitrarily large WS frames that are fully buffered and forwarded to the bot with the service token (memory pressure on both services); repeated detail fetches of a completed run fan out duplicate prefetch goroutines that outlive shutdown.
- Root cause: keepalive/deadline hardening was added to the relays but not message-size limits; prefetch was written as fire-and-forget.
- Fix: `SetReadLimit` (e.g. 1 MiB client→upstream, 16 MiB upstream→client to match the HTTP cap) on both connections; route prefetch through the existing `SingleFlight` helper keyed by run id with a bounded worker and the root context.
- Verification: `cd backend && go test -race -count=1 ./internal/routes/ -run 'WS|Transport'` with a test sending an oversize frame and asserting close code 1009.
- Effort: S | Blast radius: low | Depends on: —

### BACK-P3-001 — Query values are escaped with `url.PathEscape`, allowing parameter injection into upstream query strings
- Priority: P3 | Type: bug | Area: services/bot_api_client
- Evidence: backend/internal/services/bot_api_client_extended.go:229 and :211
  ```go
  endpoint := fmt.Sprintf("/api/v1/bots/quick-deploy?instance_name=%s&auto_start=%v", url.PathEscape(instanceName), autoStart)
  ```
  `url.PathEscape` leaves `&`, `=`, `+` intact; `instanceName` is the raw `c.Query("instance_name")` (`bot_api_delegate_routes.go:3235`), `benchmark` likewise.
- Impact: `instance_name=x%26auto_start%3Dfalse` injects/overrides upstream query parameters, and legitimate names containing `&` or `+` are corrupted. Today the upstream endpoint accepts only `instance_name` and `auto_start` (`bot/src/api/v1/bot_lifecycle.py:812-817`), so impact is limited to values the caller already controls — hence P3 — but it becomes an authorization problem the moment the bot accepts another query parameter.
- Root cause: wrong escaping function for the query component.
- Fix: build queries with `url.Values{}.Encode()` (already used at `bot_api_client_extended.go:138,188`); validate `instance_name` against the same safe-segment pattern used for path params.
- Verification: `cd backend && go test -race -count=1 ./internal/services/ -run QuickDeploy` asserting the upstream request's parsed query has exactly two keys for an input containing `&`.
- Effort: S | Blast radius: low | Depends on: —

### BACK-P3-002 — Container images run as root, have no HEALTHCHECK, float on tags; toolchain versions disagree
- Priority: P3 | Type: tech-debt | Area: docker
- Evidence: docker/Dockerfile.backend:2,15,29 and docker/Dockerfile.backend-migrator:10,21
  ```dockerfile
  FROM golang:1.27-alpine AS builder
  ...
  FROM alpine:3.24
  ...
  CMD ["./server"]
  ```
  No `USER`, no `HEALTHCHECK`, no digest pin in either file. `backend/go.mod:3` says `go 1.25.0`, `references/backend-service.md` says Go 1.26, the local toolchain is `go1.26.6`, the image builds with 1.27. The server image also ships `./migrations/` (`Dockerfile.backend:24`), which is only needed for the startup auto-migrate path that the migrator image's header says must stay off.
- Impact: a container escape or RCE runs as uid 0; builds are not reproducible and CI (go.mod version) tests a different compiler than the one that produces the shipped binary.
- Root cause: minimal Dockerfiles never hardened.
- Fix: add a non-root user (`adduser -D -u 10001 app` + `USER 10001`), `HEALTHCHECK` hitting `/version`, pin base images by digest, align `go.mod`/CI/Docker on one Go minor, drop migrations from the server image once BACK-P1-003 disables auto-migrate.
- Verification: `docker build -f docker/Dockerfile.backend . && docker run --rm <img> id -u` → non-zero; `docker inspect --format '{{.Config.Healthcheck}}' <img>`.
- Effort: S | Blast radius: low | Depends on: BACK-P1-003

### BACK-P3-003 — CI has no vulnerability scan for the Go module and lint is non-gating
- Priority: P3 | Type: test | Area: ci
- Evidence: .github/workflows/bot-quality.yml:737-740 runs `go vet` and `go test -race -count=1 ./...` for backend; :857 `continue-on-error: true # phase 1: reporting-only, does not gate` on golangci-lint; `grep -n govulncheck .github/workflows/*.yml` → no matches. `backend/cmd/migrate` and `backend/internal/models` have no test files (see test output below).
- Impact: known-vulnerable dependencies (JWT, gin, nats, pgx, gorilla/websocket are all network-facing) are not detected; ~2.1k lint findings accumulate without a ratchet.
- Root cause: phase-1 reporting posture never advanced.
- Fix: add a gating `govulncheck ./...` step; gate golangci-lint on new findings only (`--new-from-rev`), starting with `errcheck`, `noctx`, `gosec`.
- Verification: CI run shows the new steps; `govulncheck ./...` locally once installed.
- Effort: S | Blast radius: low | Depends on: —

---

### BACK-P2-011 — Integration-tagged route tests never run in CI and at least 20 of them fail
- Priority: P2 | Type: test | Area: ci / routes (found during execution of BACK-P0-001)
- Evidence: `.github/workflows/bot-quality.yml:737,740`
  ```yaml
  run: go vet ./... && go vet -tags integration ./internal/routes/
  run: go test -race -count=1 ./...
  ```
  The `integration` tag is vetted but never tested. `backend/internal/routes/admin_user_routes_test.go:1` (`//go:build integration`) and the other tagged files hold the admin-user, MFA, refresh and delegated-backtest route tests.
  `cd backend && go test -tags integration -count=1 ./internal/routes/` (2026-09-19) → FAIL; first 20 failures include `TestAuth2FA_SetupAndVerifyEnablesMFA` (401, MFA lockout state shared between tests), `TestAuthRefresh_AccessTokenRejectedForRefresh` (login 401), and 15+ `TestDelegatedBacktest*` (`SQL logic error: no such function: hashtext` on the SQLite harness, 404s).
- Impact: the only tests covering admin user management, MFA setup and the delegated backtest contract give no signal; regressions in those handlers reach `master` untested.
- Root cause: the tag keeps them out of `go test ./...`, so they rotted as handlers started using PostgreSQL-only SQL (`hashtext`, advisory locks) against the in-memory SQLite harness.
- Fix: add a CI step `go test -tags integration ./internal/routes/` once green; repair the harness (register a `hashtext` SQLite function or run against the Postgres service container), isolate lockout state per test.
- Verification: `cd backend && go test -tags integration -race -count=1 ./internal/routes/` → ok.
- Effort: M | Blast radius: low | Depends on: —

## Needs verification

- **Has migration 000070 already been applied to staging/production?** Check (read-only, by an operator): `SELECT version, dirty FROM schema_migrations;` on each environment. Determines whether BACK-P1-003 is "pull it out" or "document and move on".
- **Which manifest is live — `deploy/k8s/*` (MariaDB, `DB_AUTO_MIGRATE: "true"`) or `deploy/k8s-next/*`?** `deploy/k8s/dydx-trading-bot-production.yaml:81-88` sets `DB_TYPE: "mysql"` although the backend is PostgreSQL-only. Check: `kubectl -n <ns> get deploy backend -o jsonpath='{.spec.template.spec.containers[0].env}'` and the image's effective `DB_AUTO_MIGRATE`/`APP_ENV`.
- **Effective `APP_ENV` label in production** (`prod` vs `production`) for BACK-P2-001. Check: same `kubectl` env dump; `deploy/k8s-next/platform-config.yaml:6` says `production`, `docker/Dockerfile.worker:27` and the comment at `auth_routes.go:169` say `prod`.
- **CSRF exposure when `AUTH_COOKIE_SAMESITE=none`.** `authCookieSameSite()` (`auth_routes.go:180-192`) allows `None`; handlers use `ShouldBindJSON`, which does not require `Content-Type: application/json`, and there is no CSRF token or Origin check on state-changing routes. Check: with SameSite=None configured, submit a cross-origin `<form enctype="text/plain">` whose body is valid JSON to `POST /api/v1/bots/:id/stop` and see whether it is accepted. With the default `Lax` this is not exploitable from a cross-site context.
- **What `/ws/strategies` accepts from clients.** Any authenticated user can open it (`bot_api_delegate_routes.go:3388-3391`, no role/ownership check since there is no `instance_id`) and the relay is bidirectional using the service token. Check the bot's `/ws/strategies` handler for inbound message handling and whether the stream contains other tenants' data.
- **`golang:1.27-alpine` / `alpine:3.24` tag existence and digest.** Not checkable offline. Check: `docker manifest inspect golang:1.27-alpine`.
- **Dependency vulnerabilities.** `govulncheck` and `staticcheck` are not installed in this environment and were not installed. Check: `cd backend && govulncheck ./... && staticcheck ./...`.
- **`platform.require_privileged_mfa` stored as empty string disables privileged MFA in production** (`mfa_middleware.go:38-39` maps `""` to false instead of the production default). Check: `SELECT value FROM bot_settings WHERE section='platform' AND key='require_privileged_mfa';`.
- **Rate-limit loopback bypass** (`rate_limit.go:112`): if a sidecar/local reverse proxy on 127.0.0.1 fronts the backend without setting `X-Forwarded-For`, every request is exempt. Check the actual network path (`kubectl get pod -o yaml` for sidecars; ingress controller `use-forwarded-headers`).

## Checks run

All from `/home/chris/workspace/dydx-trading-bot/backend` with `go version go1.26.6 linux/amd64`.

| Command | Result |
| --- | --- |
| `go build ./...` | exit 0, no output |
| `go vet ./...` | exit 0, no output |
| `go vet -tags integration ./internal/routes/` | exit 0, no output |
| `go test -race -count=1 ./... 2>&1 \| tail -40` | exit 0, `real 1m15.277s`; output below |
| `govulncheck ./...` | NOT RUN — tool not installed (not installed per instructions) |
| `staticcheck ./...` | NOT RUN — tool not installed (not installed per instructions) |
| `golangci-lint run ./...` | NOT RUN — not requested |

```
?   	github.com/dydx-trading-bot/backend-go/cmd/migrate	[no test files]
ok  	github.com/dydx-trading-bot/backend-go/cmd/server	1.012s
ok  	github.com/dydx-trading-bot/backend-go/config	1.010s
ok  	github.com/dydx-trading-bot/backend-go/internal/app	1.244s
ok  	github.com/dydx-trading-bot/backend-go/internal/auth	1.010s
ok  	github.com/dydx-trading-bot/backend-go/internal/db	1.013s
ok  	github.com/dydx-trading-bot/backend-go/internal/handlers	1.047s
ok  	github.com/dydx-trading-bot/backend-go/internal/middleware	1.034s
?   	github.com/dydx-trading-bot/backend-go/internal/models	[no test files]
ok  	github.com/dydx-trading-bot/backend-go/internal/nats	1.083s
ok  	github.com/dydx-trading-bot/backend-go/internal/repository	1.410s
ok  	github.com/dydx-trading-bot/backend-go/internal/routes	56.879s
ok  	github.com/dydx-trading-bot/backend-go/internal/services	1.577s
ok  	github.com/dydx-trading-bot/backend-go/internal/startup	6.259s
```

Read-only greps used as evidence (counts quoted in findings):

- `grep -rn BumpUserGeneration --include=*.go . | grep -v _test` → 3 call sites (auth_routes.go:1362, :1586; password_reset_routes.go:148).
- `grep -rn '"\(error\|details\|message\)": *err\.Error()' --include=*.go internal | grep -v _test | wc -l` → 52.
- `grep -rnE '\.(Query|QueryRow|Exec|Begin)\(' ... | wc -l` → 182 context-less DB calls; `grep -rnE '\.(QueryContext|QueryRowContext|ExecContext|BeginTx)\(' ... | wc -l` → 65.
- `grep -rn QueryTimeout --include=*.go . | grep -v _test` → only `internal/db/db.go:40,383,384` reference the field.
- `grep -rn ReconcilePendingCommands --include=*_test.go .` → no matches.
- `grep -rn ReadLimit internal --include=*.go | grep -v _test` → no matches.
- `grep -rn "TRUSTED_PROXIES\|TrustedProxies" --include=*.go --include=*.y*ml .` → only `backend/internal/app/router.go:91`.
- `git ls-files backend/coverage.out backend/bin` → empty (not tracked).

Limitations: no database, Redis, NATS or bot API was contacted; no migration was executed; secrets files (`.configkey.bin`, `run.json`, `.env*`, encrypted profiles) were not opened. Cross-service statements about the bot (`bot/src/api/v1/bot_lifecycle.py`, `bot/src/bot_instance_manager.py`) come from reading those files only.
