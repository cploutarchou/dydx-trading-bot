# dYdX Trading Bot Monorepo

This repository contains a full-stack trading system with **3 application services** plus infrastructure.

## New developer onboarding (5 minutes)

Use this checklist to get productive quickly:

1. Open `dydx-monorepo.code-workspace` in VS Code.
2. Copy stack env defaults once: `make stack-env`.
3. Start local services: `make stack-up-dev`.
4. Verify service health: `make stack-ps`.
5. Start your service from **Run and Debug**:
	- `Frontend (Vite :5173)` for UI work
	- `Backend API (FastAPI :8889)` for API/control-plane work
	- `Bot Worker (instance bot-1)` for trading runtime work
6. Follow logs as needed: `make stack-logs`.
7. Stop services when done: `make stack-down`.

Tip: if you only work on one area, use `dydx-frontend.code-workspace` or `dydx-backend.code-workspace`.

**Prefer containerized tooling?** Devcontainer configs are ready to use — open the repo (or a sub-folder) in VS Code and select "Reopen in Container" to get a fully configured environment without manual dependency setup:
- Root `.devcontainer/` — full-stack (Python + Node + Docker-in-Docker)
- `bot/.devcontainer/` — Python/API/worker focused
- `frontend/.devcontainer/` — Node 20/React/TS focused

## What the 3 apps do

### 1) Frontend (`frontend/`)

React + TypeScript + Vite dashboard used to:

- log in and manage bot instances
- run backtests and inspect results
- monitor status through API-driven views

### 2) Bot API (`bot/`)

FastAPI service used as the control plane:

- authentication and session endpoints
- bot instance lifecycle (create/start/stop/status)
- backtest/strategy compatibility endpoints for the UI
- data access and orchestration between UI and workers

### 3) Worker (`bot/src/main_instance.py`)

Python trading runtime process that executes strategy logic:

- market data polling
- signal generation (cointegration/z-score flow)
- position open/close management
- per-instance runtime/state behavior

> Infrastructure used by these apps: **PostgreSQL** + **Redis**.

---

## Architecture at a glance

- `frontend` calls `api`
- `api` manages worker instances and persistence
- `worker` runs trading loops and execution logic
- `postgres` and `redis` support state, metadata, and caching

---

## Quickstart (Development)

### Prerequisites

- Docker + Docker Compose
- Make

### 1) Create stack env file

```bash
make stack-env
```

This creates `.env.stack` from `.env.stack.example` (if missing).

### 2) Start the dev stack

```bash
make stack-up-dev
```

Starts:

- `frontend` on `http://localhost:5173`
- `api` on `http://localhost:8889`
- `worker` (trading execution service)
- `postgres` and `redis`

### 3) Verify services

```bash
make stack-ps
```

### 4) View logs

```bash
make stack-logs
```

### 5) Stop everything

```bash
make stack-down
```

---

## Quickstart (Prod-like local run)

Use the prod profile to run frontend behind Nginx proxy:

```bash
make stack-up-prod
```

- proxy entrypoint: `http://localhost:8080` (default)
- frontend and API are routed behind proxy

---

## Useful commands

- `make stack-env` – create `.env.stack` template
- `make stack-up-dev` – start dev profile
- `make stack-up-prod` – start prod profile (with proxy)
- `make stack-ps` – status
- `make stack-logs` – tail logs
- `make stack-down` – stop stack

---

## Running each service

Each service can be started three ways: **via the full Docker stack** (recommended for integration), **locally** (fastest iteration loop), or **via VS Code** (with debugger attached).

---

### Frontend (`frontend/`)

**Port:** `http://localhost:5173`

**Prerequisites:** Node 18+ and npm.

```bash
# Install dependencies (first time only)
cd frontend
npm install
```

| Method | Command |
|---|---|
| Local dev | `cd frontend && npm run dev` |
| Build for production | `cd frontend && npm run build` |
| Lint | `cd frontend && npm run lint` |
| Full stack | `make stack-up-dev` (from repo root) |
| VS Code | Run & Debug → `Frontend (Vite :5173)` |

---

### Bot API (`bot/`)

**Port:** `http://localhost:8889`

**Prerequisites:** Python 3.11+.

