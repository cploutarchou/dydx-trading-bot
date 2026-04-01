# dYdX Trading Bot Monorepo

This repository contains a full-stack trading system with **3 application services** plus infrastructure.

## Single environment file

Use the repo-root `.env` as the **only** shared environment file for `frontend/`, `backend/`, and `bot/`.

- `frontend` reads Vite variables like `VITE_API_URL` from the repo root
- `backend` loads the repo-root `.env` when started from either repo root or `backend/`
- `bot` entrypoints and config load the repo-root `.env`

You should not need separate `backend/.env`, `bot/.env`, or `frontend/.env.local` files for normal development.

## New developer onboarding (5 minutes)

Use this checklist to get productive quickly:

1. Open your team workspace in VS Code:
   - Frontend team → `dydx-frontend.code-workspace`
   - Bot/API team → `dydx-bot.code-workspace`
   - Backend team (Go gateway/orchestration) → `dydx-backend.code-workspace`
2. Reopen in your **service devcontainer** (`frontend/.devcontainer`, `bot/.devcontainer`, or `backend/.devcontainer`).
3. Start shared infra once (from repo root):
   - `make stack-env` (first time)
   - `make infra-up`
4. Run your service from **Run and Debug** or service-local tasks.
5. For full end-to-end verification, switch to `dydx-monorepo.code-workspace` and run:
   - `make stack-up-dev`
   - `make stack-ps`
   - `make stack-logs`
6. Stop what you started when done:
   - `make stack-down` (full integration stack)
   - `make infra-down` (infra-only workflow)

Tip: daily development should be service-first. Use the monorepo workspace primarily for integration/QA/release validation.

**Prefer containerized tooling?** Devcontainer configs are ready to use — open the repo (or a sub-folder) in VS Code and select "Reopen in Container" to get a fully configured environment without manual dependency setup:

- `bot/.devcontainer/` — Python/API/worker focused
- `backend/.devcontainer/` — Go backend focused
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

Primary request path in this workspace:

- `frontend` → Go backend (`:8888`) → Python Bot API (`:8889`) → worker/runtime

The Go backend is the UI-facing API layer and triggers/orchestrates bot actions through the Python Bot API.
`postgres` and `redis` support state, metadata, and caching.

---

## Quickstart (Daily service-first development)

### Prerequisites

- Docker + Docker Compose
- Make

### 1) Open your service workspace

- Frontend team → `dydx-frontend.code-workspace`
- Bot/API team → `dydx-bot.code-workspace`
- Backend team (Go gateway/orchestration) → `dydx-backend.code-workspace`

### 2) Start shared infra only

```bash
make stack-env
make infra-up
```

This creates `.env` from `.env.example` (if missing).

### 3) Run your service locally or with service-local Run/Debug

- Frontend: `cd frontend && npm run dev`
- Bot API: `cd bot && python3 -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload`
- Bot worker: `cd bot && python3 src/main_instance.py --instance-id bot-1`
- Backend (UI gateway): `cd backend && make dev`

### 4) Stop infra when done

```bash
make infra-down
```

---

## Quickstart (Full integration stack)

Use this when validating end-to-end behavior across frontend + API + worker + infra.

### 1) Create shared env file

```bash
make stack-env
```

### 2) Start the integration stack

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

- `make stack-env` – create `.env` from `.env.example` if missing
- `make infra-up` – start shared infra only (postgres + redis)
- `make infra-down` – stop shared infra only
- `make infra-ps` – infra status
- `make infra-logs` – infra logs
- `make stack-up-dev` – start full integration dev profile
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

| Method               | Command                               |
| -------------------- | ------------------------------------- |
| Local dev            | `cd frontend && npm run dev`          |
| Build for production | `cd frontend && npm run build`        |
| Lint                 | `cd frontend && npm run lint`         |
| Full stack           | `make stack-up-dev` (from repo root)  |
| VS Code              | Run & Debug → `Frontend (Vite :5173)` |

---

### Bot API (`bot/`)

**Port:** `http://localhost:8889`

**Prerequisites:** Python 3.11+.

```bash
# Install dependencies (first time only)
cd bot
pip install -r requirements.txt
```

Edit the repo-root `.env` once for DB, Redis, auth, bot, backend, and frontend values.

| Method                  | Command                                                                               |
| ----------------------- | ------------------------------------------------------------------------------------- |
| Local dev (with reload) | `cd bot && python3 -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload` |
| Full stack              | `make stack-up-dev` (from repo root)                                                  |
| VS Code                 | Run & Debug → `Backend API (FastAPI :8889)`                                           |
| Run tests               | `cd bot && python3 -m pytest tests/ -v`                                               |

