# executionlab — Bot (Python) Execution Plan

**Project:** executionlab  
**Project teams:** Backend, Frontend, Bot / Python  
**This list:** Bot / Python  
**Source:** uploaded app-flow analysis package, generated 2026-06-21

---

## 1. Brutal summary

The bot service is not production-hard enough yet. The most dangerous problems are not UI polish or small code cleanup. The dangerous problems are security gaps, process-local state, non-transactional trading state, weak runtime ownership, and misleading API contracts.

The current architecture has a working control plane, managed bot subprocesses, Celery backtests, MariaDB persistence, Redis coordination, dYdX integrations, Telegram alerts, and WebSocket/realtime APIs. That is enough to operate a bot. It is not enough to safely scale or trust the system under failure without fixing the items below.

The execution plan must start with control-plane safety, then trading-state correctness, then reliability/observability, then refactoring. Refactoring first would be wasted effort because it would make the code prettier while the business risk stays alive.

---

## 2. Planning model

### Team split

| Team | Ownership |
|---|---|
| Bot / Python | Trading runtime, bot manager, backtests, Celery workers, dYdX integration, runtime state, risk controls, persistence correctness |
| Backend | API contracts, auth, database/migrations, Redis/Celery infrastructure, deployment ownership, service-token policy |
| Frontend | Dashboard state, websocket behaviour, operator screens, error messages, runtime control UX |

### Delivery phases

| Phase | Goal | Exit criteria |
|---|---|---|
| Phase 0 — Freeze and prove | Stop unknown damage | Ingress/auth verified, production bypass impossible, unsafe routes protected |
| Phase 1 — Trading safety | Prevent wrong exposure and false state | Exit confirmation, tracked-state reconciliation, risk control matrix tested |
| Phase 2 — Runtime reliability | Make runtime deterministic | Single owner/leader rules, Celery/Redis/backtest lifecycle hardened |
| Phase 3 — Observability | Operators can trust the screen | Freshness, task health, orphan state, websocket delivery visible |
| Phase 4 — Cleanup/refactor | Reduce blast radius | Large modules split only after tests lock behaviour |

---

## 3. ClickUp task categories

| Category | Priority | Why it matters |
|---|---:|---|
| Security and access control | Critical | Exposed backtest mutation/control routes are unacceptable |
| Trading correctness and risk controls | Critical | The system can report safe/closed while exposure may still exist |
| Runtime ownership and distributed state | High | Process-local state breaks with multiple workers/replicas |
| Backtest and Celery reliability | High | Expensive jobs need durable control and predictable recovery |
| Data consistency and migrations | High | `create_all` plus Alembic and duplicate schemas can hide drift |
| Realtime/WebSocket reliability | High | Dashboards can show empty/stale data while looking healthy |
| Observability and operations | Medium | Operators need actionable failure signals, not logs only |
| Refactoring and maintainability | Medium | Large mixed modules are a delivery risk, but not first priority |

---

## 4. Bot / Python task backlog

### Epic 1 — Control-plane security hardening

#### BOT-SEC-01 — Protect all backtest routes with executable auth
**Priority:** Urgent  
**Owner:** Bot / Python + Backend  
**Problem:** Several `/api/v1/backtests*` routes appear Bearer-protected in OpenAPI but do not declare FastAPI auth dependencies. That is a useless security story: documentation is not enforcement.

**Scope**
- Add router-level or route-level `Depends(get_current_active_user)` for normal backtest reads/mutations.
- Keep admin-only operations behind `Depends(get_admin_user)`.
- Add tests proving unauthenticated requests return 401/403.
- Verify ingress/proxy is not the only protection.

**Acceptance criteria**
- Unauthenticated create/list/detail/cancel/pause/resume/restart/delete backtest calls fail.
- Admin aliases remain admin-only.
- OpenAPI and executable dependencies match.

---

#### BOT-SEC-02 — Kill unsafe production auth bypass
**Priority:** Urgent  
**Owner:** Backend + Bot / Python  
**Problem:** `API_BYPASS_AUTH=true` is rejected only when `ENVIRONMENT == production`. If someone deploys with `prod`, `live`, `mainnet`, or a typo, protected-route auth can be bypassed.

