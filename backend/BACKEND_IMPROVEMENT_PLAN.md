# BACKEND_IMPROVEMENT_PLAN.md — Prioritized Engineering Backlog

Generated 2026-08-26 from BACKEND_AUDIT.md. Work top-down within priority; correctness before security before reliability before performance. Update `Status` (TODO / IN_PROGRESS / DONE / BLOCKED) as work proceeds.

Counts: **P0: 5 · P1: 12 · P2: 18 · P3: 9** (44 tasks total)

---

## P0 — CRITICAL

### TASK-001 — Fix invitation token Redeem/Revoke placeholder-argument mismatches
Priority: P0 · Category: Bug / Database
Problem: `Redeem` query has 5 placeholders but passes 3 args (`updated_at` and `expires_at` comparison values missing); `RevokeByTokenCode` has 3 placeholders / 2 args. On pgx both always fail.
Evidence: internal/repository/invitation_token_repo.go:210-261 (verified); invitation-only registration path auth_routes.go:498 deletes the just-created user when Redeem errors.
Risk: Invitation-only registration mode is completely broken; max_uses enforcement untestable.
Proposed solution: Pass `now, usedByUserID, now, tokenCode, now` to Redeem and `now, now, tokenCode` to Revoke. Add unit tests asserting placeholder/arg parity (count `?` vs len(args)).
Affected files: internal/repository/invitation_token_repo.go (+ test).
Validation: `go test ./internal/repository/... ./internal/routes/...`; new placeholder-parity test.
Estimated complexity: XS · Regression risk: Low · Status: DONE (2026-08-26)

### TASK-002 — Replace raw `?` placeholders on pgx in auth lockout, security events, CRM, backoffice, bootstrap, debug routes
Priority: P0 · Category: Bug / Security
Problem: Login lockout helpers (`readUserLockState`, `incrementFailedLogin`, `resetFailedLogin`, `logSecurityLoginEvent`), CRM security-events, backoffice audit-log handlers, bootstrap-admin lock reset, and the debug migrations route issue `?`-placeholder SQL directly against pgx `*sql.DB` (pgx does not translate `?`). Every statement errors at runtime; errors are swallowed/logged.
Evidence: internal/routes/auth_routes.go:677-735; internal/routes/portal_routes.go:557-560; internal/routes/backoffice_routes.go:329-336; internal/startup/bootstrap_admin.go:91-95; internal/app/router.go:279-299 (all verified; also invalid `REPLACE(?, '%', '')` expression on Postgres in debug route).
Risk: Account lockout (brute-force protection) silently disabled; `security_login_events` never written; two portal endpoints always 500; debug endpoint reports zeros.
Proposed solution: Rewrite statements with `$n` placeholders (or route through repository helpers with bindQuery). Fix `REPLACE(...)` to Postgres-compatible expression. Keep schema-evolution tolerance for the lockout columns.
Affected files: listed above (+ tests).
Validation: `go test ./...`; add unit tests for lockout increment/reset logic with a Postgres-parity placeholder checker.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-26)

### TASK-003 — Bootstrap admin: remove hardcoded default password, stop destructive reset on restart
Priority: P0 · Category: Security
Problem: When `BOOTSTRAP_ADMIN_PASSWORD` is unset the code uses `admin123` AND overwrites the existing admin's email/full name/password on every restart (`PasswordChangeRequired=false`), silently reverting operator-changed credentials. Lock-reset statements also use broken `?` SQL (overlaps TASK-002).
Evidence: internal/startup/bootstrap_admin.go:14-98 (verified).
Risk: Publicly-known admin password; privileged account takeover; operator password changes silently reverted.
Proposed solution: Fail startup (or generate+print-once random password) when no explicit `BOOTSTRAP_ADMIN_PASSWORD` in production; only set password on *create*, never on update unless a dedicated `BOOTSTRAP_ADMIN_RESET=true` is set; set `PasswordChangeRequired=true` when default is used; do not clobber email/full name.
Affected files: internal/startup/bootstrap_admin.go (+ test).
Validation: `go test ./internal/startup/...`; new tests for create/update/reset paths.
Estimated complexity: S · Regression risk: Low (dev flows may need env var) · Status: DONE (2026-08-26)

### TASK-004 — Fail closed on missing JWT secret and encryption key; fix InitAuthMiddleware nil deref
Priority: P0 · Category: Security
Problem: `resolveJWTSecret` falls back to repo-public constant whenever env/config are empty and the production baseline (only enforced when `APP_ENV=production`) didn't run; `InitAuthMiddleware` nil-checks `cfg` then dereferences it unconditionally (line 40); `secret_crypto.go` pads/truncates keys and uses an insecure default key outside production; config has `change-me-*` DB/ClickHouse/MinIO defaults.
Evidence: internal/middleware/auth_middleware.go:18-51; internal/services/secret_crypto.go:19,37-54; internal/startup/security_baseline.go; config/config.go defaults (verified).
Risk: Forgeable admin JWTs in any deployment that forgets `APP_ENV`; weak encryption of stored mnemonics.
Proposed solution: Startup fails in all environments when JWT secret missing (test env may inject ephemeral random); InitAuthMiddleware nil-guards; encryption key: require 32-byte key (or derive via HKDF from configured secret with stored salt) and refuse insecure default outside explicit dev; document env requirements.
Affected files: internal/middleware/auth_middleware.go, internal/services/secret_crypto.go, internal/startup/security_baseline.go, config/config.go (+ tests).
Validation: `go test ./...`; new startup-failure tests.
Estimated complexity: M · Regression risk: Medium (deploys must set secrets — intended) · Status: DONE (2026-08-26; encryption-key KDF hardening deferred — changing derivation would make existing stored credentials undecryptable; tracked under remaining risks)

### TASK-005 — Enforce MFA challenge at login (session step-up)
Priority: P0 · Category: Security
Problem: Login grants a full session after password only; `/2fa/verify` is enrollment-only; `RequireMFA` checks enrollment existence, never that this session completed TOTP.
Evidence: internal/routes/auth_routes.go loginHandler (verified: password → createSessionForUser); internal/middleware/mfa_middleware.go:43-81.
Risk: Password alone compromises accounts with TOTP configured — including admin (paired with wallet-mnemonic retrieval endpoint).
Proposed solution: When `user.MFAEnabled`: issue short-lived pre-auth session (or step-up token) limited to `/api/v1/auth/2fa/challenge`; verify TOTP there, then promote session to full auth (`mfa_verified_at` claim); `RequireMFA` checks `mfa_verified_at` within TTL for privileged routes. Backward-compatible: users without MFA unaffected.
Affected files: internal/routes/auth_routes.go, internal/auth/session_store.go, internal/middleware/mfa_middleware.go (+ tests).
Validation: `go test ./internal/routes/... ./internal/middleware/...`; new login-MFA flow tests.
Estimated complexity: L · Regression risk: Medium (frontend login flow must handle challenge step) · Status: DONE (2026-08-26)

---

## P1 — HIGH

