# dYdX Trading Platform Monorepo

This repository contains the active dYdX trading platform across three runtime services and shared infrastructure.

`frontend -> backend -> bot -> exchange/runtime`

## Services

| Service     | Purpose                                                  | Default port |
| ----------- | -------------------------------------------------------- | ------------ |
| `frontend/` | public website, auth flows, client/backoffice/IB portals | `5173`       |
| `backend/`  | public application API, auth, orchestration, bot proxy   | `8888`       |
| `bot/`      | Python bot API, trading runtime, backtests, live workers | `8889`       |

## Local Infrastructure Stack

All local services should discover infrastructure through environment variables. The canonical local-development stack is:

| Service | Host | Port | Purpose | Environment variables |
| --- | --- | --- | --- | --- |
| PostgreSQL | `localhost` | `5432` | active transactional database and persistence path for backend and bot | `DATABASE_URL`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DB_*` |
| Valkey | `localhost` | `6379` | Redis-compatible cache/broker surface for existing Celery, lock, rate-limit, and cache flows | `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `VALKEY_HOST`, `VALKEY_PORT`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| NATS JetStream | `localhost` | `4222` | available command/event transport, not a required runtime dependency in the current checked-in app path | `NATS_URL` |
| NATS monitoring | `localhost` | `8222` | readiness and operator monitoring | `NATS_MONITORING_URL` |
| ClickHouse HTTP | `localhost` | `8123` | optional analytical backtest writer target, disabled by default | `CLICKHOUSE_URL`, `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_DATABASE`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` |
| MinIO API | `localhost` | `9010` | default S3-compatible backtest artifact target with local fallback safety | `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `S3_ENDPOINT`, `S3_REGION`, `S3_FORCE_PATH_STYLE` |
| MinIO Console | `localhost` | `9011` | object-storage admin UI | `MINIO_CONSOLE_URL` |

PostgreSQL remains the active transactional database/persistence path today, and backtests still keep their current
PostgreSQL-backed metadata and legacy JSON fields for compatibility and rollback. ClickHouse and MinIO are live
locally and auto-discovered through environment variables. The checked-in stack now enables the MinIO-backed backtest
artifact path by default while leaving ClickHouse disabled:

- `BACKTEST_ARTIFACT_STORAGE_ENABLED=true`
- `BACKTEST_CLICKHOUSE_WRITES_ENABLED=false`
- `BACKTEST_MINIO_ARTIFACTS_ENABLED=true`

## Repository Structure

The current project is organized around service ownership plus shared deployment/config assets:

- `frontend/`: React 19 + TypeScript + Vite UI. Builds the client portal, backoffice portal, and IB portal from `frontend/apps/*` with shared source in `frontend/src/*` and shared exports in `frontend/packages/*`.
- `backend/`: Go API gateway/orchestration service. Runtime entry point is `backend/cmd/server`, app-facing route ownership is under `backend/internal/routes`, and PostgreSQL migrations live in `backend/migrations/postgres`.
- `bot/`: Python FastAPI control plane and trading runtime. API assembly is `bot/src/api/server.py`, worker startup is `bot/src/main_instance.py`, and lifecycle ownership is `bot/src/bot_instance_manager.py`.
- `config/`: Encrypted structured runtime profiles plus examples. Root `run.json` is generated from this flow and is not hand-maintained.
- `docker/`: Dockerfiles and Nginx config for service images.
- `platform/`: Platform registry metadata and service deployment descriptors.
- `deploy/`: Rendered deployment output and deployment history.
- `scripts/`: Repository-level operational, config, validation, and backtest helper scripts.
- `docs/`: Wiki-style platform documentation and rollout/audit notes.

## Quick Start

### 1. Prepare runtime config

```bash
make config-keygen
make dev-config
make dev
```

The structured profile flow populates the standard local aliases above. `.env.example` remains a compatibility example, but the encrypted profile under `config/profiles/` is the canonical startup source.

Optional backtest adapter flags belong in the structured profile too. Checked-in local/dev defaults keep PostgreSQL as
the transactional source of truth, enable MinIO-backed backtest artifacts with local fallback safety, and still leave
ClickHouse disabled until explicitly validated.

### 2. Choose your local workflow

#### Service-first development (recommended for daily work)

```bash
make infra-up
make infra-ps
make infra-logs
```

Then start the service you are actively developing:

- frontend: `cd frontend && npm install && npm run dev`
- backend: `cd backend && make run`
- bot API: `cd bot && make local-api`
- bot worker: `cd bot && make local-worker`

When finished:

- stop infra: `make infra-down`

#### Full integration stack (frontend + backend + bot + infra)

```bash
make stack-up-dev
make stack-ps
make stack-logs
```

When finished:

- stop stack: `make stack-down`

## Documentation Map

- [Platform Wiki Home](docs/README.md)
- [Platform Overview](docs/PLATFORM.md)
- [Development Workflow](docs/DEVELOPMENT.md)
- [Operations Guide](docs/OPERATIONS.md)
- [Current Arbitrage Analysis](docs/current-project-arbitrage-analysis.md)
- [Arbitrage Improvement Plan](docs/project-specific-arbitrage-improvement-plan.md)
- [Arbitrage Final Report](docs/codex-final-report.md)
- [Arbitrage Phase 2 Rollout Playbook](docs/arbitrage-phase2-rollout-playbook.md)
- [Arbitrage Day-1 Rollout Command Sheet](docs/arbitrage-day1-rollout-command-sheet.md)
- [Documentation Governance](docs/DOCUMENTATION_GOVERNANCE.md)
- [Frontend Service Doc](frontend/README.md)
- [Backend Service Doc](backend/README.md)
- [Bot Service Doc](bot/README.md)
- [Shared Config Doc](config/README.md)