**Scope**
- Normalize environment names.
- Fail closed for production-like environments.
- Add startup tests for `production`, `prod`, `live`, `mainnet`.

**Acceptance criteria**
- Auth bypass cannot start in any production-like environment.
- Startup error clearly explains the invalid configuration.

---

#### BOT-SEC-03 — Remove JWT/service tokens from WebSocket query string auth
**Priority:** High  
**Owner:** Backend + Frontend + Bot / Python  
**Problem:** WebSocket auth accepts `access_token` in query params. Query strings leak through logs, proxies, browser history, and monitoring tools.

**Scope**
- Support Authorization header/subprotocol token flow.
- Keep query auth only as temporary deprecated compatibility if required.
- Redact query strings in logs immediately.
- Update frontend websocket connection code.

**Acceptance criteria**
- New frontend uses header/subprotocol auth.
- Query-token usage logs a deprecation warning or is removed.
- Proxy/API logs never print token query values.

---

#### BOT-SEC-04 — Stop storing bot mnemonic/credentials as plain JSON
**Priority:** Urgent  
**Owner:** Bot / Python + Backend  
**Problem:** Signing credentials in `bot_instances.config` are high-value secrets. Plain JSON in DB/backups is unacceptable for a trading system.

**Scope**
- Identify all fields containing mnemonic, wallet, node credentials, Telegram tokens.
- Encrypt secrets at application layer or move to a secret manager.
- Redact logs, API responses, snapshots, and debug dumps.
- Add rotation plan.

**Acceptance criteria**
- DB dump does not expose mnemonic or signing secrets.
- Secrets are never returned by API except through explicit redacted forms.
- Existing rows have a migration path.

---

### Epic 2 — Trading safety and state correctness

#### BOT-TRD-01 — Confirm exchange fill/flat state before marking exits closed
**Priority:** Urgent  
**Owner:** Bot / Python  
**Problem:** Exit flow marks trades/positions closed after reduce-only close orders are submitted, not after fills/flat position confirmation. That is dangerous. The app can tell operators exposure is closed while the exchange still has open risk.

**Scope**
- After each close order, poll fills/positions until confirmed or timeout.
- Persist intermediate states: `CLOSING`, `PARTIALLY_CLOSED`, `CLOSE_SUBMITTED`, `CLOSE_CONFIRMED`, `ORPHANED_EXIT_FAILED`.
- Reconcile exchange positions before deleting tracked state.
- Add tests for partial close, second leg failure, timeout, and stale fill response.

**Acceptance criteria**
- No trade/position is marked closed until exchange exposure is confirmed flat.
- Failed/partial exits remain visible and recoverable.
- Telegram/API clearly identify orphan exposure.

---

#### BOT-TRD-02 — Build live risk-control matrix and enforce missing controls
**Priority:** Urgent  
**Owner:** Bot / Python  
**Problem:** Config fields exist for `max_positions`, drawdown, stop-loss, take-profit, trailing-stop, and timeout, but the traced live flow does not prove they are enforced. That is worse than missing fields because it creates false confidence.

**Scope**
- Create matrix: config field → code path → entry/exit enforcement → test.
- Add missing enforcement for max positions, per-pair exposure, drawdown, stop-loss, take-profit, trailing stop, and timeout where required.
- Reject unsupported fields at config validation level or mark them visibly unsupported.

**Acceptance criteria**
- Every risk field is either enforced and tested or explicitly rejected.
- UI/backend cannot send fake safety settings that do nothing.

---

#### BOT-TRD-03 — Fix tracked-state DB/file conflict handling
**Priority:** High  
**Owner:** Bot / Python  
**Problem:** Tracked positions and pairs are written to DB and file without one transactional source of truth. A stale DB row can hide a newer recovery file.

**Scope**
- Add version/timestamp/checksum to tracked positions and pair state.
- Define source-of-truth rules on startup and recovery.
- Add conflict resolution logs and operator alert.
- Add tests for DB write fail + file success, stale DB + fresh file, concurrent additions.

**Acceptance criteria**
- Startup does not blindly prefer stale DB state.
- Conflict resolution is deterministic and logged.
- No tracked position is lost during recovery.

---

