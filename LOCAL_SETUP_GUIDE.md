# Local Environment Setup Guide

This guide explains how to set up your local development environment for the dYdX Trading Bot. You have **two options** depending on your workflow.

## Prerequisites

### Windows PowerShell

The root Makefile can be invoked directly from PowerShell. On Windows it prefers
Git Bash (so Docker Desktop remains on the recipe PATH) and falls back to an
installed MSYS2 Bash for its POSIX recipes. Verify the detected shell and
optionally enable target completion:

```powershell
make windows-check
make install-completion-powershell
# Restart PowerShell, then type: make <Tab>
```

For completion in only the current session, run
`. .\scripts\powershell\MakeCompletion.ps1`. PowerShell 7 users can install
into their PowerShell 7 profile with
`make install-completion-powershell POWERSHELL=pwsh`.

```bash
# 1. One-time setup: create config encryption key
make config-keygen

# 2. Configure development environment
make dev-config

# 3. Prepare run.json
make dev
```

---

## 🔧 Option 1: Infrastructure Only (Recommended for Service Development)

**Use this if you're developing a specific service (frontend, backend, or bot) locally.**

Infrastructure services are based on the **k3s-next production architecture**, running locally:

| Service | Host | Port | Purpose | Environment variables |
| --- | --- | --- | --- | --- |
| PostgreSQL | `localhost` | `5432` | server hosting separate `dydx_bot` (backend) and `dydx_bot_runtime` (bot) databases | `DATABASE_URL`, `POSTGRES_*`, `DB_*`, `BOT_DATABASE_URL`, `BOT_DB_*` |
| Valkey | `localhost` | `6379` | Redis-compatible cache/broker surface for existing Celery, lock, and cache flows | `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `VALKEY_HOST`, `VALKEY_PORT`, `CELERY_*` |
| NATS JetStream | `localhost` | `4222` | durable backtest events; command execution is cutover-gated and off while Celery owns execution | `NATS_URL`, `NATS_ENABLED`, `BOT_COMMAND_BUS_ENABLED` |
| NATS monitoring | `localhost` | `8222` | health and operator visibility | `NATS_MONITORING_URL` |
| ClickHouse HTTP | `localhost` | `8123` | derived analytics target; application defaults are off unless the profile/stack enables it | `CLICKHOUSE_URL`, `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_DATABASE`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` |
| MinIO API | `localhost` | `9010` | object artifacts; application defaults are off unless the profile/stack enables it | `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `S3_ENDPOINT`, `S3_REGION`, `S3_FORCE_PATH_STYLE` |
| MinIO Console | `localhost` | `9011` | bucket/object admin UI | `MINIO_CONSOLE_URL` |

PostgreSQL is authoritative for application and backtest state. Valkey is temporary cache/Celery transport. The
development structured profile and full Compose stack enable MinIO artifacts and ClickHouse projections; application
code defaults those adapters off when no explicit profile/env flag is present. NATS events may be enabled independently,
but keep `BOT_COMMAND_BUS_ENABLED=false` until Celery-to-NATS execution cutover is intentionally performed.

### Start Infrastructure

```bash
make infra-up
```

### Check Status

```bash
make infra-ps      # List running containers
make infra-logs    # Follow logs
```

### Develop Individual Services

In separate terminal tabs, each service talks to the shared infrastructure:

```bash
# Frontend (React + Vite)
cd frontend && npm install && npm run dev
# → Runs on http://localhost:5173

# Backend (Go API Gateway)
cd backend && make run
# → Runs on http://localhost:8888

# Bot (Python FastAPI Control Plane)
cd bot && python -m uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8889
# → Runs on http://localhost:8889

