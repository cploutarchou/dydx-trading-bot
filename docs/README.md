# Platform Wiki Home

This folder collects platform-level notes, audits, and rollout guidance that cut across the individual service READMEs.

## Start here

- [Root repository README](/home/chris/workspace/dydx-trading-bot/README.md)
- [Bot service README](/home/chris/workspace/dydx-trading-bot/bot/README.md)
- [Backend service README](/home/chris/workspace/dydx-trading-bot/backend/README.md)
- [Frontend service README](/home/chris/workspace/dydx-trading-bot/frontend/README.md)

## Operational notes

- Backtest heartbeat tuning and stale-run behavior are documented in [bot/README.md](/home/chris/workspace/dydx-trading-bot/bot/README.md).
- Active k3s manifests now live under `deploy/k8s-next/`; the older `deploy/k8s/` single-file bundles are legacy references only.

## Local docs in this folder

- [Database migrations audit](database-migrations.md)
- [Database migration audit](database-migration-audit.md)
- [MySQL to PostgreSQL migration report](mysql-to-postgres-migration-report.md)
- [Scripts usage audit](scripts-usage-audit.md)
- [Admin coming soon and light theme plan](admin-coming-soon-and-light-theme-plan.md)
