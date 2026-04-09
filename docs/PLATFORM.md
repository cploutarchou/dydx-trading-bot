# Platform Overview

## Runtime Topology

The active stack is a three-service monorepo:

`frontend -> backend -> bot -> exchange/runtime`

Supporting infrastructure:

- backend PostgreSQL on `localhost:5432`
- bot PostgreSQL on `localhost:5433`
- Redis on `localhost:6379`

## Service Boundaries

### Frontend

- React 19 + TypeScript + Vite operator workspace and public website
- consumes HTTP and websocket traffic from the Go backend only
- never talks directly to the Python bot service in normal product flows

### Backend

- public application API for the frontend
- authentication, orchestration, persistence, and delegation layer
- proxies bot HTTP and websocket channels
- owns the frontend-facing contract

### Bot

- Python FastAPI control plane and trading runtime
- manages bot instances, live strategy workers, and backtests
- owns exchange connectivity and runtime execution
- persists bot/runtime state into the bot-dedicated PostgreSQL

### Shared Config

- encrypted environment profiles under `config/profiles/`
- generated runtime config in root `run.json`
- service startup always prefers structured config over ad hoc local `.env` files

## Public Surface Policy

The frontend is allowed to communicate with:

- backend HTTP routes on `:8888`
- backend websocket routes on `:8888`

The frontend is not allowed to communicate with:

- bot HTTP routes on `:8889`
- bot websocket routes on `:8889`
- direct database connections

That rule keeps auth, tracing, access control, and contract normalization in one place.

## Current Product Shape

The platform currently includes:

- public website and pricing pages
- login, registration, 2FA, and forced password-change flows
- dashboard and operator workspace shell
- strategy creation and live runtime control
- backtest execution, live progress, and live results
- live websocket-first monitoring for backtests and runtime views

## Source of Truth

Use these artifacts in order:

1. service source code
2. service `README.md`
3. this wiki
4. generated contracts such as `bot/openapi.json`

Legacy handoff notes and one-off task logs are intentionally not treated as canonical product documentation anymore.