# Bot Worker (Celery backtest worker)
cd bot && make local-worker
# → Processes backtest jobs
```

### Service Environment Variables

Each service automatically discovers the infrastructure using these defaults:

```
DATABASE_URL=postgres://dydx_bot:change-me-db-password@localhost:5432/dydx_bot?sslmode=disable
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=dydx_bot
POSTGRES_USER=dydx_bot
POSTGRES_PASSWORD=change-me-db-password
BOT_POSTGRES_DB=dydx_bot_runtime
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dydx_bot
DB_USER=dydx_bot
DB_PASSWORD=change-me-db-password
BOT_DB_CUTOVER_MODE=dedicated
BOT_DATABASE_URL=postgresql+psycopg2://dydx_bot:change-me-db-password@localhost:5432/dydx_bot_runtime?sslmode=disable
BOT_DB_HOST=localhost
BOT_DB_PORT=5432
BOT_DB_NAME=dydx_bot_runtime
BOT_DB_USER=dydx_bot
BOT_DB_PASSWORD=change-me-db-password
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
VALKEY_HOST=localhost
VALKEY_PORT=6379
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
NATS_URL=nats://localhost:4222
NATS_MONITORING_URL=http://localhost:8222
BOT_COMMAND_BUS_ENABLED=false
CLICKHOUSE_URL=http://localhost:8123
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_ENABLED=true
CLICKHOUSE_SECURE=false
MINIO_ENDPOINT=localhost:9010
MINIO_CONSOLE_URL=http://localhost:9011
MINIO_BUCKET=backtests
MINIO_ENABLED=true
S3_ENDPOINT=http://localhost:9010
S3_REGION=us-east-1
S3_FORCE_PATH_STYLE=true
BACKTEST_ARTIFACT_STORAGE_ENABLED=true
BACKTEST_CLICKHOUSE_WRITES_ENABLED=true
BACKTEST_MINIO_ARTIFACTS_ENABLED=true
```

### Stop Infrastructure

```bash
make infra-down
```

**Advantages:**

- ✅ Hot reload for services
- ✅ Faster development cycles
- ✅ Easy debugging with local IDE
- ✅ Independent service testing
- ✅ Low resource consumption
- ✅ Matches the available local infrastructure contract without forcing every service into active app use

---

## 🚀 Option 2: Full Integration Stack

**Use this if you need to test the entire platform end-to-end or work on integration issues.**

All services run in Docker containers with local-only credentials and ports. This validates service integration but is
not a security-equivalent production deployment.

### Start Full Stack

```bash
make stack-up-dev
```

This starts **all services in isolated containers**:

#### Application Layer

- **Frontend**: `http://localhost:5173` (Nginx)
- **Backend API**: `http://localhost:8888` (Go)
- **Bot API**: `http://localhost:8889` (Python)
- **Bot Worker**: Processing backtest jobs

#### Infrastructure Layer

- **PostgreSQL**: `localhost:5432`
- **Valkey**: `localhost:6379`
- **NATS JetStream**: `localhost:4222`, monitoring: `8222`
- **ClickHouse HTTP**: `localhost:8123`
- **MinIO**: `localhost:9010` (API), `localhost:9011` (console)

Checked-in stack defaults keep PostgreSQL authoritative and explicitly enable the MinIO artifact and ClickHouse derived
analytics paths. The bot `/ready` endpoint reports both adapters; strict MinIO failures block readiness.

### Check Status

```bash
make stack-ps      # List all running services
make stack-logs    # Follow all logs
```

### Access Services

```
Frontend:           http://localhost:5173
Backend API:        http://localhost:8888
Bot API:            http://localhost:8889
MinIO Console:      http://localhost:9011
NATS Monitoring:    http://localhost:8222
```

### Stop Full Stack

```bash
make stack-down
```

**Advantages:**

- ✅ Full integration testing
- ✅ Production-like environment
- ✅ Services isolated in containers
- ✅ No port conflicts with local development
- ✅ Easier to replicate production issues
- ✅ All infrastructure managed automatically

---

## 📊 Quick Comparison