#### BOT-TRD-04 — Prove paired-order atomicity compensation
**Priority:** High  
**Owner:** Bot / Python  
**Problem:** dYdX cannot atomically commit both legs. The current system uses compensation. That must be tested brutally because this is where real money gets lost.

**Scope**
- Add integration/unit tests around leg 1 success + leg 2 failure.
- Validate emergency reduce-only close path.
- Persist compensation event and final exposure state.
- Add metrics for failed second leg and emergency close result.

**Acceptance criteria**
- If leg 2 fails, system either confirms leg 1 closed or leaves explicit orphan state.
- Operator receives a critical alert with bot, pair, side, size, order ID.

---

### Epic 3 — Runtime ownership and process-local state

#### BOT-RUN-01 — Enforce single API owner or add distributed ownership
**Priority:** High  
**Owner:** Bot / Python + Backend  
**Problem:** Manager handles, websocket registries, runtime settings, rate-limit fallback, metrics, and strategy store are process-local. Multiple Uvicorn workers or replicas will give nondeterministic behaviour.

**Scope**
- Decide: single API owner process or distributed state architecture.
- If single-owner: enforce deployment constraint and health check.
- If distributed: move manager ownership, broadcasts, rate limits, runtime settings, metrics to Redis/DB/distributed primitives.

**Acceptance criteria**
- Deployment cannot accidentally run unsafe multiple owners.
- `/ready` exposes ownership mode.
- Runtime control commands always hit the owning manager or are routed safely.

---

#### BOT-RUN-02 — Move API strategy CRUD from memory to durable DB
**Priority:** High  
**Owner:** Bot / Python + Backend  
**Problem:** Strategy CRUD is process-local despite durable ORM tables. Strategies can disappear on restart and differ across workers.

**Scope**
- Replace `InMemoryStrategyStore` writes with DB-backed repository.
- Version strategy changes.
- Make backtest strategy resolution deterministic.
- Add migration/backfill if needed.

**Acceptance criteria**
- Strategy survives API restart.
- Multiple API processes return the same strategy data.
- Backtests record exact strategy version used.

---

#### BOT-RUN-03 — Wire and supervise realtime monitoring service
**Priority:** High  
**Owner:** Bot / Python  
**Problem:** API reads realtime tables and WebSockets imply live updates, but the realtime writer service is not wired into an entrypoint in the traced source.

**Scope**
- Confirm if an external starter exists.
- If not, wire `start_realtime_service` under a supervised process/task.
- Add freshness timestamps to realtime rows.
- Add `/api/v1/realtime/health` or include in system status.

**Acceptance criteria**
- Realtime endpoints expose data freshness.
- Stale realtime data is clearly shown as stale, not silently accepted.
- Service restart is supervised and logged.

---

### Epic 4 — Backtest and Celery reliability

#### BOT-BT-01 — Validate Celery Beat deployment for market sync
**Priority:** Medium  
**Owner:** Bot / Python + Backend  
**Problem:** Market sync task exists, but Beat start command was not found in the repository. A scheduled task that is never scheduled is dead code.

**Scope**
- Confirm deployment starts Celery Beat when `MARKET_SYNC_ENABLED=true`.
- Add Makefile/docker/process command if missing.
- Add health visibility for last market sync.

**Acceptance criteria**
- Last market-sync time/result visible in API/admin.
- Deployment starts Beat intentionally or the feature is marked disabled.

---

#### BOT-BT-02 — Implement or remove candle aggregation hook
**Priority:** Medium  
**Owner:** Bot / Python  
**Problem:** `backtests.aggregate_candles` returns skipped. Keeping a fake post-processing task is misleading.

**Scope**
- Decide whether aggregation is needed.
- Implement real aggregation or rename/remove the task.
- Update monitoring so skipped compatibility hooks do not look successful business work.

**Acceptance criteria**
- No operator can mistake the stub for real candle aggregation.

---

#### BOT-BT-03 — Add Redis pub-sub subscriber or remove producer expectation
**Priority:** High  
**Owner:** Bot / Python + Backend  
**Problem:** Backtest Redis status pub-sub producer exists but no subscriber was found in the repo. Progress push may be missing.

**Scope**
- Confirm external bridge/subscriber.
- If absent, implement supervised subscriber to websocket/event fan-out.
- Add monitoring for publish/subscriber lag.

