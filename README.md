# dYdX Trading Bot Monorepo

This repository contains a full-stack trading system with **3 application services** plus infrastructure.

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

## Notes

- The repository also contains a Go backend in `backend/` for legacy/parallel backend work.
- Current UI-to-bot control flow in this workspace is centered around the Python Bot API under `bot/`.