| Feature             | Option 1 (Infra)                   | Option 2 (Full Stack)                  |
| ------------------- | ---------------------------------- | -------------------------------------- |
| **Best for**        | Active development of one service  | Integration testing / end-to-end flows |
| **Hot reload**      | ✅ Yes (local dev)                 | ❌ No (Docker containers)              |
| **Resource usage**  | 💚 Low                             | 🔴 High                                |
| **Setup time**      | ⚡ Fast                            | ⏱️ Slower (builds images)              |
| **Debugging**       | 🔍 Local IDE debuggers             | 🔧 Docker logs/exec                    |
| **Port conflicts**  | ⚠️ Possible (services run locally) | ✅ No (isolated containers)            |
| **Database access** | Direct to PostgreSQL/Valkey        | Via Docker containers                  |
| **Frontend dev**    | `npm run dev` (Vite HMR)           | Via Nginx in Docker                    |

---

## 🔄 Switching Between Options

### From Option 1 → Option 2

```bash
# Stop your local services (Ctrl+C in their terminal tabs)
# Stop infrastructure
make infra-down

# Start full stack
make stack-up-dev
```

### From Option 2 → Option 1

```bash
# Stop full stack
make stack-down

# Start infrastructure only
make infra-up

# Start your services individually
```

---

## 📝 Environment Variables & Configuration

### For Option 1 (Infra Only)

Services automatically discover infrastructure on localhost. If you need to override, set:

```bash
export DATABASE_URL=postgres://dydx_bot:change-me-db-password@localhost:5432/dydx_bot?sslmode=disable
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=dydx_bot
export POSTGRES_USER=dydx_bot
export POSTGRES_PASSWORD=change-me-db-password
export BOT_POSTGRES_DB=dydx_bot_runtime
export BOT_DB_CUTOVER_MODE=dedicated
export BOT_DATABASE_URL=postgresql+psycopg2://dydx_bot:change-me-db-password@localhost:5432/dydx_bot_runtime?sslmode=disable
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_URL=redis://localhost:6379/0
export VALKEY_HOST=localhost
export VALKEY_PORT=6379
export NATS_URL=nats://localhost:4222
export NATS_MONITORING_URL=http://localhost:8222
export CLICKHOUSE_URL=http://localhost:8123
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=8123
export MINIO_ENDPOINT=localhost:9010
export MINIO_CONSOLE_URL=http://localhost:9011
export MINIO_BUCKET=backtests
export S3_ENDPOINT=http://localhost:9010
export S3_REGION=us-east-1
export S3_FORCE_PATH_STYLE=true
```

### For Option 2 (Full Stack)

All environment variables are managed by docker-compose. Override defaults:

```bash
# Before stack-up-dev
export POSTGRES_PASSWORD=my-secure-password
export MINIO_SECRET_KEY=my-minio-password
make stack-up-dev
```

---

## 🐛 Troubleshooting

### Docker daemon not running

```bash
# Check Docker status
docker ps

# If it fails, start Docker daemon (system dependent)
```

### Port already in use

```bash
# Find what's using the port (e.g., 5173)
lsof -i :5173

# Kill the process if needed
kill -9 <PID>
```

### Infrastructure containers not healthy

```bash
# Check individual service health
make infra-ps

# Restart all infra
make infra-down && make infra-up

# Check logs for a specific service
docker logs dydx-postgresql
docker logs dydx-valkey
docker logs dydx-nats
docker logs dydx-clickhouse
docker logs dydx-minio
```

### Full stack services failing to start

```bash
# Validate your configuration
make stack-env-check

# Check Docker build logs
docker logs dydx-backend-api
docker logs dydx-bot-api
docker logs dydx-frontend

# Force rebuild services
make images-build
make stack-up-dev
```

### Database connection errors

```bash
# Verify PostgreSQL is running and accessible
docker exec dydx-postgresql psql -U dydx_bot -d dydx_bot -c "SELECT 1;"

# Check Valkey
docker exec dydx-valkey valkey-cli ping

# Check NATS
curl http://localhost:8222/healthz

# Check ClickHouse
curl http://localhost:8123/ping

# Check MinIO
curl http://localhost:9010/minio/health/live
```