**Acceptance criteria**
- Backtest progress reaches frontend via a known, tested path.
- If no push exists, frontend contract uses polling honestly.

---

#### BOT-BT-04 — Harden interrupted backtest recovery under worker loss
**Priority:** High  
**Owner:** Bot / Python  
**Problem:** Recovery exists, but lock TTL/redelivery/heartbeat behaviour must be proven under real worker crashes.

**Scope**
- Test worker kill, API restart, Redis restart, DB temporary outage.
- Verify run statuses and idempotency.
- Add repair command/runbook.

**Acceptance criteria**
- No duplicate active run for same `run_id`.
- Interrupted runs are marked/recovered consistently.
- Operator has a documented repair path.

---

### Epic 5 — Database, migrations, and schema discipline

#### BOT-DB-01 — Stop relying on `Base.metadata.create_all()` before Alembic
**Priority:** High  
**Owner:** Backend + Bot / Python  
**Problem:** Startup creates tables before Alembic. That can mask migration drift and produce schemas that do not match clean migration-only environments.

**Scope**
- Compare schema from clean Alembic-only vs startup-created DB.
- Remove or gate `create_all` in production.
- Add migration verification step to CI.

**Acceptance criteria**
- Production schema is migration-owned.
- CI fails on model/migration drift.

---

#### BOT-DB-02 — Choose one realtime schema and delete/archive duplicates
**Priority:** High  
**Owner:** Backend + Bot / Python  
**Problem:** Realtime model/table names diverge and duplicate repositories exist. This causes fixes to land in dead paths.

**Scope**
- Identify active realtime tables and repositories.
- Mark canonical path.
- Archive or delete inactive paths after validation.
- Add test that API uses canonical repository.

**Acceptance criteria**
- One realtime schema is canonical.
- No active code imports deprecated realtime repository.

---

#### BOT-DB-03 — Validate MariaDB TLS configuration
**Priority:** Medium  
**Owner:** Backend  
**Problem:** TLS is represented by diagnostics, but connection SSL parameters were not clearly visible in engine kwargs.

**Scope**
- Confirm current DB transport encryption.
- Add explicit SSL connection args where required.
- Fail startup if production requires TLS and it is missing.

**Acceptance criteria**
- Production DB connection encryption is proven.
- Startup diagnostics show sanitized TLS mode.

---

### Epic 6 — Observability and operator truth

#### BOT-OBS-01 — Add operator-visible freshness and ownership dashboard data
**Priority:** High  
**Owner:** Bot / Python + Frontend  
**Problem:** Operators need to know whether status, realtime data, websocket updates, and manager ownership are fresh. Without that, the dashboard is decoration.

**Scope**
- Add freshness fields for realtime rows, backtest status, market sync, bot manager monitor.
- Frontend displays stale/unknown states clearly.
- Add API response fields: `source`, `last_updated_at`, `owner_process_id`, `staleness_seconds` where useful.

**Acceptance criteria**
- Stale data is impossible to confuse with live data.
- Frontend shows degraded status with reason.

---

#### BOT-OBS-02 — Add critical trading incident event types
**Priority:** High  
**Owner:** Bot / Python  
**Problem:** Partial leg failures, orphan exits, stale reconciliation, and state conflicts must become first-class incidents, not just log lines.

**Scope**
- Define event types and severity.
- Persist in `event_logs` and send Telegram when critical.
- Add admin API filters for critical trading incidents.

**Acceptance criteria**
- Every dangerous trading inconsistency creates a durable event.
- Operators can list unresolved critical incidents.

---

#### BOT-OBS-03 — Standardize API envelopes and validation errors
**Priority:** Medium  
**Owner:** Backend + Frontend  
**Problem:** Most API handlers use `api_response`, while auth, FastAPI validation, and exceptions use different shapes. Frontend handling gets messy.

**Scope**
- Define standard success/error contract.
- Add exception handlers for validation and HTTPException.
- Update frontend error parser.

**Acceptance criteria**
- Frontend can handle one normalized error structure.
- Auth routes are documented if intentionally different.

---

### Epic 7 — Refactoring after safety locks

