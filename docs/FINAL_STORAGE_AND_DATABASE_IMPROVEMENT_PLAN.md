 # Final Storage and Database Improvement Plan

Date: 2026-07-12
Scope: PostgreSQL, Valkey/Celery, NATS JetStream, ClickHouse, MinIO, local artifacts, task state, migrations, health checks, recovery, and operator documentation.

## Architecture decisions

- PostgreSQL is authoritative for application entities, backtest metadata/state, bot runtime state, commands, attempts, and worker heartbeats.
- MinIO is authoritative for enabled backtest result artifacts; local files are a development fallback only and must be atomically replaced.
- ClickHouse is a derived analytics projection. A ClickHouse outage must not corrupt PostgreSQL state, and repeated terminal persistence must not multiply analytical facts.
- Valkey is temporary/cache/lock/Celery transport and result state. It is never the source of truth for durable business state.
- NATS JetStream is durable event/command transport. The current Celery executor remains authoritative; the NATS command executor must stay disabled until an explicit cutover so a dual-written command cannot execute twice.
- `bot_states/` contains per-instance operational logs and development fallback artifacts; database-backed instance config is authoritative.

## Phase 0 — Audit and baseline

### [x] Completed — P0.1 Inventory persistence systems and validate the supplied documents

- **Problem:** Existing documentation contains completion claims and defaults that cannot be trusted without implementation and runtime evidence.
- **Evidence:** Full reads of `LOCAL_SETUP_GUIDE.md` and `improvements-0.1.md`; repository search found PostgreSQL, Valkey/Celery, NATS JetStream, ClickHouse, MinIO, local files, task tables, and in-memory test fallbacks. Baseline containers showed PostgreSQL/Valkey/MinIO healthy and NATS/ClickHouse falsely unhealthy.
- **Affected files:** Repository-wide; source documents above; this plan and final report.
- **Proposed solution:** Trace owners/readers/writers, compare config and docs, run focused tests and live probes, and record an authoritative matrix in the final report.
- **Acceptance criteria:** Every referenced persistence system is classified; conflicting paths and incomplete components are recorded; claims include command/test evidence.
- **Required tests:** Repository search; Compose rendering; focused Python/Go persistence tests; live service probes.
- **Risk level:** Low.
- **Status:** Completed.
- **Implementation notes / evidence:** `88 passed, 6 skipped` for focused bot persistence/NATS tests; focused Go DB/NATS/service/repository/config packages passed; both Compose files rendered successfully. Live probes proved NATS and ClickHouse endpoints worked while Docker health failed because `curl` is absent from both images.

## Phase 1 — Correctness and duplicate prevention

### [x] Completed — P1.0 Enforce backend/bot PostgreSQL ownership separation

- **Problem:** Backend and bot used the same local database and both defined `bot_instances` with incompatible schemas; bot inserts failed on backend-owned `user_id NOT NULL`.
- **Evidence:** Full bot suite against the running shared database failed with `psycopg2.errors.NotNullViolation` on `bot_instances.user_id`. Compose set both `DATABASE_URL` and `BOT_DATABASE_URL` to `dydx_bot` despite the documented ownership guardrail.
- **Affected files:** All four Compose files, `.env.example`, encrypted development profile, profile example, setup/architecture docs, bot Alembic path.
- **Proposed solution:** Idempotently create `dydx_bot_runtime` on the same PostgreSQL server, use strict `BOT_DB_CUTOVER_MODE=dedicated`, and point bot API/worker to it while backend stays on `dydx_bot`.
- **Acceptance criteria:** Ownership diagnostics show separated database names; bot schema initializes and repository integration inserts succeed; existing volumes/data are not deleted.
- **Required tests:** Compose rendering; dedicated DB initialization; real bot schema/migration and API DB integration test.
- **Risk level:** High.
- **Status:** Completed.
- **Implementation notes / evidence:** The idempotent init container created `dydx_bot_runtime` alongside existing `dydx_bot`. Bot required-table verification passed and the real API DB integration passed on the dedicated target. Alembic lookup was corrected from `bot/src/alembic.ini` to `bot/alembic.ini` and stamped the PostgreSQL branch at `0003_backtest_storage_cols`.

