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
- `.github/agents/light-mode-theme-engineer.agent.md`
  Use for light-mode theming work on the fintech surface.
- `.github/agents/seo-optimization-specialist.agent.md`
  Use for SEO/meta/OG work on public pages.

## Instructions

- `.github/copilot-instructions.md`
- `.github/instructions/pages-layout-breakpoints.instructions.md`

## Skills

- `.github/skills/frontend-live-data-safety/SKILL.md`
- `.github/skills/senior-ux-designer/SKILL.md`
- `.github/skills/react-query-patterns/SKILL.md`
- `.github/skills/tailwind-dark-theme-fintech/SKILL.md`
- `.github/skills/light-mode-theme-fintech/SKILL.md`
- `.github/skills/portal-routing-guardrails/SKILL.md`
- `.github/skills/error-observability-patterns/SKILL.md`

## Prompts

- `.github/prompts/fintech-copy-tone.prompt.md`
- `.github/prompts/testing-and-contracts.prompt.md`
- `.github/prompts/responsive-mobile-first-qa.prompt.md`
- `.github/prompts/release-readiness.prompt.md`
- `.github/prompts/light-mode-polish.prompt.md`

## Supporting docs

- `README.md`
- `docs/architecture/README.md`
- `docs/architecture/FINTECH_UI_STANDARDS.md`
- `docs/guides/TROUBLESHOOTING.md`

## CI note

`frontend/.github/workflows/ci.yml` is NOT executed by GitHub Actions (only repo-root
`.github/workflows/` is loaded). The effective frontend CI gate is the
`frontend-quality` job in the root `.github/workflows/bot-quality.yml`.

## Current implementation hotspots (2026-05)

- `src/pages/Backtests.tsx` — backtest intelligence dashboard/new/runs UX and active-run quick access.
- `src/components/StrategyManager.tsx` — runtime operations UX with heartbeat/status telemetry.
- `src/components/BacktestList.tsx` — run archive with active polling and status normalization behavior.