### TASK-006 — Fix `UpdateTradeLog` corrupted `?0..?5` placeholders
Priority: P1 · Category: Bug / Database
Problem: `pnl = ?0, pnl_usd = ?1, ...` becomes `$100, $111, ...` after bindQuery → "there is no parameter $100". PUT endpoint 100% broken.
Evidence: internal/repository/tradelog_repo.go:148-166 (verified).
Risk: Trade-log editing entirely broken on Postgres.
Proposed solution: Plain `?` placeholders (15/15 parity); add placeholder-parity unit test.
Affected files: internal/repository/tradelog_repo.go (+ test).
Validation: `go test ./internal/repository/...`.
Estimated complexity: XS · Regression risk: Low · Status: DONE (2026-08-26)

### TASK-007 — Fix partner relationship Upsert ON CONFLICT target and List placeholders; add supporting unique index
Priority: P1 · Category: Database / Bug
Problem: `ON CONFLICT (sponsor_user_id, partner_user_id)` has no matching unique constraint (only `partner_user_id UNIQUE`); `List` uses `LIMIT $2 OFFSET $3` with 2 args.
Evidence: internal/repository/partner_relationship_repo.go:16-43, 64-74; migrations 000035/000046 (verified).
Risk: Partner/IB application approval and hierarchy listing always fail.
Proposed solution: New migration: `CREATE UNIQUE INDEX ... ON partner_relationships(sponsor_user_id, partner_user_id)` after dedup guard (semantics: partner unique already implies one row per partner — keep composite for conflict clarity or switch to `ON CONFLICT (partner_user_id)`); fix List to `$1/$2`.
Affected files: partner_relationship_repo.go, new migration (+ tests).
Validation: `go test ./internal/repository/...`; migration up/down on dev DB.
Estimated complexity: S · Regression risk: Medium (migration) · Status: DONE (2026-08-26; chose ON CONFLICT (partner_user_id) matching the existing UNIQUE constraint — zero-migration-risk; List fixed to $1/$2; regression tests added)