```bash
# Install dependencies (first time only)
cd bot
pip install -r requirements.txt

# Copy and configure env (first time only)
cp example.env .env
# Edit .env — set DB, Redis, and any API credentials
```

| Method | Command |
|---|---|
| Local dev (with reload) | `cd bot && python3 -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload` |
| Full stack | `make stack-up-dev` (from repo root) |
| VS Code | Run & Debug → `Backend API (FastAPI :8889)` |
| Run tests | `cd bot && python3 -m pytest tests/ -v` |

Health check: `curl http://localhost:8889/health`

---

### Bot Worker (`bot/src/main_instance.py`)

The worker is a long-running process — one per trading instance. It shares the same Python env and `.env` as the Bot API.

| Method | Command |
|---|---|
| Local | `cd bot && python3 src/main_instance.py --instance-id bot-1` |
| Full stack | Starts automatically with `make stack-up-dev` |
| VS Code | Run & Debug → `Bot Worker (instance bot-1)` |
| Multiple instances | Repeat with a different `--instance-id` value |

State files are written to `bot/bot_states/` per instance.

---

### Go Backend (`backend/`) — legacy

**Port:** `http://localhost:8888`

**Prerequisites:** Go 1.21+. For hot-reload, install [`air`](https://github.com/air-verse/air): `go install github.com/air-verse/air@latest`.

| Method | Command |
|---|---|
| Run | `cd backend && make run` |
| Run with hot-reload | `cd backend && make dev` |
| Build binary | `cd backend && make build` |
| Tests | `cd backend && make test` |
| Lint | `cd backend && make lint` |

> The Go backend is a legacy/parallel path. The primary control plane for the UI is the Python Bot API.

---

## Developer setup (VS Code)

This repository is configured so frontend and backend teams can work in a shared setup without opening separate random folders manually.

### Recommended workspace files

- `dydx-monorepo.code-workspace` → default for most contributors (full repo)
- `dydx-frontend.code-workspace` → frontend-focused view
- `dydx-backend.code-workspace` → backend-focused view (`bot` + legacy `backend`)

Open one of these files directly in VS Code.

### Shared Run/Debug profiles (one per service)

From **Run and Debug**, use:

- `Frontend (Vite :5173)`
- `Backend API (FastAPI :8889)`
- `Bot Worker (instance bot-1)`

These are defined in `.vscode/launch.json` and are team-shared.

### Shared tasks

From **Terminal → Run Task**, use team tasks in `.vscode/tasks.json`:

- `stack: up dev`
- `stack: down`
- `stack: logs`
- `frontend: dev`
- `bot: api`
- `bot: worker`

### Typical team workflow

1. Open `dydx-monorepo.code-workspace`.
2. Start infra/app stack with `stack: up dev` (or `make stack-up-dev`).
3. Frontend team runs `Frontend (Vite :5173)`.
4. Backend team runs `Backend API (FastAPI :8889)` and/or `Bot Worker (instance bot-1)`.
5. Validate with `make stack-ps` and `make stack-logs`.

---

## Notes

- The repository also contains a Go backend in `backend/` for legacy/parallel backend work.
- Current UI-to-bot control flow in this workspace is centered around the Python Bot API under `bot/`.

---

## Troubleshooting first-run issues

**Stack won't start / Docker error**
- Make sure Docker daemon is running: `docker info`
- Ensure no port conflicts: `lsof -i :5173,8889,5432,6379`

**Missing `.env.stack` error**
- Run `make stack-env` to generate it from the example template, then edit any required secrets.

**Service stays unhealthy**
- Check logs: `make stack-logs`
- Check per-service status: `make stack-ps`
- If Postgres fails to start, ensure no existing local Postgres is using port 5432.

**Port already in use**
- Frontend 5173: `kill $(lsof -ti :5173)`
- Bot API 8889: `kill $(lsof -ti :8889)`

**VS Code debug profile won't launch**
- Open the repo via a `.code-workspace` file (not a plain folder) so `.vscode/launch.json` is picked up.
- Confirm the correct Python interpreter or Node executable is on `PATH` inside your terminal.

**Devcontainer not building**
- Run `docker system prune` to clear stale layers, then rebuild via VS Code command palette → "Dev Containers: Rebuild Container".
