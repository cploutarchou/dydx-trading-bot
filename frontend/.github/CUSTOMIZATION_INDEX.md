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
- `.github/agents/api-integration-specialist.agent.md`
  Use for API integration, React Query hook architecture, endpoint contract handling, and cache/invalidation behavior.

## Instructions

- `.github/copilot-instructions.md`

## Skills

- `.github/skills/frontend-live-data-safety/SKILL.md`
- `.github/skills/senior-ux-designer/SKILL.md`
- `.github/skills/react-query-patterns/SKILL.md`
- `.github/skills/tailwind-dark-theme-fintech/SKILL.md`
- `.github/skills/portal-routing-guardrails/SKILL.md`
- `.github/skills/error-observability-patterns/SKILL.md`

## Prompts

- `.github/prompts/fintech-copy-tone.prompt.md`
- `.github/prompts/testing-and-contracts.prompt.md`
- `.github/prompts/responsive-mobile-first-qa.prompt.md`
- `.github/prompts/release-readiness.prompt.md`

## Supporting docs

- `../README.md`
- `../docs/architecture/README.md`
- `../docs/architecture/FINTECH_UI_STANDARDS.md`
- `../docs/guides/TROUBLESHOOTING.md`

## Current implementation hotspots (2026-05)

- `src/pages/Backtests.tsx` — backtest intelligence dashboard/new/runs UX and active-run quick access.
- `src/components/StrategyManager.tsx` — runtime operations UX with heartbeat/status telemetry.
- `src/components/BacktestList.tsx` — run archive with active polling and status normalization behavior.
