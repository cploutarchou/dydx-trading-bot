# Frontend Customization Index

Use this file when the task is primarily inside the React frontend service.

## Read in this order

1. `../AGENTS.md`
2. `.github/copilot-instructions.md`
3. This file
4. The most relevant agent or supporting doc below

## Preferred agent

- `.github/agents/senior-react-defi-product.agent.md`
  Use for product UI, public website, operator UX, live views, tables, charts, and responsive work.

## Instructions

- `.github/copilot-instructions.md`

## Supporting docs

- `../README.md`
- `../docs/architecture/README.md`
- `../docs/architecture/FINTECH_UI_STANDARDS.md`
- `../docs/guides/TROUBLESHOOTING.md`

## Current implementation hotspots (2026-05)

- `src/pages/Backtests.tsx` — backtest intelligence dashboard/new/runs UX and active-run quick access.
- `src/components/StrategyManager.tsx` — runtime operations UX with heartbeat/status telemetry.
- `src/components/BacktestList.tsx` — run archive with active polling and status normalization behavior.
