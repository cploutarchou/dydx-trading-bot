# Final Storage and Database Validation Report

Date: 2026-07-12  
Scope: local full stack and repository persistence surfaces in `/home/chris/workspace/dydx-trading-bot`

## Outcome

The supported local PostgreSQL stack is operational and restart-safe. All nine long-running containers start, their
health checks pass, the bot and backend are ready, and a real Celery backtest fetched dYdX testnet candles, completed,
persisted artifacts to strict MinIO, projected terminal analytics to ClickHouse, emitted durable NATS events, and was
read back after PostgreSQL, MinIO, and ClickHouse restarts.

The audit found and corrected high-impact defects: backend/bot schema collision, a mismatched Celery broker database,
pre-terminal ClickHouse duplicate writes, incomplete bot migrations, silent strict-MinIO fallback, non-atomic local
artifacts, false Compose health checks, and an ungated NATS command mirror. The full bot suite now passes.

One critical item is blocked: the legacy generated files under `deploy/k8s/` still describe MariaDB/shared-schema
deployments that current code does not support. `deploy/k8s-next` and the validated local stack are PostgreSQL-based.
Changing a possibly live production datastore without cluster context, backups, and an owner-approved cutover would be
unsafe; exact evidence and next action are recorded below and in the improvement plan.

## Storage architecture and responsibility matrix

| System | Data | Writers | Readers | Role / authority | Completion and conflicts |
|---|---|---|---|---|---|
| PostgreSQL `dydx_bot` | Backend users, auth, settings, strategies, delegated backtest summaries/events, platform task metadata | Go backend and backend migrations | Go backend/frontend through API | Authoritative platform database | Complete for the local stack; startup migration is explicitly controlled by `DB_AUTO_MIGRATE` |
| PostgreSQL `dydx_bot_runtime` | Bot instances, jobs, event logs, trades, backtest runtime/request state, artifact registry, tracked positions, cointegrated pairs | Bot API, Celery worker, Alembic | Bot API/worker; backend only through bot HTTP/events | Authoritative bot/trading/backtest state | Complete at Alembic `0004_runtime_state_tables`; separated from backend to prevent incompatible `bot_instances` ownership |
| Valkey DB 0 | Cache, sessions, locks, rate limits, temporary application coordination | Backend and bot | Backend and bot | Temporary/cache; never durable business truth | Complete; named volume is persistent operationally but content is reconstructable |
| Valkey DB 1 | Celery broker queues | Bot API producer | Celery worker | Durable-enough task transport, not result truth | Complete; API/worker URLs now match and a real task drained successfully |
| Valkey DB 2 | Celery task results | Celery worker | Bot task inspection/control | Temporary task result cache | Complete; expiry remains configured by Celery |
| NATS JetStream `BACKTEST_EVENTS` | Started/progress/completed backtest events with message IDs | Bot worker | Backend event projector | Durable event transport; PostgreSQL remains state truth | Complete and live: one file-backed stream, one consumer, four messages during validation |
| NATS command subjects | Potential backtest execution commands | Backend command service | NATS worker only after cutover | Disabled alternate executor | Correctly gated by `BOT_COMMAND_BUS_ENABLED=false`; no command stream is created in the Celery-owned stack |
| MinIO bucket `backtests` | `request.json`, `trades.json`, `position_snapshots.json`, `daily_pnl.json`, terminal `full_result.json` under `backtests/{run_id}/` | Bot API/worker repository | Bot API/worker repository | Authoritative large backtest artifacts when enabled | Complete in strict mode; no local fallback on client/config/write/read failure; stable `s3://` references are stored in PostgreSQL |
| ClickHouse `dydx_analytics` | Terminal backtest trades, position snapshots, daily PnL; optional equity/strategy metrics when present | Bot repository/worker | Analytics APIs and operator queries | Derived/rebuildable analytical projection | Complete for validated flows; only terminal snapshots project, and identical terminal saves are checksum-gated |
| Local `bot_states/` / artifact files | Instance operational files and development artifact fallback | Bot runtime/test adapters | Bot runtime/test adapters | Development fallback/operational only | Atomic same-directory temp + `fsync` + replace; not used by strict full stack |
| SQLite/in-memory stores | Unit/integration test databases and repository doubles | Tests | Tests | Test-only | Not a supported deployment datastore; backend also uses in-memory SQLite in route tests |
| MariaDB/MySQL under `deploy/k8s/` | Legacy generated staging/production contract | Unknown external deployment workflow | Unknown clusters | Conflicting/unsupported legacy path | Blocked; current bot rejects MySQL and shared schema is incompatible. `deploy/k8s-next` is the supported PostgreSQL direction |

No MongoDB runtime client was found. MongoDB and SQLite entries in Go dependency metadata are indirect/test concerns,
not configured production persistence paths.

## Problems found and changes implemented

1. Backend and bot targeted the same PostgreSQL database but defined incompatible `bot_instances` tables. Added an
   idempotent database-init service and dedicated `dydx_bot_runtime` URLs/ownership guardrails without deleting volumes.