### [x] Completed — P1.1 Make artifact persistence fail-closed and interruption-safe

- **Problem:** MinIO strict mode falls back to local storage when the SDK/client cannot be constructed; local writes use direct `Path.write_bytes`, allowing partial files after interruption and racing writers.
- **Evidence:** `minio_artifact_store.py` only raises in strict mode inside the client write/read branches; `_client is None` reaches fallback. `artifacts.py` writes directly to the final path.
- **Affected files:** `bot/src/infrastructure/storage/minio_artifact_store.py`, `bot/src/infrastructure/storage/artifacts.py`, `bot/tests/test_storage_adapters.py`.
- **Proposed solution:** Reject all enabled strict operations when the client is unavailable, validate object keys, and use same-directory temporary files plus atomic replace for local artifacts.
- **Acceptance criteria:** Strict mode never silently writes/reads local data; invalid traversal-like keys are rejected; interrupted/concurrent local writes expose only complete payloads.
- **Required tests:** Missing-client strict write/read/exists tests; atomic replacement/concurrency regression tests; existing adapter suite.
- **Risk level:** High.
- **Status:** Completed.
- **Implementation notes / evidence:** Added strict missing-client rejection, normalized MinIO keys, atomic `fsync` + replace for local writes, and concurrency/missing-client tests. Focused adapter tests pass.

### [x] Completed — P1.2 Prevent Celery/NATS duplicate backtest execution

- **Problem:** Backend publishes every successful Celery-owned backtest request to `backtest.command.start` when `NATS_ENABLED=true`, while the full-stack worker runs only Celery. Starting the NATS worker later can execute the already-running/completed run again because the command row remains `published` rather than terminal.
- **Evidence:** `docker-compose.stack*.yml` enables NATS but sets `WORKER_MODE=celery`; `NATSCommandService` ignores `CommandBusEnabled`; `worker_entrypoint.py` runs one executor mode; NATS handler executes `execute_existing_backtest` for non-terminal command rows.
- **Affected files:** `backend/internal/services/nats_command_service.go`, its tests, `backend/config/config.go`, `.env.example`, Compose stack files, profile/example config, docs.
- **Proposed solution:** Gate command creation/publication on the explicit `BOT_COMMAND_BUS_ENABLED` cutover flag, default it off for the current Celery architecture, keep NATS events available, and document the cutover invariant.
- **Acceptance criteria:** With NATS enabled and command bus disabled, no command row or JetStream command is created; explicit enablement preserves tested publish/idempotency behavior.
- **Required tests:** Go command-service disabled/enabled tests; Compose/config contract tests; live JetStream inspection.
- **Risk level:** High.
- **Status:** Completed.
- **Implementation notes / evidence:** `NATSCommandService` now returns without creating a task row or message unless both NATS and `BOT_COMMAND_BUS_ENABLED` are enabled. Defaults and both stack variants pin the cutover flag false; enabled/disabled Go tests pass.

### [x] Completed — P1.3 Make ClickHouse backtest projections idempotent

- **Problem:** Re-saving a terminal run appends the same rows to MergeTree tables, inflating analytics.
- **Evidence:** `_sync_backtest_sidecars` writes all analytical rows on every `save_run`; current DDL uses append-only `MergeTree` and has no run projection marker.
- **Affected files:** `bot/src/infrastructure/persistence/repository_backtest.py`, backtest model/migration if needed, storage tests and repository tests.
- **Proposed solution:** Persist a deterministic terminal projection checksum in PostgreSQL artifact metadata and skip analytical rewrites when the same checksum is already recorded; preserve retry on partial/failed projection.
- **Acceptance criteria:** Repeating the same completed save produces zero additional analytical writes; changed terminal results produce a new projection attempt; PostgreSQL remains authoritative.
- **Required tests:** Same-payload duplicate-save test, changed-payload test, failed-writer retry test.
- **Risk level:** High.
- **Status:** Completed.
- **Implementation notes / evidence:** Terminal projection checksums are stored on the PostgreSQL artifact-reference metadata only after all expected rows are accepted. An identical repeated save retains the recorded row count and performs no writer calls; failed/no-op writers do not mark completion.

