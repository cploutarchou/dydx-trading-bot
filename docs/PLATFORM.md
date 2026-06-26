# Platform Overview

This repository is organized around three runtime services and shared deployment/config assets:

- `frontend/` — public UI, auth flows, and operator dashboards
- `backend/` — API gateway, orchestration, and bot proxy
- `bot/` — Python control plane, backtest runtime, and live workers

## Core flow

`frontend -> backend -> bot -> exchange/runtime`

## Key references

- [Platform Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
- [Root repository README](/home/chris/workspace/dydx-trading-bot/README.md)
- [Bot service README](/home/chris/workspace/dydx-trading-bot/bot/README.md)
- [Backend service README](/home/chris/workspace/dydx-trading-bot/backend/README.md)
- [Frontend service README](/home/chris/workspace/dydx-trading-bot/frontend/README.md)

## Backtest runtime note

Long-running backtests refresh their heartbeat periodically to avoid false stale classification. The keepalive cadence is
controlled by `BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS`.

## Local docs

- [Database migrations audit](database-migrations.md)
- [Database migration audit](database-migration-audit.md)
- [MySQL to PostgreSQL migration report](mysql-to-postgres-migration-report.md)
- [Scripts usage audit](scripts-usage-audit.md)
- [Admin coming soon and light theme plan](admin-coming-soon-and-light-theme-plan.md)