2. Bot Alembic resolved `/app/src/alembic.ini`, stamped an incomplete schema, and its clean PostgreSQL DDL failed.
   Corrected the path, URL percent escaping, startup order, enum/timestamp DDL, empty-schema bootstrap, and added
   `0004_runtime_trading_state_tables` plus required-table verification.
3. `tracked_positions` and `cointegrated_pairs` were absent, causing silent file fallback. The forward migration creates
   both, and a real tracked-position DB read/clear flow passed.
4. API and worker used different Celery broker databases. Both now use Valkey DB 1 and DB 2 for results; DB 0 remains
   cache/session space.
5. Progress persistence appended mutable ClickHouse rows, duplicating logical facts before terminal completion.
   Analytics now projects immutable terminal snapshots only, then records a PostgreSQL projection checksum.
6. Strict MinIO could silently fall back when no client was constructed. All strict operations now fail closed, keys are
   normalized, health is sanitized, and the full stack explicitly enables strict mode.
7. Local artifact writes could expose partial/racing files. They now use same-directory temporary files, flush, `fsync`,
   and atomic replacement with cleanup.
8. NATS commands were mirrored while Celery was the executor. Backend command creation/publication now requires the
   explicit command-bus cutover flag; durable events stay enabled.
9. NATS, ClickHouse, backend, and bot health checks invoked absent `curl` binaries. They use available `wget` probes and
   loopback endpoints; app startup is health-ordered after required storage.
10. Backend ignored `DB_AUTO_MIGRATE` and hard-coded pool settings. It now validates the flag, defaults migration off,
    uses configured pool values, and the local stack opts in explicitly.
11. URL and host aliases could conflict. ClickHouse URL host/port/scheme are canonical when supplied, and profiles/docs
    now identify canonical Celery and database namespaces.
12. The test environment lacked `pytest-asyncio`, hiding five NATS correlation tests. The dependency is pinned and the
    full suite passes.

## Files changed

- Platform/config/docs: `.env.example`, `README.md`, `LOCAL_SETUP_GUIDE.md`, `improvements-0.1.md`, both structured
  profile files, all four Compose files, this report, and the final improvement plan.
- Backend: `cmd/server/main.go`, new parser tests, `config/config.go`, NATS command service and status/service tests.
- Bot database/migrations: `src/infrastructure/database.py`, `src/api/server.py`, PostgreSQL revisions `0001`, `0002`,
  and new `0004_runtime_trading_state_tables.py`.
- Bot storage: artifact, MinIO, ClickHouse writer, backtest repository, runtime config, and NATS event-bus modules.
- Bot tests/dependencies: storage/repository/database/config/Celery/NATS tests and `requirements.txt`.

Use `git status --short` for the exact review-time list, including new files.

## Skills used or created

Applied repository customizations:

- `defi-python-algo-trading` for trading-path safety and idempotency.
- `config-infrastructure-management` for structured config, Compose, and secret/default handling.
- `defi-observability-metrics` for readiness and sanitized storage diagnostics.
- Root senior DeFi platform agent, production backtest auditor, backend database/migration, and service-specific
  instructions from the customization indices.

No new skill was created. Existing repository skills cover the work; another overlapping skill would add maintenance
without a distinct reusable workflow.

## Tests and quality gates

Passing results:

- Bot full suite: `374 passed, 11 skipped, 2 warnings`.
- Focused storage/repository suite after terminal-projection fix: `48 passed`.
- Previously failing config/Celery/NATS tests after dependency/config repair: `45 passed`.
- Initial focused persistence/NATS baseline: `88 passed, 6 skipped`.
- Backend: `go test ./...` passed all packages; `gofmt -d` reported no diff.
- Frontend: `npm run lint && npm run build` passed; Vite transformed 2,013 modules.
- Python formatting: Black check passed on all changed Python files; `compileall` passed. Ruff is not installed in the
  project virtual environment and was not claimed as executed.
- Compose: all x86 and ARM infrastructure/full-stack files render successfully.
- Configuration/security: encrypted development profile validated; Kubernetes plaintext-secret scan passed; no secret
  values were added to source.
- Git hygiene: `git diff --check` passed before final documentation generation and is part of the final command set.

The 11 skipped bot tests are existing conditional/integration skips; none was newly hidden or weakened. Two warnings are
upstream deprecations (`passlib`/Python crypt and Starlette test client).

## Runtime validation evidence

- Nine containers were healthy: PostgreSQL, Valkey, NATS, ClickHouse, MinIO, backend, bot API, bot worker, frontend.
- Bot `/ready` reported `artifacts.healthy=true`, `strict=true`, and `analytics.healthy=true`; backend `/ready` returned
  HTTP 200.
- Existing bot DB upgraded to `0004_runtime_state_tables`; a purpose-created empty DB migrated revisions 0001–0004,
  created 16 public tables, passed required-table verification, and was removed only after confirming audit-only scope.
- MinIO bucket `backtests` exists and the final run has all five expected artifact objects.
- Real backtest `run-d49bb94f7a1a` fetched BTC-USD/ETH-USD candles, completed with one trade, and is readable through the
  authenticated API. Its PostgreSQL record reports terminal status, artifact references, and three analytical rows.
