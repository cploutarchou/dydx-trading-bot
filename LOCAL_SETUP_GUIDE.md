# Local Environment Setup Guide

This guide explains how to set up your local development environment for the dYdX Trading Bot. You have **two options** depending on your workflow.

## Prerequisites

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

- **PostgreSQL** (main database): `localhost:5432`
- **Valkey** (Redis-compatible cache): `localhost:6379`
- **NATS JetStream** (event/command bus): `localhost:4222` (monitoring: `8222`)
- **ClickHouse** (analytics database): `localhost:8123`
- **MinIO** (object storage): `localhost:9010` (API), `localhost:9011` (console)

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

# Bot Worker (Celery/NATS Backtest Worker)
cd bot && python worker_entrypoint.py
# → Processes backtest jobs
```

### Service Environment Variables

Each service automatically discovers the infrastructure using these defaults:

```
DATABASE_HOST=localhost
DATABASE_PORT=5432
REDIS_HOST=localhost
REDIS_PORT=6379
NATS_URL=nats://localhost:4222
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
MINIO_HOST=localhost
MINIO_PORT=9000
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
- ✅ Matches production infrastructure (PostgreSQL, Valkey, NATS, ClickHouse, MinIO)

---

## 🚀 Option 2: Full Stack (Production-like Replication)

**Use this if you need to test the entire platform end-to-end or work on integration issues.**

All services run in Docker containers, fully replicating your production k3s environment:

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
- **ClickHouse**: `localhost:8123`, API: `9000`
- **MinIO**: `localhost:9010` (API), `localhost:9011` (console)

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
export DATABASE_HOST=localhost
export DATABASE_PORT=5432
export REDIS_HOST=localhost
export REDIS_PORT=6379
export NATS_URL=nats://localhost:4222
export CLICKHOUSE_HOST=localhost
export MINIO_HOST=localhost
```

### For Option 2 (Full Stack)

All environment variables are managed by docker-compose. Override defaults:

```bash
# Before stack-up-dev
export DATABASE_PASSWORD=my-secure-password
export MINIO_ROOT_PASSWORD=my-minio-password
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
```

### MinIO access issues

```bash
# MinIO console
http://localhost:9011
# Default credentials: minioadmin / change-me-minio

# Create a test bucket
docker exec dydx-minio mc mb minio/dydx-artifacts
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

# From bot directory
cd bot && python -m src.infrastructure.backtest.run_backtest \
  --start 2024-01-01 \
  --end 2024-03-31 \
  --pairs 5

# Or use the Makefile target from root
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
curl http://localhost:8888/api/health
curl http://localhost:8889/health
```

---

## 🚨 Important Notes

### Configuration

- Both options use the same `run.json` generated from `make dev`
- Environment variables are loaded from both `run.json` and shell environment
- For Option 2, docker-compose provides infrastructure endpoints via service names

### Database Migrations

- Migrations run automatically on service startup
- Both PostgreSQL and Valkey data persist between restarts
- State is stored in Docker volumes for Option 2

### Data Persistence

- Option 1: Data persists in system databases
- Option 2: Data persists in Docker volumes named `<name>_data`

### Clean Slate

```bash
# Option 1: Stop and clean
make infra-down
docker volume rm dydx-infra_postgresql_data dydx-infra_valkey_data

# Option 2: Stop and clean
make stack-down
docker volume rm dydx-stack_postgresql_data dydx-stack_valkey_data
```

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