### TASK-008 — Wrap partner application approval in a transaction
Priority: P1 · Category: Database
Problem: Role promotion → relationship upsert → application update as 3 independent writes; partial failure leaves promoted user with pending application.
Evidence: internal/routes/portal_routes.go:325-353.
Risk: Privilege-escalation state inconsistency.
Proposed solution: Single `BeginTx` via existing `SQLExecutor` abstraction; rollback on any step.
Affected files: internal/routes/portal_routes.go (+ test).
Validation: `go test ./internal/routes/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-26; introduced shared SQLRunner interface in executor.go + WithTx on UserRepository/PartnerApplicationRepository/PartnerRelationshipRepository; reviewPartnerApplicationHandler now commits role promotion + hierarchy upsert + review status atomically)

### TASK-009 — Enforce run ownership on ALL delegated backtest routes; fail closed
Priority: P1 · Category: Security / API
Problem: `ensureBacktestRunAccess` used by only ~3 of ~40 `/api/v1/backtests/:run_id/*` endpoints (incl. DELETE/cancel/resync/artifacts); returns true when owner is NULL or sync repo nil. `POST /backtests/:run_id/create-strategy` (strategy_routes.go) never checks ownership and copies another user's strategy snapshot.
Evidence: internal/routes/bot_api_delegate_routes.go:1112-1170 usage map; internal/routes/strategy_routes.go:62-185.
Risk: Any authenticated user can read/cancel/delete other users' backtests and exfiltrate strategy configurations.
Proposed solution: Apply ownership check as group middleware on the run-scoped tree; unknown-owner runs readable only by admins; nil repo fails closed (503) for non-admins; add check in create-strategy.
Affected files: bot_api_delegate_routes.go, strategy_routes.go (+ tests).
Validation: `go test ./internal/routes/...`; add cross-user access denial tests.
Estimated complexity: M · Regression risk: Medium (frontend runs created pre-migration/unknown owner) · Status: DONE (2026-08-26; NOTE: audit overstated the gap — a group-level run_id middleware already existed at bot_api_delegate_routes.go:1908; fixes applied: helper now fails closed on nil repo (503) and unknown-owner runs (404, admin bypass retained); create-strategy now enforces ownership + request ctx propagation. REMAINING: POST /compare takes run ids in the request body whose payload shape is upstream-defined — left unenforced, documented as remaining risk.)

### TASK-010 — Delegate bot routes: Go-side ownership + stop service-token fallback for user calls
Priority: P1 · Category: Security
Problem: `/api/v1/bots/:instance_id/*` delegated routes have no ownership check; when service token is configured the caller's identity is not forwarded upstream, and on upstream 401 the client silently retries as the service identity. Fallback path also returns upstream 401 as success and blind-retries POSTs on transport errors.
Evidence: internal/routes/bot_api_delegate_routes.go:2953-3145, 1387-1392; internal/services/bot_api_client.go:444-511.
Risk: Cross-user access to live positions/alerts/jobs; upstream authz bypass; duplicate backtest/bot creation.
Proposed solution: Ownership lookup (`GetBotInstanceByInstanceID` + owner/admin check) before delegating; restrict service-token fallback to server-initiated calls only; treat fallback status ≥400 as error; retry only idempotent methods on transport errors (or add idempotency keys).
Affected files: bot_api_client.go, bot_api_delegate_routes.go (+ tests).
Validation: `go test ./internal/services/... ./internal/routes/...`.
Estimated complexity: M · Regression risk: Medium · Status: DONE (2026-08-27; both halves now closed: (1) service-token escalation removed from bot_api_client under TASK-016 work; (2) Go-side ownership middleware on the delegated /api/v1/bots/:instance_id group — admins bypass, foreign/unknown instances 404, nil registry fails closed 503; quick-deploy (no instance_id) unaffected; repo's not-found-as-error quirk mapped to 404. Regression test: TestDelegateBotRoutes_EnforceInstanceOwnership)

### TASK-011 — Trade-log CRUD: ownership scoping + persist all create fields
Priority: P1 · Category: Security / Bug
Problem: Get/Update/Delete/List by raw IDs with no user scoping anywhere; `CreateTradeLog` persists 3 fields but returns 201 with exit prices/PnL/sides it never saved; accepts arbitrary `result_id_fk`.
Evidence: internal/handlers/tradelog_handler.go:26-308; internal/services/tradelog_service.go; internal/repository/tradelog_repo.go.
Risk: Any user reads/tampers/deletes any other user's trade logs (PnL integrity); clients believe unpersisted data was saved.
Proposed solution: Thread userID through service/repo; scope every query via join to owning run/result (owner or admin bypass); persist full field set on create.
Affected files: tradelog_handler.go, tradelog_service.go, tradelog_repo.go (+ tests).
Validation: `go test ./internal/...`; cross-user denial tests.
Estimated complexity: M · Regression risk: Medium (response semantics change to truthful values) · Status: DONE (2026-08-26; owner scoping threaded through handler/service/repo via trade_logs→backtest_results→backtest_runs.user_id joins; admin bypass (scope 0); Create persists the full field set and returns truthful stored values; fixed latent br.run_id→run_id_fk column bug; sentinel errors map foreign/missing logs to 404; TestTradeLogOwnershipScoping added)

### TASK-012 — Graceful shutdown + HTTP server timeouts
Priority: P1 · Category: Reliability / DevOps
Problem: No signal handling; `router.Run` uses default `http.Server` (no ReadHeader/Read/Idle timeouts — slowloris); 5 background workers (event consumer, push hub subscriber, outbox ticker, candle prefetch, telemetry goroutines) never stopped; deferred DB close unreachable.
Evidence: cmd/server/main.go:39-114; internal/app/router.go:317-328, 127-136, 202-213; internal/services/backtest_push_hub.go:112-180.
Risk: Request drops on deploy/SIGTERM; leaked goroutines/connections; slowloris DoS.
Proposed solution: Root context cancelled on SIGTERM/SIGINT; `http.Server{ReadHeaderTimeout, ReadTimeout, IdleTimeout}` + `Shutdown(ctx)` drain; worker `Run(ctx)` + WaitGroup; close Redis/NATS/ClickHouse clients; make deferred DB close reachable.
Affected files: cmd/server/main.go, internal/app/router.go, consumer/hub/outbox services (+ tests).
Validation: `go test ./...`; manual SIGTERM drain test.
Estimated complexity: M · Regression risk: Low · Status: DONE (2026-08-26; signal.NotifyContext root ctx; http.Server with ReadHeaderTimeout 10s/ReadTimeout 60s/IdleTimeout 120s (WriteTimeout deliberately unset for SSE/WS); Shutdown drains 15s; Dependencies.RootContext wires event consumer + ICO outbox worker + hub Stop; TestRunServer_GracefulShutdownOnContextCancel added)

### TASK-013 — JetStream consumer: backoff, MaxDeliver/DLQ, ack hygiene
Priority: P1 · Category: Reliability
Problem: Any `ProcessRaw` failure (incl. permanently malformed envelopes) → immediate `msg.Nak()` hot loop; `_ = msg.Ack()`; no AckWait/MaxAckPending config; projector not idempotent so redelivery duplicates broadcasts.
Evidence: internal/services/backtest_event_consumer.go:112-166.
Risk: Pipeline wedge, CPU/log flood, duplicated WS events.
Proposed solution: `NakWithDelay` exponential backoff; terminal handling for decode errors (Ack + dead-letter metric/log); explicit AckWait/MaxDeliver durable options; log ack failures with sequence.
Affected files: backtest_event_consumer.go (+ tests).
Validation: `go test ./internal/services/... -run Consumer`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-26; malformed envelopes terminal (Ack+dead-letter) instead of infinite NAK; NakWithDelay exponential backoff from NumDelivered capped 30s; ensureEventConsumer provisions AckWait 60s/MaxDeliver 16/MaxAckPending 256 with add-or-update; ack failures logged)

### TASK-014 — Push hub: serialize per-connection writes
Priority: P1 · Category: Concurrency
Problem: `push()` writes conns concurrently from Redis subscriber and JetStream projector goroutines — gorilla/websocket permits exactly one concurrent writer → interleaved frames corrupt client streams. Sequential 5s-deadline writes also stall the consumer Fetch loop (head-of-line blocking, redelivery duplicates at default 30s AckWait).
Evidence: internal/services/backtest_push_hub.go:65-108; router.go:107-136.
Risk: Corrupted WS streams for real users; projection stalls under slow clients.
Proposed solution: Per-subscriber buffered send channel + dedicated writer goroutine (or per-conn mutex); non-blocking send drops/disconnects slowest subscribers.
Affected files: backtest_push_hub.go (+ tests).
Validation: `go test -race ./internal/services/... -run Hub`.
Estimated complexity: M · Regression risk: Low · Status: DONE (2026-08-26; hub rewritten with per-subscriber buffered channel (16) + dedicated writer goroutine — single-writer per conn fixes concurrent-write corruption; non-blocking sends disconnect slow subscribers instead of stalling the Redis subscriber/JetStream Fetch loop; Stop() disconnects everyone on shutdown; ctx-aware backoff; race detector clean)

### TASK-015 — Bound unbounded queries (candles, audit logs, positions)
Priority: P1 · Category: Performance / Database
Problem: `GetCandles` omits LIMIT when handler filter has none → full run candle history (10⁵-10⁶ rows) into RAM + JSON; `GetAuditLogsByUser` has no LIMIT (append-only table); `GetPositions` unbounded.
Evidence: internal/repository/backtest_repo.go:229-233, 333; internal/handlers/backtest_handler.go:214-221; internal/repository/auditlog_repo.go:116-124.
Risk: OOM/latency under data growth; endpoint abuse.
Proposed solution: Default+max limit in handlers (candles e.g. 5000 + cursor); repo errors on `Limit <= 0` for these endpoints; paginate per-user audit logs like ListAllAuditLogs.
Affected files: backtest_handler.go, auditlog_handler.go, backtest_repo.go, auditlog_repo.go (+ tests).
Validation: `go test ./internal/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-26; live risk fixed: GetAuditLogsByUser now LIMIT-bounded (default 200, cap 1000) through repo/service/handler; dead candle handler left as-is pending TASK-036 decision)

### TASK-016 — Bot API client hardening: URL escaping, bounded reads, retry safety
Priority: P1 · Category: Security / Reliability
Problem: Path params interpolated unescaped (`fmt.Sprintf("/api/v1/backtests/%s", runID)`) → `..%2F` rewrites upstream path; `io.ReadAll` without limit; query strings built with raw `%s`.
Evidence: internal/services/bot_api_client.go:608-788; bot_api_client_extended.go (many); :557.
Risk: Upstream path manipulation (paired with TASK-010 service-token issue = admin boundary crossing); memory exhaustion from huge upstream bodies.
Proposed solution: `url.PathEscape` every path segment (or validate IDs against `^[A-Za-z0-9_-]+$`); `url.Values.Encode()` for queries; `io.LimitReader` (e.g. 8MB like clickhouse_reader).
Affected files: bot_api_client.go, bot_api_client_extended.go (+ tests).
Validation: `go test ./internal/services/... -run BotAPIClient`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-26; 40 endpoint sites wrapped in url.PathEscape, 16MB LimitReader cap, fallback errors surfaced, non-idempotent retries removed — service-token escalation removal recorded under TASK-010)

### TASK-017 — WebSocket relay + status push keepalive (deadlines, ping/pong)
Priority: P1 · Category: Reliability
Problem: Bidirectional relay sets no read deadlines/ping-pong/write deadlines → silently dead peers leak 3 goroutines per connection forever; backtest status push handler blocks on read with no deadline.
Evidence: internal/routes/bot_api_delegate_routes.go:1230-1235, 1357-1380.
Risk: Goroutine/FD exhaustion under network churn.
Proposed solution: Standard gorilla keepalive: ping ticker (~30s), `SetReadDeadline(now+60s)` extended on pong/read both directions, `SetWriteDeadline` before relayed writes; use `DialContext` bound to request ctx.
Affected files: bot_api_delegate_routes.go (+ tests).
Validation: `go test ./internal/routes/...`; race test.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-26; relay uses DialContext bound to request ctx; read deadlines + pong handlers on both peers; write deadlines on every relayed frame; 30s WriteControl pings from a relay pinger that closes both conns on failure; status-push handler got the same keepalive so dead clients are reaped)

---

## P2 — MEDIUM

### TASK-018 — Thread context.Context through repository layer
Priority: P2 · Category: Architecture / Reliability
Problem: ~15 repos use non-context `Query/Exec`; client disconnects never cancel; `QueryTimeout` config is dead; stuck queries can exhaust the 25-conn pool.
Evidence: internal/repository/*.go (grep; task/ico repos already contextual — follow their pattern).
Risk: Pool exhaustion under load; wasted DB work.
Proposed solution: Incremental adoption: `QueryContext/ExecContext` with request ctx (handlers → services → repos); apply a default query timeout where ctx has none.
Affected files: repos + services + handlers (phased).
Validation: `go test ./...` per phase.
Estimated complexity: L · Regression risk: Medium · Status: IN_PROGRESS → Phase 1 DONE (2026-08-28; ctx-accepting variants (GetX…Context) added for the hot read paths of UserRepository (GetByID/GetByUsername/GetByEmail) and BacktestRepository (GetRunByID/GetRunOwnerID/GetRunsByUserID/CountRunsByUserID/CountActiveRunsByUserID); SQLRunner extended with the context trio; request-scoped callers migrated (login, MFA middleware, backtest list/admission/ownership); legacy signatures delegate via Background()+30s so QueryTimeout is no longer dead config. Phase 2 (write paths + remaining repos) remains open., task/ico repos are contextual exemplars. Phase-1 candidate: BacktestRepository + UserRepository hot paths; QueryTimeout stays dead until adopted)

### TASK-019 — Telemetry: fix user_id type assertion; wire batch writer
Priority: P2 · Category: Observability / Bug
Problem: `userIDVal.(string)` never matches (auth sets int) → user attribution always nil; per-request goroutine + single-row ClickHouse INSERT unbounded; existing `APIRequestEventBatchWriter` unwired and its Close/ForceFlush has lifecycle defects.
Evidence: internal/middleware/api_request_events_middleware.go:62-66, 75-104, 204-281.
Risk: Wrong/no user attribution in analytics; resource spikes; shutdown drops.
Proposed solution: Assert int (log-once on mismatch); wire batch writer into BuildRouter; fix its sync.Once close + WaitGroup flush + ticker guard.
Affected files: api_request_events_middleware.go, internal/app/router.go (+ tests).
Validation: `go test ./internal/middleware/... ./internal/app/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-27; LOWER(COALESCE(status)) removed from admission/strategy queries so the (user_id, status, created_at) indexes apply; one-time normalization migration 000068 lowercases historical statuses)

### TASK-020 — Make singleflight panic-safe (news, codex)
Priority: P2 · Category: Reliability
Problem: `call.value, call.err = fn()` without deferred cleanup — a panic in fn permanently wedges the key (all waiters + future requests block forever).
Evidence: internal/services/news_service.go:249-254; internal/services/codex_service.go:948-953.
Risk: Endpoint hard-down from a single panic.
Proposed solution: `defer` delete+close after registering; add regression test injecting panic.
Affected files: both services (+ tests).
Validation: `go test ./internal/services/...`.
Estimated complexity: XS · Regression risk: Low · Status: DONE (2026-08-27; deferred delete+close runs after registering the call, and fn executes under a recover that converts panics into errors — waiters and future requests for the key can no longer block forever, and a panicking fetch surfaces as a 500 instead of an empty success)

### TASK-021 — Candle prefetch: singleflight + bounded memory
Priority: P2 · Category: Performance
Problem: One resync triggers up to ~11 untracked `PrefetchCandlesForRun` goroutines; each materializes ALL candles for ALL markets in RAM before one Redis SET.
Evidence: internal/routes/backtest_delegation_service.go:71-122; internal/routes/bot_api_delegate_routes.go:1300-1309; internal/services/candle_cache_service.go:257-289.
Risk: Memory spikes; DB/Redis amplification; goroutine leak on shutdown.
Proposed solution: singleflight per runPK; write page-by-page keys instead of full materialization; track with WaitGroup.
Affected files: candle_cache_service.go, delegation service (+ tests).
Validation: `go test ./internal/...`.
Estimated complexity: M · Regression risk: Medium (cache layout change) · Status: DONE (2026-08-27, scoped: per-run singleflight added — one resync fan-out no longer triggers ~11 duplicate full-history loads; page-wise cache layout deferred deliberately — it changes the cache read contract; remaining risk documented)

### TASK-022 — realtime-stats cache singleflight
Priority: P2 · Category: Performance
Problem: Check-then-fetch-then-set without coalescing on hot polled path (30s TTL) → upstream stampede.
Evidence: internal/routes/bot_api_delegate_routes.go:3014-3048.
Risk: Python API load spikes.
Proposed solution: Copy existing singleflight pattern from codex/news.
Affected files: bot_api_delegate_routes.go (+ test).
Validation: `go test ./internal/routes/...`.
Estimated complexity: XS · Regression risk: Low · Status: DONE (2026-08-27; generic panic-safe services.SingleFlight[T] added and applied to the realtime-stats cache-miss path — dashboard polling no longer stampedes the bot API on TTL expiry)

### TASK-023 — Cache schema-probe results (user_repo, backtest repos)
Priority: P2 · Category: Performance / Database
Problem: `hasUserColumn` probes run up to ~9× per user read (plus Create/Update) — ~10 queries per GetByID; same detectFKColumn pattern per candles/trades/positions query.
Evidence: internal/repository/user_repo.go:86-162; backtest_repo.go:583-608; backtest_sync_repo.go:623-652.
Risk: ~10× query amplification on the hottest table.
Proposed solution: `sync.Once`-cached column sets per table (schema fixed after startup migrations).
Affected files: user_repo.go, backtest_repo.go, backtest_sync_repo.go (+ tests).
Validation: `go test ./internal/repository/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-27; shared cachedTableColumns helper keyed by DB pointer+table — user_repo/backtest repos no longer issue ~9 schema probes per read; per-test databases keyed separately)

### TASK-024 — Sync-health: replace N+1 with aggregate query
Priority: P2 · Category: Performance / Database
Problem: ~13 queries per run × limit 200 → ~2,600 queries/request; errors coerced to 0.
Evidence: internal/repository/backtest_sync_repo.go:654-788.
Risk: Endpoint meltdown as runs accumulate.
Proposed solution: Single aggregate (GROUP BY/lateral) per page; surface errors.
Affected files: backtest_sync_repo.go (+ test).
Validation: `go test ./internal/repository/...`.
Estimated complexity: M · Regression risk: Medium · Status: DONE (2026-08-27; single aggregate query with scalar subselects replaces ~13 queries/run × limit; FK columns resolved once via schema cache; nullable timestamps compared in Go for dialect portability; dead helpers removed)

### TASK-025 — Remove Postgres-incompatible CAST AS CHAR fallback
Priority: P2 · Category: Bug
Problem: Drifted-schema fallback casts status/config to `CHAR` (length-1 in PG) → silently returns "R"/truncated JSON.
Evidence: internal/repository/bot_instance_repository.go:74-98.
Risk: Corrupt data displayed instead of clear error.
Proposed solution: Use `::text` or drop the compat path (migration 000022 guarantees schema).
Affected files: bot_instance_repository.go (+ test).
Validation: `go test ./internal/repository/...`.
Estimated complexity: XS · Regression risk: Low · Status: DONE (2026-08-27; CAST(... AS CHAR) → CAST(... AS TEXT); Postgres CHAR defaults to length 1, silently truncating status/config to one character on the drifted-schema fallback path)

### TASK-026 — Task commands: idempotent create + pending reconciler
Priority: P2 · Category: Reliability
Problem: Duplicate idempotency key surfaces as 500 instead of returning existing row; async publish goroutines unbounded/untracked; failed publishes stuck `pending` forever (no reconciler).
Evidence: internal/repository/task_repository.go:37-64; internal/services/nats_command_service.go:127-282.
Risk: Lost commands (bot actions silently never execute); goroutine pileup when NATS down.
Proposed solution: `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING` + fetch-existing; bound publish concurrency + WaitGroup; periodic reconcile of stale `pending` (JetStream Msg-Id dedupe makes re-publish safe).
Affected files: task_repository.go, nats_command_service.go (+ tests).
Validation: `go test ./internal/...`.
Estimated complexity: M · Regression risk: Medium · Status: DONE (2026-08-27; ON CONFLICT idempotent create returns the existing command on retries; ListTaskCommandsPendingSince + ReconcilePendingCommands re-publish stale pendings with JetStream Msg-Id dedupe; reconciler ticker wired to the shutdown context)

### TASK-027 — Partner commission metrics: bucket default periods; aggregate latest per user
Priority: P2 · Category: Database / Correctness (money)
Problem: Default periods derived from `time.Now()` at µs precision → new row per ingest for the same logical window; `AggregateByUsers` SUMs all rows → inflated payouts.
Evidence: internal/routes/portal_routes.go:641-646; internal/repository/partner_commission_metric_repo.go:36, 167-204.
Risk: Financial reporting overstates commissions.
Proposed solution: Round periods to day/month boundaries (or require explicit); aggregate `DISTINCT ON (user_id)` latest-period rows.
Affected files: portal_routes.go, partner_commission_metric_repo.go (+ tests).
Validation: `go test ./internal/routes/... ./internal/repository/...`.
Estimated complexity: S · Regression risk: Medium (money semantics — verify business intent) · Status: DONE (2026-08-27; periods truncated to UTC day boundaries with start<end validation; AggregateByUsers sums DISTINCT ON latest period per user — repeated ingests no longer inflate commission totals)

### TASK-028 — Request body size limits + shared pagination clamping
Priority: P2 · Category: API / Security
Problem: No `MaxBytesReader` anywhere (OOM via large bodies, incl. unauth endpoints); limit params on several delegated endpoints accept negative/oversized values (`/:run_id/trades`, `/logs`, alerts/jobs/history); auditlog limit has no ceiling.
Evidence: grep MaxBytesReader → 0 hits; bot_api_delegate_routes.go:2497-2506, 2425-2429, 2988-3094; auditlog_handler.go:157-196.
Risk: DoS vectors; unbounded DB scans.
Proposed solution: Global `http.MaxBytesReader` (e.g. 10MB; tighter where sensible); shared `clampInt(name, def, min, max)` helper applied to all list endpoints.
Affected files: app/router.go, delegate routes, auditlog handler (+ tests).
Validation: `go test ./internal/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-27; global http.MaxBytesReader 10MB middleware; parseBoundedIntQuery applied to limit (1..1000), days (1..365), hours (1..720) across delegated endpoints; analytics hours capped at 720)

### TASK-029 — Drop query-string access token; default-deny CORS
Priority: P2 · Category: Security
Problem: `?access_token=` accepted (leaks to logs/history/Referer); unconfigured non-prod CORS reflects credentials for any origin.
Evidence: internal/middleware/auth_token.go:24-26; internal/middleware/middleware.go:27, 66-69.
Risk: Token leakage; credentialed cross-origin reads in misconfigured deploys.
Proposed solution: Remove query-param path (coordinate frontend first — check usage); CORS allowlist-only with credentials echo only for allowed origins.
Affected files: auth_token.go, middleware.go (+ tests).
Validation: `go test ./internal/middleware/...`; frontend grep for `access_token=` query usage.
Estimated complexity: S · Regression risk: Medium (may break WS clients using query tokens — provide migration note) · Status: DONE (2026-08-27; query-string access_token now accepted ONLY on WebSocket upgrade requests — browsers cannot set WS headers, and the frontend's WS URLs use it; all other requests must use Authorization/cookies. CORS default-deny: unconfigured non-prod allows only loopback origins instead of every origin)

### TASK-030 — Gate analytics routes with permission
Priority: P2 · Category: Security
Problem: Platform-wide live positions/trade summaries/worker metrics/api-request analytics require only RequireAuth.
Evidence: internal/app/analytics_routes.go:33-71.
Risk: Tenant data exposure to any account.
Proposed solution: `RequirePermission(database, "analytics.read")` or admin gate (confirm intended audience with product owner).
Affected files: analytics_routes.go (+ tests).
Validation: `go test ./internal/app/...`.
Estimated complexity: XS · Regression risk: Medium (dashboard may rely on it) · Status: DONE (2026-08-27; routes now RequirePermission(analytics.read) + analytics.read added to admin/super_admin fallback maps so operators keep access; other roles grantable via RBAC — dashboards needing it must grant the permission)

### TASK-031 — Revoke sessions/refresh tokens on password change; invalidate old refresh on rotation
Priority: P2 · Category: Security
Problem: Password change leaves existing sessions + attacker's refresh cookie valid for full TTL; rotation issues new refresh JWT without invalidating old.
Evidence: internal/routes/auth_routes.go:903-1001, 1114-1126.
Risk: Post-compromise persistence.
Proposed solution: Delete user's sessions from store + clear cookies on password change; server-side refresh-token registry (Redis) with reuse detection.
Affected files: auth_routes.go, internal/auth/session_store.go (+ tests).
Validation: `go test ./internal/routes/... ./internal/auth/...`.
Estimated complexity: M · Regression risk: Medium · Status: DONE (2026-08-27, scoped: password change bumps a per-user session generation — all existing sessions for the account die with the attacker's; cookies cleared; new sessions unaffected; unit test covers revoke/issue/other-user. REMAINING: legacy refresh JWTs still exchange without revocation — needs the server-side registry called out in remaining risks)

### TASK-032 — db.go wrapper ctx-cancellation fix; migration Force() guard tightening
Priority: P2 · Category: Reliability
Problem: `Query/QueryRow/BeginTx` wrappers `defer cancel()` before caller consumes rows (latent, currently unused); migration recovery Force()s half-applied migrations as complete outside production; dead duplicate-instance recovery block.
Evidence: internal/db/db.go:261-288, 327-330, 419-523.
Risk: Future adopters hit "context canceled"; dev/staging schema drift.
Proposed solution: Caller-owned ctx; restrict Force to clean dirty-flag recovery; delete dead block; fix nil-DB `Close()` flag.
Affected files: internal/db/db.go (+ tests).
Validation: `go test ./internal/db/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-27; Query/QueryRow/Exec converted to caller-context signatures (self-cancelling wrappers removed), BeginTx no longer kills the tx after BEGIN, Close marks closed even on nil DB, dead duplicate-instance migration recovery block deleted)

### TASK-033 — Registration: replace compensation-delete with transaction
Priority: P2 · Category: Database
Problem: User INSERT then token Redeem; failure path deletes user (can itself fail → orphan user; invite consumed-or-not non-atomic).
Evidence: internal/routes/auth_routes.go:482-516.
Risk: Orphan users; invite accounting drift.
Proposed solution: Single tx: INSERT user + UPDATE token.
Affected files: auth_routes.go (+ tests).
Validation: `go test ./internal/routes/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-27; user INSERT + token Redeem commit atomically in one transaction; compensation-delete path removed; InvitationTokenRepository gained WithTx)

### TASK-034 — LOWER(status) index-defeating admission query
Priority: P2 · Category: Performance / Database
Problem: `CountActiveRunsByUserID`/`GetRunsByStrategyID` wrap status in `LOWER(COALESCE(...))` defeating the (user_id, status, created_at) partial indexes; runs on every backtest submission.
Evidence: internal/repository/backtest_repo.go:934-947, 984-999.
Risk: Admission check degrades with run volume.
Proposed solution: Trust normalized-lowercase writes (write path already normalizes); one-time `UPDATE ... SET status=LOWER(status)` migration; keep `LOWER()` only on the write side.
Affected files: backtest_repo.go + migration (+ tests).
Validation: `go test ./internal/repository/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-27; user INSERT + token Redeem now commit atomically; compensation-delete path removed; InvitationTokenRepository gained WithTx)

### TASK-035 — Async NATS publish bounding + publisher ctx use
Priority: P2 · Category: Reliability
Problem: Unbounded fire-and-forget goroutines per command (10s NATS timeout each); Publisher ignores caller ctx; `AddStream` round-trip on every publish.
Evidence: internal/services/nats_command_service.go:161-282; internal/nats/publisher.go:182-269.
Risk: Goroutine pileup; wasted round-trips.
Proposed solution: Semaphore-bounded worker; cache ensured streams; honor ctx.
Affected files: nats_command_service.go, publisher.go (+ tests).
Validation: `go test ./internal/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-27; CreateTaskCommand uses ON CONFLICT (idempotency_key) DO NOTHING + fetch-existing so retries return the original command; ListTaskCommandsPendingSince + ReconcilePendingCommands re-publish stale pendings (JetStream Msg-Id dedupe makes it safe); reconciler ticker wired to the shutdown context)

---

## P3 — LOW

### TASK-036 — Remove dead/unwired code: backtest_routes.go registration path, BotAPIClient.SetToken
Priority: P3 · Category: Architecture
Problem: `RegisterBacktestRoutes*` never called (would panic gin on duplicate registration; carries IDOR-prone unscoped handlers); `SetToken` has no production callers.
Evidence: internal/routes/backtest_routes.go; internal/services/bot_api_client.go:303; grep confirms no callers.
Risk: Future wiring introduces panics/IDOR.
Proposed solution: Delete dead files/functions or wire intentionally with ownership checks (coordinate TASK-009 first).
Affected files: backtest_routes.go, backtest_handler.go dead paths, bot_api_client.go.
Validation: `go build ./... && go test ./...`.
Estimated complexity: XS · Regression risk: Low · Status: DONE (2026-08-28; unwired backtest_routes.go + dead backtest_handler.go deleted (APIResponse preserved in its own file), BotAPIClient.SetToken removed)

### TASK-037 — Unify response envelopes + stop leaking internal errors
Priority: P3 · Category: API
Problem: 3+ envelope shapes across domains; `err.Error()` echoed to clients on many 500s; wrong status codes (400/404 for infra failures; 500 for user errors in ICO handlers; 200 for creates).
Evidence: handlers/routes sweep (see audit §3 P3).
Risk: Client integration fragility; information disclosure.
Proposed solution: Domain-by-domain normalization to `{success,message,data,timestamp}` + generic 500 text with trace_id; classify 4xx vs 5xx via sentinel errors.
Affected files: multiple handlers/routes (phased).
Validation: `go test ./...` + contract-lock tests.
Estimated complexity: L · Regression risk: Medium · Status: DONE (2026-08-28, scoped: 32 five-hundred-response sites across portal/backoffice/admin routes no longer echo internal error detail — detail goes to server logs, clients get the fixed message; full envelope unification DEFERRED as frontend-breaking, tracked in remaining risks)

### TASK-038 — Time/UTC consistency + candle end-date boundary
Priority: P3 · Category: Bug
Problem: Services stamp `time.Now()` local while handlers use UTC; candle end-date filter excludes the entire end day (midnight boundary); zoneless parse assumes UTC.
Evidence: key_service.go:91-92, strategy_service.go, tradelog_service.go:33-34; backtest_repo.go:224-227; bot_api_delegate_routes.go:867-885.
Risk: Off-by-one-day filters; inconsistent records.
Proposed solution: `.UTC()` everywhere; end-date `+24h` exclusive bound; document timestamp contract with Python API.
Affected files: services + repos (+ tests).
Validation: `go test ./internal/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-28; service-layer timestamps normalized to UTC (12 sites); candle end-date boundary had no live path after TASK-036 removed the dead handler — documented)

### TASK-039 — Migrate USD money columns to NUMERIC (phased)
Priority: P3 · Category: Database / Correctness (money)
Problem: REAL (float4, ~6 sig digits) for balances/PnL in backtest tables; DOUBLE PRECISION for commissions; SUM aggregation loses cents.
Evidence: migrations 000010/000011/000013/000014/000017/000023/000024/000035; models.go float64 fields.
Risk: Financial reporting drift.
Proposed solution: Phase 1: new/edited columns NUMERIC(20,8); Phase 2: ALTER ... USING on hottest aggregates (commissions, total_pnl_usd, bot_trades.pnl) with backfill verification; scan via decimal type where precision matters.
Affected files: migrations, models, repos (phased).
Validation: migration rehearsal on staging snapshot; value-equality checks.
Estimated complexity: XL · Regression risk: High (data migration) · Status: DONE (2026-08-28, Phase 1: migration 000069 converts the payout-critical partner_commission_metrics USD columns DOUBLE PRECISION → NUMERIC(20,8) with reversible down; models keep float64 scanning. Phase 2 (backtest_runs/bot_trades REAL columns) deferred pending staging rehearsal)

### TASK-040 — bindQuery hardening / retirement
Priority: P3 · Category: Maintainability
Problem: Naive `?`-scanner corrupted `?0` into `$100` silently and would corrupt literal `?` inside strings; per-repo duplicated bindQuery.
Evidence: internal/repository/* bindQuery copies; tradelog incident (TASK-006).
Risk: Repeat incidents.
Proposed solution: Central shared implementation with literal-aware scanning; lint rule/tests asserting no `?\d` patterns; long-term migrate query strings to `$n` natively.
Affected files: repos (+ shared helper + tests).
Validation: `go test ./internal/repository/...`.
Estimated complexity: M · Regression risk: Low · Status: DONE (2026-08-28; single literal-aware bindPlaceholders implementation shared by all 15 repository bindQuery methods — ? inside string literals no longer corrupts, and the ?0-style accident class is centralized for future retirement)

### TASK-041 — Misc security/ops polish
Priority: P3 · Category: Security / Observability
Problem: Masked secret reveals 8 chars (first4+last4); Mailgun webhook accepts future-dated timestamps; Telegram preflight `http.Post` (no timeout, token in URL); rate-limiter bucket growth + unsynchronized counter; `GetCacheStats` always "operational"; debug headers endpoint echoes all headers; username enumeration messages; registration password min 6 vs change min 8.
Evidence: secret_crypto.go:111-121; ico_mailgun_webhook_handler.go:109; telegram_service.go:451-492; rate_limit.go:39-49, 87-103; cache_service.go:214-226; app/router.go:221-226; auth_routes.go:71, 791-798.
Risk: Low individually; hardening debt.
Proposed solution: Item-by-item small fixes as listed in audit.
Affected files: as listed.
Validation: `go test ./internal/...`.
Estimated complexity: M · Regression risk: Low · Status: DONE (2026-08-28; secret masks show last-4 only; Mailgun webhook window two-sided; Telegram API calls bounded by a 10s client; rate-limiter cleanup interval const (race removed); GetCacheStats truthful degraded status; debug routes admin-gated; registration password min aligned to 8; usernames dropped from failed-login logs)

### TASK-042 — Backtest sync: batch upserts in transactions; per-run lock note
Priority: P3 · Category: Database
Problem: Row-by-row `db.Exec` upserts for trades/positions/candles (N implicit transactions, partial materialization on failure); per-run mutex is per-process only (ineffective across replicas).
Evidence: internal/repository/backtest_sync_repo.go:335-594, 167-178.
Risk: Slow syncs; cross-replica interleaving.
Proposed solution: `BeginTx` per batch or multi-row INSERT via unnest; document/accept lock scope.
Affected files: backtest_sync_repo.go (+ tests).
Validation: `go test ./internal/repository/...`.
Estimated complexity: M · Regression risk: Medium · Status: DONE (2026-08-28; trades/positions/candles sync batches each commit in one transaction — mid-list failures can no longer leave partially materialized runs)

### TASK-043 — ICO outbox hardening (claim semantics, doc at-least-once)
Priority: P3 · Category: Reliability
Problem: `ListPendingOutbox` without `FOR UPDATE SKIP LOCKED`/claim; `MarkOutboxSent` by id only; duplicate-send window after crash; per-batch 20s ctx can abort mid-batch.
Evidence: internal/repository/ico_whitelist_repo.go:396-466; internal/app/router.go:206-213.
Risk: Duplicate emails (already possible); multi-replica double-send.
Proposed solution: Claim column or SKIP LOCKED; per-entry timeout; document at-least-once.
Affected files: ico_whitelist_repo.go, outbox service (+ tests).
Validation: `go test ./internal/...`.
Estimated complexity: S · Regression risk: Low · Status: DONE (2026-08-28; outbox sent/failed transitions guarded by status IN ('pending','retry') so bookkeeping is single-writer across pollers; at-least-once delivery documented)

### TASK-044 — Add Postgres-backed integration tests for critical SQL paths
Priority: P3 · Category: Testing
Problem: sqlmock tests cannot catch placeholder dialect/arg-count bugs (this audit found 6 shipped broken statements).
Evidence: A1-A6 findings all green in CI.
Risk: Repeat of shipped-broken SQL.
Proposed solution: Integration test harness (dockerized PG; skip when unavailable) covering: invitation redeem/revoke, login lockout, partner upsert/list, trade-log update, delegated pagination queries.
Affected files: new integration test files; CI wiring (optional local).
Validation: `go test -tags=integration ./...` (or env-gated).
Estimated complexity: L · Regression risk: None (test-only) · Status: DONE (2026-08-28; env-gated Postgres harness in postgres_critical_paths_test.go covering invitation redeem/revoke, partner upsert/list, trade-log update — the exact bug class sqlmock hid. Skips green without POSTGRES_TEST_DSN; local PG lacked credentials for a live run)

---

## Execution log

| Task | Status | Summary |
|------|--------|---------|
| TASK-001 | DONE | Redeem/Revoke arg-count fixed (invitation-only registration un-broken). Regression tests added in internal/repository/invitation_token_repo_test.go (sqlite in-memory; sqlite natively rejects arg-count mismatches, so the bug class is now guarded). Validation: targeted tests + repository/routes packages green. |
| TASK-002 | DONE | All 6 raw-`?` sites converted to `$n` (auth lockout, security events, CRM, backoffice, bootstrap lock-reset, debug route); incrementFailedLogin arg order also corrected (was threshold/time/id shuffled). Validation: build/vet + routes/app/startup/repository packages green (forced rerun). Note: modernc sqlite accepts `$n` params, so dialect compatibility retained. |
| TASK-003 | DONE | Bootstrap admin contract rewritten: production requires BOOTSTRAP_ADMIN_PASSWORD (fail fast); dev generates random one-time password (logged once, rotation required); restarts no longer clobber password/email/full name unless BOOTSTRAP_ADMIN_RESET_PASSWORD=true; admin flags still re-asserted; lock state still reset. legacy "admin123" can never authenticate. 5 tests in bootstrap_admin_test.go. |
| TASK-004 | DONE | Shared fail-closed JWT secret resolution in internal/auth/jwt_secret.go used by BOTH middleware and token service (previously two independent managers with repo-public placeholder fallback); config no longer injects placeholder default; production fatals on missing secret; non-production uses process-lifetime ephemeral random secret + warning; InitAuthMiddleware nil-cfg deref fixed. Validation: full go test ./... green. |
| TASK-006 | DONE | UpdateTradeLog placeholders fixed (15/15 parity); regression test TestUpdateTradeLog_PersistsAllFields (sqlite). |
| TASK-007 | DONE | Upsert → ON CONFLICT (partner_user_id) matching existing UNIQUE constraint (zero-migration-risk); List placeholders fixed; regression tests for upsert idempotency + pagination. |
| TASK-008 | DONE | SQLRunner interface + WithTx on 3 repos; approval flow (role promotion + hierarchy upsert + review status) now single transaction with rollback-on-error; non-approve path unchanged. |
| TASK-009 | DONE (partial — /compare body enforcement deferred, see task entry) | ensureBacktestRunAccess fails closed: nil repo → 503, unknown owner → 404 (admins bypass); create-strategy enforces ownership + gains request-context cancellation. NOTE: coverage was better than audited — group middleware already guarded all :run_id param routes. |
| TASK-010 | DONE | Service-token escalation removed from bot_api_client (401 on user token never retried as service identity); fallback errors surfaced; non-idempotent retries removed. Ownership middleware added to delegated /api/v1/bots/:instance_id routes (admin bypass; foreign/unknown 404; nil registry 503); regression test covers foreign/unknown/owner/admin. |
| TASK-015 | DONE | Per-user audit-log listing bounded (limit param, default 200, cap 1000) end-to-end. |
| TASK-016 | DONE | All 40 upstream endpoint constructions wrap path params in url.PathEscape; response bodies capped at 16MB via LimitReader with explicit oversize error. |
| TASK-005 | DONE | Login-time MFA challenge implemented: SessionData gained MFARequired/MFAVerifiedAt (+MFAPending()); RequireAuth rejects pending sessions everywhere with 401 code=mfa_challenge_required (the code the frontend already handles on privileged routes); new POST /api/v1/auth/2fa/challenge (RequireAuthAllowPendingMFA) verifies TOTP, promotes the session to the full TTL, and only then issues the refresh cookie/login response that the MFA login branch deliberately withheld; pending sessions live max 5 minutes and burn after 5 bad codes; users without MFA log in exactly as before. 5 end-to-end tests in auth_routes_login_mfa_test.go. Also fixed 5 pre-existing `:=` compile errors in integration-tagged test files that blocked `go vet -tags integration`. Validation: full go test ./... green, -race green, integration-tagged 2FA tests green. FRONTEND FOLLOW-UP REQUIRED: login page must handle `mfa_required: true` responses by prompting for the 6-digit code and posting to /api/v1/auth/2fa/challenge. |
| TASK-011 | DONE | Trade-log CRUD fully owner-scoped (handler→service→repo) via run-ownership joins with admin bypass; Create persists all fields (phantom-response bug fixed); latent `br.run_id` column bug fixed; ownership scoping test added. |
| TASK-012 | DONE | SIGTERM/SIGINT → root ctx; http.Server timeouts (ReadHeader 10s/Read 60s/Idle 120s; no Write for SSE/WS); 15s Shutdown drain; event consumer, ICO outbox worker, push hub all stop on ctx cancellation; graceful-shutdown regression test added. |
| TASK-013 | DONE | Malformed JetStream envelopes now terminal (Ack + dead-letter) instead of infinite NAK hot-loop; NakWithDelay exponential backoff from NumDelivered (0.5s→30s cap); durable consumer provisioned with AckWait 60s/MaxDeliver 16/MaxAckPending 256; ack failures logged. |
| TASK-014 | DONE | Push hub rewritten: per-subscriber buffered channel + dedicated writer goroutine (single writer per conn — fixes concurrent-write frame corruption); non-blocking sends disconnect slow subscribers instead of stalling projection; Stop() for shutdown; race detector clean. |
| TASK-017 | DONE | WS relay: DialContext bound to request ctx, read deadlines + pong handlers both directions, write deadlines on all frames, 30s WriteControl keepalive pings with dual-close on failure; backtest status-push handler reaps dead clients the same way. |
| TASK-010 | DONE (fully, 2026-08-27) | Ownership middleware on delegated /api/v1/bots/:instance_id group: admins bypass, foreign/unknown instances 404, nil registry 503, quick-deploy unaffected; repo not-found-as-error mapped to 404. TestDelegateBotRoutes_EnforceInstanceOwnership covers foreign/unknown/owner/admin. |
| TASK-020 | DONE | News/codex singleflight made panic-safe: deferred cleanup + recover→error; a panicking fetch no longer wedges the key or returns empty success to waiters. |
| TASK-025 | DONE | bot_instances compat fallback: CAST AS CHAR → CAST AS TEXT (length-1 truncation on Postgres fixed). |
| P2 batch (2026-08-27) | DONE | TASK-022 generic panic-safe SingleFlight + realtime-stats coalescing; TASK-023 shared schema-probe cache (DB-pointer keyed); TASK-024 sync-health N+1 → single aggregate query (~13 q/run → 1 total); TASK-026 idempotent command create + pending reconciler ticker; TASK-027 commission periods day-bucketed + DISTINCT-ON aggregation (money correctness); TASK-028 10MB global body cap + bounded limit/days/hours parsing; TASK-029 query-token restricted to WS upgrades + loopback-only default CORS; TASK-030 analytics permission gate (analytics.read, admin fallback); TASK-031 password-change session revocation via generation counters (unit-tested); TASK-032 db.Database caller-context wrappers + Close fix + dead recovery removed; TASK-033 registration transaction; TASK-034 LOWER(status) removed + normalization migration 000068; TASK-035 NATS publish bounding (16-slot limiter) + publisher ctx honoring + stream-ensure caching; TASK-019 telemetry user_id int fix + batch writer wired with safe lifecycle; TASK-021 candle prefetch singleflight (page-wise layout deferred). TASK-018 DEFERRED with phase plan. |
| P3 batch (2026-08-28) | DONE | TASK-036 dead code removed; TASK-037 500-response error-detail leaks scrubbed (32 sites, envelope unification deferred); TASK-038 UTC normalization; TASK-039 Phase-1 NUMERIC migration 000069 (commissions); TASK-040 shared literal-aware bindPlaceholders (15 repos); TASK-041 misc polish (mask/mailgun/telegram/limiter/cache-stats/debug-gate/password-min/log-hygiene); TASK-042 sync batches transactional; TASK-043 outbox claim guards; TASK-044 env-gated Postgres critical-path harness. TASK-018 remains DEFERRED with phase plan. Validation: build/vet/full tests/race/integration-tag all green. |
| Follow-up batch (2026-08-28) | DONE | Frontend MFA login step (api.completeMfaChallenge + store mfaChallengeRequired + Login.tsx TOTP prompt; tsc+lint green). Refresh-JWT revocation registry: SessionGen claim bound to session generation at issuance, refresh rejects stale generations with code=token_revoked (regression test). TASK-018 Phase 1 ctx-through-repos on hot paths. CI backend-tests job added with Postgres service + POSTGRES_TEST_DSN (closes the no-backend-CI gap). Migration 000070 NUMERIC Phase 2 written (NOT REHEARSED — deploy only after staging rehearsal). Frontend WS query-token usage verified compatible. |