- ClickHouse contains exactly one trade, one position snapshot, and one daily-PnL row for that run. Restarted execution
  created stable new run ID `run-54dadc86c2c8`, also with exactly one row in each table.
- NATS `BACKTEST_EVENTS` stored started/progress/completed events and the backend consumer was attached. No command
  stream was present with the command bus disabled.
- PostgreSQL, MinIO, and ClickHouse were restarted non-destructively. All returned healthy, bot/backend readiness
  recovered, MinIO artifacts remained, the ClickHouse count remained one, and the completed result was readable.
- No Docker volume was removed. The only database dropped was the uniquely named empty-bootstrap validation database,
  created during this audit and confirmed to contain audit-only schema data.

## Remaining risks and blocked items

1. **Blocked / critical:** legacy `deploy/k8s` production and staging manifests still deploy MariaDB/shared bot state.
   Required next action: deployment owner confirms retirement versus live use, supplies cluster context and backups, and
   approves a rehearsed migration to the PostgreSQL `deploy/k8s-next` contract.
2. **Medium:** ClickHouse and PostgreSQL do not share a transaction. The checksum prevents normal/repeated terminal
   saves, but a process death after ClickHouse accepts rows and before PostgreSQL commits the checksum remains a narrow
   duplicate window. Follow-up: add a deterministic ClickHouse insert token or a deduplicating engine/query contract and
   an injected crash-point integration test.
3. **Medium:** Retention is intentionally non-destructive/indefinite for MinIO and ClickHouse. Follow-up: approve legal
   and operational retention periods, then add lifecycle/TTL policies with dry-run inventory and restore tests.
4. **Medium:** Backups are documented but no external backup target, schedule, encryption key, or live restore
   environment was provided. Follow-up: configure scheduled PostgreSQL/MinIO/ClickHouse/NATS backups and perform a
   measured restore drill.
5. **Low:** Checked-in Compose defaults are local-development credentials. Ports are loopback-bound, but production must
   inject secret-manager values and must not reuse these defaults.
6. **Low:** Optional ClickHouse degradation is visible but does not block bot readiness by design because PostgreSQL and
   MinIO are authoritative. Production alerting should page on sustained analytics degradation.

## Exact start commands

```bash
cd /home/chris/workspace/dydx-trading-bot
make config-keygen       # first setup only; keep the generated key private
make dev-config
make dev
make stack-up-dev
make stack-ps
```

Non-destructive restarts preserve named volumes:

```bash
docker compose -f docker-compose.stack.yml restart postgresql minio clickhouse
docker compose -f docker-compose.stack.yml ps
```

## Exact validation commands

```bash
cd /home/chris/workspace/dydx-trading-bot

# Render/health
for f in docker-compose.infra.yml docker-compose.infra.arm64.yml \
         docker-compose.stack.yml docker-compose.stack.arm64.yml; do
  docker compose -f "$f" config >/dev/null || exit 1
done
docker compose -f docker-compose.stack.yml ps
curl -fsS http://127.0.0.1:8888/ready
curl -fsS http://127.0.0.1:8889/ready

# Schemas, bucket, analytics, and JetStream
docker exec dydx-postgresql psql -U dydx_bot -d dydx_bot_runtime \
  -c 'select version_num from alembic_version'
docker exec dydx-minio sh -c 'ls -la /data/backtests'
docker exec dydx-clickhouse clickhouse-client --user default \
  --password change-me-clickhouse --query 'SHOW TABLES FROM dydx_analytics'
curl -fsS 'http://127.0.0.1:8222/jsz?streams=true'

# Quality gates
cd bot && .venv/bin/python -m pytest tests -q && cd ..
cd backend && go test ./... && cd ..
cd frontend && npm run lint && npm run build && cd ..
python3 scripts/check_no_plaintext_k8s_secrets.py
git diff --check
```

Representative local backtest (the full stack's development service token must match `BOT_API_TOKEN`):

```bash
curl -fsS -H 'Authorization: Bearer local-dev-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"storage-validation",
    "start_date":"2026-06-01",
    "end_date":"2026-06-02",
    "initial_balance":10000,
    "max_pairs":2,
    "pair_selection_mode":"manual",
    "pairs":["BTC-USD","ETH-USD"],
    "selected_pairs":["BTC-USD/ETH-USD"],
    "timeout_seconds":180,
    "trading_parameters":{
      "pair_selection_mode":"manual",
      "zscore_threshold":1.5,
      "stats_window":21,
      "usd_per_trade":10.0,
      "resolution":"1HOUR"
    }
  }' http://127.0.0.1:8889/api/v1/backtests/run
```

Use the returned `run_id` with `GET /api/v1/backtests/{run_id}/status` and the ClickHouse count queries above. External
market-data availability can affect future reruns; the 2026-07-12 validation completed against the live dYdX testnet
indexer.

## Recommended follow-up

Resolve the legacy Kubernetes ownership decision first. Then close the ClickHouse crash-window with datastore-level
deduplication, approve retention policies, and schedule encrypted backup/restore drills. These are the only material
storage reliability items not completed within the safe local/repository scope.