Runtime validation additionally exposed mutable progress rows being projected before terminal completion. Analytics now
projects terminal snapshots only. Live runs `run-d49bb94f7a1a` and `run-54dadc86c2c8` each contain exactly one trade,
one position snapshot, and one daily-PnL ClickHouse row.

### [x] Completed — P1.4 Align Celery producer and consumer persistence namespaces

- **Problem:** The bot API published Celery jobs through Valkey DB 0 while the worker consumed DB 1, leaving accepted backtests permanently queued.
- **Evidence:** Audit run `run-64ddcbc4d71d` remained pending; Valkey DB 0 contained one `backtests` list entry, DB 1 contained none, and worker logs showed no receipt.
- **Affected files:** `docker-compose.stack.yml`, `docker-compose.stack.arm64.yml`, `.env.example`, setup docs, Celery contract tests.
- **Proposed solution:** Set identical `CELERY_BROKER_URL=.../1` and `CELERY_RESULT_BACKEND=.../2` on API and worker; reserve DB 0 for cache/session state.
- **Acceptance criteria:** A submitted task is received by the worker, the broker queue drains, and the terminal result is readable.
- **Required tests:** Compose rendering, Celery config contract, real API submission and worker log/result checks.
- **Risk level:** High.
- **Status:** Completed.
- **Implementation notes / evidence:** The single known orphan audit message was cancelled and removed only after its queue count was verified as exactly one. Replacement run `run-672288fe05c2` was received by Celery and completed in about two seconds; later final runs also completed.

## Phase 2 — Startup, health, and migrations

### [x] Completed — P2.1 Repair Compose health and dependency contracts

- **Problem:** NATS and ClickHouse are permanently marked unhealthy because their images do not contain `curl`; enabled bot storage adapters are not ordered after those healthy services.
- **Evidence:** Docker inspect reports `exec: "curl": executable file not found`; host probes return healthy responses; both images contain `wget`.
- **Affected files:** `docker-compose.infra.yml`, `docker-compose.infra.arm64.yml`, `docker-compose.stack.yml`, `docker-compose.stack.arm64.yml`.
- **Proposed solution:** Use image-available health probes, bind local data ports to loopback, and add health-conditioned dependencies for enabled storage services.
- **Acceptance criteria:** All infrastructure containers become healthy; Compose validates on x86 and ARM files; bot services wait for their enabled dependencies.
- **Required tests:** `docker compose config -q`; live `docker compose up`; Docker health inspection.
- **Risk level:** Medium.
- **Status:** Completed.
- **Implementation notes / evidence:** Replaced unavailable `curl` probes with image-provided `wget`, added health-conditioned storage dependencies, and bound datastore ports to loopback. All four Compose variants render; recreated NATS and ClickHouse changed from false-unhealthy to healthy without volume removal.

### [x] Completed — P2.2 Make backend migration policy explicit and environment-controlled

- **Problem:** Backend startup hard-codes `AutoMigrate: true`, contradicting `.env.example`, repository instructions, and production deployment expectations.
- **Evidence:** `backend/cmd/server/main.go:53`; `DB_AUTO_MIGRATE=false` is currently ignored.
- **Affected files:** `backend/cmd/server/main.go`, startup tests, stack Compose, setup docs.
- **Proposed solution:** Parse `DB_AUTO_MIGRATE` with safe environment defaults, set it explicitly for the local stack, and retain production control.
- **Acceptance criteria:** False disables startup migrations, true enables them, invalid values fail startup, and clean local stack deterministically migrates.
- **Required tests:** Go unit tests for parsing; clean-schema integration/runtime migration check.
- **Risk level:** High.
- **Status:** Completed.
- **Implementation notes / evidence:** Backend parses `DB_AUTO_MIGRATE`, rejects invalid values, defaults off, and uses configured pool sizes. The local stack explicitly enables migrations. Unit tests cover unset/true/false/invalid values.