### MinIO access issues

```bash
# MinIO console: http://localhost:9011
# Default local credentials: change-me-minio-access-key / change-me-minio-secret-key
```

---

## 📝 Common Development Workflows

### Frontend Development

```bash
# Terminal 1: Infrastructure
make infra-up

# Terminal 2: Frontend with hot reload
cd frontend && npm run dev
```

### Backend Development

```bash
# Terminal 1: Infrastructure
make infra-up

# Terminal 2: Backend API
cd backend && make run
```

### Bot Development

```bash
# Terminal 1: Infrastructure
make infra-up

# Terminal 2: Bot API
cd bot && python -m uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8889

# Terminal 3 (optional): Bot Worker for backtests
cd bot && python worker_entrypoint.py
```

### Running Backtests

```bash
# Make sure infrastructure is running
make infra-up

# From the repository root
make backtest START=2024-01-01 END=2024-03-31 PAIRS=5
```

### Full Integration Testing

```bash
# Terminal 1: Full stack (all services in containers)
make stack-up-dev
make stack-ps

# Terminal 2: Follow logs
make stack-logs

# Terminal 3: Test API endpoints
curl http://localhost:8888/health
curl http://localhost:8888/ready
curl http://localhost:8889/health
```

---

## 🚨 Important Notes

### Configuration

- Both options use the same `run.json` generated from `make dev`
- Environment variables are loaded from both `run.json` and shell environment
- For Option 2, docker-compose provides infrastructure endpoints via service names

### Database Migrations

- The full local stack sets `DB_AUTO_MIGRATE=true` for the Go backend. Standalone backend startup defaults migration
  execution off; run `cd backend && make migrate-up` first or explicitly set `DB_AUTO_MIGRATE=true` for local use.
- The bot applies Alembic before ORM compatibility creation, verifies runtime-critical tables (including durable
  tracked-position and cointegration state), and currently reports `0004_runtime_state_tables` at the PostgreSQL head.
- Celery uses Valkey DB 1 for its broker and DB 2 for results in both API and worker processes; DB 0 remains the
  application cache/session namespace.
- PostgreSQL and Valkey data persist between restarts; all five infrastructure systems use named Compose volumes.

### Data Persistence

- Option 1: Data persists in system databases
- Option 2: Data persists in Docker volumes named `<name>_data`

### Clean Slate (destructive, explicit opt-in)

```bash
# Inventory data and volumes first; these commands do not delete anything.
docker compose -f docker-compose.infra.yml ps
docker volume ls | grep dydx-trading-bot
docker exec dydx-postgresql pg_dump -U dydx_bot -d dydx_bot -Fc > dydx_bot.backup

# Only after confirming/exporting required data, stop services.
make infra-down   # or: make stack-down

# Destructive reset is intentionally not automated by this guide. If a clean reset is truly
# required, an operator must explicitly remove the five reviewed named volumes.
```

Never remove PostgreSQL, Valkey, NATS, ClickHouse, or MinIO volumes merely to fix startup. Restart/recreate containers
first; named volumes survive `make infra-down` and `make stack-down`.

---

## 📚 Additional Commands

```bash
# Show all available commands
make help

# View specific service help
cd backend && make help
cd frontend && npm run
cd bot && make help

# Config management
make show-config-token      # Display shareable config token
make config-key-rotate      # Rotate encryption key

# Database utilities
make migration-up           # Run pending migrations
make migration-verify       # Show migration status
```

---

## 🎯 Next Steps

1. **Choose your workflow**: Option 1 (infra) or Option 2 (full stack)
2. **Start infrastructure/stack**: `make infra-up` or `make stack-up-dev`
3. **Start developing**: Launch your service(s)
4. **Test locally** with your chosen approach
5. **For integration issues**: Switch to the other approach to verify

## 📖 Architecture Reference

See [deploy/k8s-next/README.md](deploy/k8s-next/README.md) for details on the production k3s architecture that these local setups replicate.

Happy coding! 🚀