Health check: `curl http://localhost:8889/health`

---

### Bot Worker (`bot/src/main_instance.py`)

The worker is a long-running process — one per trading instance. It shares the same Python env and `.env` as the Bot API.

That `.env` is the shared repo-root file.

| Method             | Command                                                      |
| ------------------ | ------------------------------------------------------------ |
| Local              | `cd bot && python3 src/main_instance.py --instance-id bot-1` |
| Full stack         | Starts automatically with `make stack-up-dev`                |
| VS Code            | Run & Debug → `Bot Worker (instance bot-1)`                  |
| Multiple instances | Repeat with a different `--instance-id` value                |

State files are written to `bot/bot_states/` per instance.

---

### Go Backend (`backend/`) — UI gateway + bot orchestration path

**Port:** `http://localhost:8888`

**Prerequisites:** Go 1.21+. For hot-reload, install [`air`](https://github.com/air-verse/air): `go install github.com/air-verse/air@latest`.

| Method              | Command                    |
| ------------------- | -------------------------- |
| Run                 | `cd backend && make run`   |
| Run with hot-reload | `cd backend && make dev`   |
| Build binary        | `cd backend && make build` |
| Tests               | `cd backend && make test`  |
| Lint                | `cd backend && make lint`  |

> The Go backend is the UI-facing gateway/proxy to the Python Bot API. In the preferred local setup, frontend targets Go backend (`:8888`), and backend triggers bot actions through Python Bot API (`:8889`).

---

## Developer setup (VS Code)

This repository is configured for **service-first daily work** and **monorepo integration verification**.

### Recommended workspace files

- `dydx-bot.code-workspace` → **default** for bot/API contributors (`bot/` only)
- `dydx-frontend.code-workspace` → **default** for frontend contributors
- `dydx-backend.code-workspace` → **default** for backend contributors (`bot` + `backend`)
- `dydx-monorepo.code-workspace` → integration/release/QA validation across services

Open one of these files directly in VS Code.

### Run/Debug profiles

Use service-local Run/Debug for daily work:

- Frontend workspace → `frontend/.vscode/launch.json`
- Bot workspace → `bot/.vscode/launch.json`
- Backend workspace → `backend/.vscode/launch.json`

Use monorepo Run/Debug for integration flow:

- `Frontend (Vite :5173)`
- `Backend API (FastAPI :8889)`
- `Bot Worker (instance bot-1)`

These are defined in root `.vscode/launch.json`.

### Tasks

Service-specific tasks live in each service workspace:

- `bot/.vscode/tasks.json`
- `frontend/.vscode/tasks.json`
- `backend/.vscode/tasks.json`

Monorepo integration tasks live in root `.vscode/tasks.json`:

- `stack: up dev`
- `stack: down`
- `stack: logs`
- `infra: up`
- `infra: down`
- `infra: logs`

### Typical team workflow

1. Open your team workspace (`dydx-bot`, `dydx-frontend`, or `dydx-backend`).
2. Reopen in that service’s devcontainer.
3. Start shared infra via `infra: up` (or `make infra-up` from repo root).
4. Run your service with service-local Run/Debug or task.
5. For end-to-end verification, open `dydx-monorepo.code-workspace` and run `stack: up dev`.

---

## Notes

- The Go backend in `backend/` is the active UI-facing API gateway and orchestration layer.
- Current UI-to-bot control flow in this workspace is: frontend → Go backend → Python Bot API.

---

## Troubleshooting first-run issues

### Stack won't start / Docker error

- Make sure Docker daemon is running: `docker info`
- Ensure no port conflicts: `lsof -i :5173,8888,8889,5432,6379`

### Missing `.env` error

- Run `make stack-env` to generate it from `.env.example`, then edit any required secrets.

### Service stays unhealthy

- Check logs: `make stack-logs`
- Check per-service status: `make stack-ps`
- If Postgres fails to start, ensure no existing local Postgres is using port 5432.

### Port already in use

- Frontend 5173: `kill $(lsof -ti :5173)`
- Go backend 8888: `kill $(lsof -ti :8888)`
- Bot API 8889: `kill $(lsof -ti :8889)`

### VS Code debug profile won't launch

- Open the correct service `.code-workspace` (or `dydx-monorepo.code-workspace` for integration) so the matching `.vscode/launch.json` is picked up.
- Confirm the correct Python interpreter or Node executable is on `PATH` inside your terminal.

### Devcontainer not building

- Run `docker system prune` to clear stale layers, then rebuild via VS Code command palette → "Dev Containers: Rebuild Container".