### [x] Completed — P2.3 Expose truthful storage readiness and configuration

- **Problem:** Health/readiness emphasizes PostgreSQL and upstream API but does not truthfully report enabled MinIO, ClickHouse, NATS, or Valkey readiness; backend defaults enable optional adapters unexpectedly.
- **Evidence:** Bot `/ready` checks DB/manager state; backend config defaults ClickHouse/MinIO to enabled; local docs call adapters both optional/off and enabled.
- **Affected files:** Bot storage adapters/server health code and tests; backend config tests; env/profile examples; docs.
- **Proposed solution:** Add sanitized adapter diagnostics/probes, distinguish required strict dependencies from optional degraded projections, and align defaults with the actual local/full-stack modes.
- **Acceptance criteria:** Operators can identify unavailable enabled storage without secrets; strict MinIO blocks readiness; optional analytics reports degradation without corrupting core state.
- **Required tests:** Health/readiness contract tests and live outage/recovery probes.
- **Risk level:** Medium.
- **Status:** Completed.
- **Implementation notes / evidence:** MinIO and ClickHouse expose sanitized probes through bot `/health` and `/ready`; strict unhealthy artifacts block readiness while optional analytics degradation is visible but non-blocking. Backend optional adapter code defaults are off unless explicitly enabled.

### [x] Completed — P2.4 Make bot PostgreSQL bootstrap complete and deterministic

- **Problem:** ORM creation followed by an Alembic baseline stamp skipped raw-SQL trading tables, and the PostgreSQL base migrations failed on a truly empty database because enum/default DDL was invalid.
- **Evidence:** `tracked_positions` and `cointegrated_pairs` were absent at revision `0003`; trading-state tests logged file fallback. Empty-database migration failed first on duplicate enum creation and then on unparenthesized `NOW() AT TIME ZONE` defaults.
- **Affected files:** `bot/src/infrastructure/database.py`, `bot/src/api/server.py`, `bot/migrations/postgres/0001_initial_schema.py`, `0002_add_artifact_references.py`, new `0004_runtime_trading_state_tables.py`.
- **Proposed solution:** Migrate before ORM compatibility creation, bootstrap empty schemas from base, repair PostgreSQL enum/timestamp DDL, add a forward repair migration, and verify the raw runtime tables at startup.
- **Acceptance criteria:** Existing DB upgrades to `0004`; a newly created empty database migrates from base to head; tracked-position DB read/write flow succeeds.
- **Required tests:** Real existing-database upgrade, disposable empty-database bootstrap, required-table verification, tracked-position flow.
- **Risk level:** High.
- **Status:** Completed.
- **Implementation notes / evidence:** Existing `dydx_bot_runtime` upgraded to `0004_runtime_state_tables`. A purpose-created empty validation database migrated all four revisions, created 16 public tables, passed required-table verification, and was dropped only after confirming it held audit-only data.

## Phase 3 — Recovery, retention, and documentation

### [x] Completed — P3.1 Document and validate retention, backup, and recovery

- **Problem:** Compose volumes persist data but there is no consolidated backup/restore contract; the setup guide suggests destructive volume deletion without a mandatory data check; ClickHouse/NATS retention is inconsistent and MinIO lifecycle is unspecified.
- **Evidence:** Named volumes exist for all five infrastructure services; guide “Clean Slate” commands omit MinIO/ClickHouse/NATS and do not require confirmation.
- **Affected files:** `LOCAL_SETUP_GUIDE.md`, root/service READMEs, new final report, Compose/config comments.
- **Proposed solution:** Document ownership-aware backups, safe clean-slate prechecks, retention defaults, recovery commands, and restart validation without deleting volumes.
- **Acceptance criteria:** Exact backup/restore and non-destructive restart commands are documented; destructive cleanup is explicitly opt-in and preceded by inventory/export checks.
- **Required tests:** Execute read-only backup inventory commands and restart/reconnect smoke tests.
- **Risk level:** Medium.
- **Status:** Completed.
- **Implementation notes / evidence:** Setup guide now documents named-volume persistence, host-side PostgreSQL backup, non-destructive restart, and mandatory inventory/export before any manually authorized volume removal. Automated object/analytics deletion remains intentionally absent to prevent accidental data loss.