## Nomad-native deployment option

If you want to run the job-based path directly under `deploy/nomad/`:

- `deploy/nomad/dydx-trading-bot.nomad.hcl`
- `deploy/nomad/README.md`

This path submits a real Nomad job (`nomad job run ...`) so allocations and status appear in `/ui/jobs`.

## Core Rules

- the frontend communicates with the backend only
- the backend owns the frontend-facing contract
- the bot owns runtime execution and exchange connectivity
- structured config in `config/profiles/` is the source of truth for local and deployed startup

## Development Notes

- use the root `Makefile` for stack workflows
- use each service `README.md` for service-specific commands and responsibilities
- treat generated artifacts such as `bot/openapi.json` as canonical contracts when detailed schema accuracy matters
- run `python3 scripts/validate_docs_governance.py` before merge for doc/contract changes
- run `python3 scripts/validate_stack_env.py --environment development` after structured-config changes

## Local Troubleshooting

- PostgreSQL not ready: `docker exec dydx-postgresql pg_isready -U dydx_bot -d dydx_bot`
- Valkey not ready: `docker exec dydx-valkey valkey-cli ping`
- NATS not ready: `curl http://localhost:8222/healthz`
- ClickHouse not ready: `curl http://localhost:8123/ping`
- MinIO not ready: `curl http://localhost:9010/minio/health/live`
- Compose syntax validation: `docker compose -f docker-compose.infra.yml config` and `docker compose -f docker-compose.stack.yml config`

Backtest runtime tuning note: active long-running backtests refresh their heartbeat periodically to avoid false stale
classification. `BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS` controls that cadence, and staging already pins it in
`deploy/k8s/dydx-trading-bot-staging.yaml`.

If a legacy backtest cannot be restarted because its original request blob is missing, use
`bot/scripts/repair_backtest_requests.py` to backfill the restart payload from persisted run fields first.

## Arbitrage Improvement Flags

New live-arbitrage efficiency behavior is disabled by default. These env vars are startup
defaults; admin users can now manage the persisted runtime values from
`Settings -> Arbitrage Runtime`.

- `ARBITRAGE_IMPROVEMENTS_ENABLED=false`
- `PAIR_PRIORITY_ENGINE_ENABLED=false`
- `POLYMARKET_SIGNALS_ENABLED=false`
- `DEFILLAMA_SIGNALS_ENABLED=false`
- `NEWS_SIGNALS_ENABLED=false`
- `AUTO_EXECUTION_CHANGES_ENABLED=false`

See `.env.example` for optional TTL and pair-priority tuning values.

Authenticated diagnostics are exposed through the backend at:

- `GET /api/v1/arbitrage/improvement-metrics`
- `GET /api/v1/arbitrage/pair-priority?limit=10`
- `GET /api/v1/arbitrage/opportunity/:id/explain`
- `GET /api/v1/settings/arbitrage-runtime`
- `PUT /api/v1/settings/arbitrage-runtime`

Bot-local runtime diagnostics are also exposed for service probing and platform health wiring:

- `GET /metrics` (bot service)

The bot `/metrics` payload now includes additive `arbitrage.rejection_reasons` buckets
alongside existing counters to explain why opportunities were rejected.

## Arbitrage Intelligence Operator Playbook

Use the non-embedded bot manager panel and diagnostics endpoints to improve results
without changing core strategy logic.

1. **Baseline first (flags off)**

- Keep all new flags off initially.
- Capture 30-60 minutes of metrics from:
  - `GET /api/v1/arbitrage/improvement-metrics`
  - `GET /api/v1/arbitrage/pair-priority?limit=10`

1. **Enable safe efficiency improvements**

- Turn on `ARBITRAGE_IMPROVEMENTS_ENABLED=true`.
- Watch for upward trend in:
  - `exchange_api_calls_saved_total`
  - `duplicate_api_calls_avoided_total`
- Validate `provider_errors_total` does not rise materially.

1. **Use rejection reasons to remove waste**

- In the panel, inspect top rejection reasons and click for explainability.
- For repeated `min_order_size` or `market_already_open`, reduce low-value scan pressure before changing any execution logic.

1. **Turn on pair priority cautiously**

- Enable `PAIR_PRIORITY_ENGINE_ENABLED=true` in testnet/staging first.
- Start with `PAIR_PRIORITY_MAX_PAIRS=0` (no cap), then gradually apply caps.
- Verify opportunity quality remains stable while API calls per scan decline.

1. **Keep execution behavior unchanged by default**

- Leave `AUTO_EXECUTION_CHANGES_ENABLED=false` unless explicitly testing a reviewed release plan.

Suggested weekly KPI review:

- API efficiency: saved calls / total calls
- Opportunity quality: executed / detected
- Rejection concentration: top 3 rejection reasons share
- Stability: provider errors, stale-data detections, reconnect counts

The non-embedded bot manager screen displays diagnostics, and the admin settings screen saves
runtime flags to the backend database before syncing them to the bot process. dYdX keys and
provider API secrets still use the existing encrypted credential flows, not plain settings rows.