#### BOT-REF-01 — Split `server.py` into routers and service modules
**Priority:** Medium  
**Owner:** Backend + Bot / Python  
**Problem:** `src/api/server.py` is too large and mixed. It owns routing, lifespan, recovery, metrics, strategy memory, websocket auth, and business orchestration. That blast radius is stupidly high.

**Scope**
- Split routers: auth, bots, backtests, celery, runtime, arbitrage, realtime, health.
- Keep public contracts stable.
- Add route contract tests before moving code.

**Acceptance criteria**
- No endpoint path/shape regression.
- Startup/lifespan logic isolated from route definitions.

---

#### BOT-REF-02 — Split `service_backtest.py` into orchestration, simulation, control, recovery
**Priority:** Medium  
**Owner:** Bot / Python  
**Problem:** Backtest service is too large and mixed. Fixing bugs here is risky because unrelated behaviour is coupled.

**Scope**
- Extract request normalization, dispatch, simulation, lifecycle control, recovery, analytics.
- Add tests around current behaviour first.

**Acceptance criteria**
- Backtest functionality remains compatible.
- Each extracted module has clear responsibility and tests.

---

#### BOT-REF-03 — Remove or isolate legacy standalone bot path
**Priority:** Low  
**Owner:** Bot / Python  
**Problem:** Legacy `main.py` and managed `main_instance.py` can drift. Two runtime paths double the testing burden.

**Scope**
- Confirm whether legacy path is still used.
- If unused, archive/remove.
- If used, document exact purpose and differences.

**Acceptance criteria**
- There is one canonical runtime path or a documented reason for two.

---

## 5. Recommended sprint order

### Sprint 1 — Stop the bleeding
1. BOT-SEC-01 — Protect all backtest routes.
2. BOT-SEC-02 — Kill unsafe production auth bypass.
3. BOT-TRD-01 — Confirm exchange fill/flat state before marking exits closed.
4. BOT-TRD-02 — Risk-control matrix.

### Sprint 2 — Make runtime state trustworthy
1. BOT-TRD-03 — DB/file conflict handling.
2. BOT-RUN-01 — Single owner/distributed ownership decision.
3. BOT-RUN-03 — Realtime service wiring/freshness.
4. BOT-OBS-02 — Critical trading incident events.

### Sprint 3 — Backtest/Celery reliability
1. BOT-BT-03 — Redis pub-sub subscriber/contract.
2. BOT-BT-04 — Backtest recovery crash testing.
3. BOT-BT-01 — Celery Beat validation.
4. BOT-BT-02 — Candle aggregation hook decision.

### Sprint 4 — Database discipline
1. BOT-DB-01 — Migration-only schema ownership.
2. BOT-DB-02 — Canonical realtime schema.
3. BOT-DB-03 — MariaDB TLS validation.

### Sprint 5 — Refactor safely
1. BOT-REF-01 — Split API server module.
2. BOT-REF-02 — Split backtest service.
3. BOT-REF-03 — Legacy runtime decision.

---

## 6. Dependency map

| Task | Depends on | Blocks |
|---|---|---|
| BOT-SEC-01 | None | Safe public/backtest usage |
| BOT-TRD-01 | Exchange/fill API validation | Trustworthy live trading state |
| BOT-TRD-02 | Code matrix | Frontend/backend config correctness |
| BOT-RUN-01 | Deployment topology decision | Multi-worker scaling |
| BOT-RUN-03 | Runtime ownership decision if supervised by API | Frontend realtime trust |
| BOT-DB-01 | Migration comparison | Reliable deployment/schema governance |
| BOT-REF-01 | Contract tests | Safer API maintainability |
| BOT-REF-02 | Backtest behaviour tests | Safer backtest changes |

---

## 7. Definition of done for the Bot / Python list

A task is not done when the code compiles. It is done only when:

1. The bug/risk has a test proving the old behaviour fails or the new behaviour works.
2. The operator-facing state is honest.
3. Failure mode is documented.
4. No secrets are printed or returned.
5. Runtime state survives restart where the feature claims durability.
6. Frontend/backend contracts are updated if API behaviour changes.

---

## 8. What not to do first

Do not start by making the UI prettier. Do not start by splitting files. Do not start by adding more bot features. That is weak prioritization.

The first priority is to make the system safe: auth enforcement, exchange exposure truth, risk controls, state recovery, and runtime ownership. Everything else is secondary.