### [x] Completed — P3.2 Reconcile supplied documentation and produce final evidence report

- **Problem:** Required source docs contain stale ports/defaults/migration claims and duplicate “fixed” plus “pending” sections.
- **Evidence:** `LOCAL_SETUP_GUIDE.md` says adapters are off then exports them on; says migrations always run; `improvements-0.1.md` repeats addressed findings as pending.
- **Affected files:** `LOCAL_SETUP_GUIDE.md`, `improvements-0.1.md`, `README.md`, `.env.example`, architecture docs, `docs/FINAL_STORAGE_AND_DATABASE_VALIDATION_REPORT.md`, this plan.
- **Proposed solution:** Rewrite only verified claims, include datastore matrix and exact validation commands, and retain blocked items with evidence.
- **Acceptance criteria:** Documentation matches rendered config and runtime; final report contains every user-requested section; all plan statuses and evidence are current.
- **Required tests:** Command/path verification, link/path checks, final diff review.
- **Risk level:** Low.
- **Status:** Completed.
- **Implementation notes / evidence:** Setup, root README, env example, encrypted/example profiles, supplied improvement note, this plan, and the final report now describe the rendered and live-validated architecture, Celery namespaces, migration head, strict artifact behavior, and remaining deployment risk.

## Phase 4 — Deployment-surface reconciliation

### [!] Blocked — P4.1 Retire or regenerate legacy `deploy/k8s` MariaDB manifests

- **Problem:** `deploy/k8s/dydx-trading-bot-{staging,production}.yaml` declare a PostgreSQL contract in comments but still deploy MariaDB, set `DB_TYPE=mysql`, and point backend and bot at a shared schema. Current runtime validation and `deploy/k8s-next` use PostgreSQL with separated ownership.
- **Evidence:** Repository-wide datastore scan found active-looking MariaDB services/PVCs/config in both generated manifests, while bot configuration rejects MySQL URLs and the shared `bot_instances` collision is proven locally.
- **Affected files:** `deploy/k8s/dydx-trading-bot-staging.yaml`, `deploy/k8s/dydx-trading-bot-production.yaml`, their source generator/deployment workflow, external clusters and secrets.
- **Proposed solution:** The deployment owner must confirm whether these generated files are retired artifacts or live release inputs. If live, regenerate them from the PostgreSQL `deploy/k8s-next` contract and execute a reviewed data migration/cutover; if retired, remove them in a separately approved cleanup.
- **Acceptance criteria:** One production datastore contract remains; rendered workloads use supported PostgreSQL URLs and separate backend/bot databases; cluster backup/restore and migration jobs pass before traffic cutover.
- **Required tests:** Kustomize/render validation, staging migration rehearsal with data checksums, backup/restore drill, workload readiness and rollback exercise.
- **Risk level:** Critical.
- **Status:** Blocked.
- **Implementation notes / evidence:** No cluster context, authoritative deployment-path decision, MariaDB backup, or cutover authorization was available. Rewriting these manifests would be a materially broader and potentially destructive production migration, so they were not changed.

## Quality gates

- Bot: focused persistence tests, then full `pytest` suite and applicable lint/import checks.
- Backend: targeted packages, then `go test ./...`, formatting/vet/lint where installed.
- Frontend: lint/build if a storage-facing contract changes.
- Platform: config validation, both x86 Compose files and ARM variants, secret/legacy DB checks.
- Runtime: all infrastructure healthy; schemas/tables/bucket/streams usable; representative persisted backtest read-back; duplicate-save check; datastore restart recovery.

## Rollback posture

- Code/config changes are additive or feature-gated. Revert the affected files and restart services; do not delete volumes.
- No destructive database migration is planned. Any added metadata is nullable/backward-compatible.
- If strict MinIO causes production readiness failures, restore object storage first; disabling strict mode is an explicit operational fallback that must be recorded as reduced durability.
