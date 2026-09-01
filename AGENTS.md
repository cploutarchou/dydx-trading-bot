# AGENTS.md

Repository-level startup guidance for coding agents working in this monorepo.

## Start every new task with this checklist

1. Read `.github/copilot-instructions.md`
2. Read `.github/CUSTOMIZATION_INDEX.md`
3. Load and apply the most relevant skill/agent/prompt from the index before implementation

## Primary customization files

- Workspace defaults: `.github/copilot-instructions.md`
- Customization index: `.github/CUSTOMIZATION_INDEX.md`
- Consolidated root agent (platform + universal + trading/quant): `.github/agents/senior-defi-monorepo-platform.agent.md`
- Python trading skill: `.github/skills/defi-python-algo-trading/SKILL.md`
- Service indexes:
  - `backend/.github/CUSTOMIZATION_INDEX.md`
  - `bot/.github/CUSTOMIZATION_INDEX.md`
  - `frontend/.github/CUSTOMIZATION_INDEX.md`
- Risk/deploy prompts: `.github/prompts/*.prompt.md`

## Operating notes

- Treat this file as a startup pointer; keep details in `.github/*` customization files.
- If there is any conflict, prefer the more specific instruction file for the affected scope.

## Latest platform context (2026-05)

- Integration boundary remains strict: `frontend -> backend -> bot`.
- Frontend now has a dedicated `Backtests` intelligence surface with dashboard/new/runs views and an **Active Runs Quick Access** panel with live status polling + freshness indicators.
- Strategy operations UX is centered in `frontend/src/components/StrategyManager.tsx` with runtime heartbeat visibility and operator/analyst density presets.
- Backend delegated backtest routes in `backend/internal/routes/bot_api_delegate_routes.go` normalize status/progress fields for compatibility and expose DB-backed backtest list responses via `backtest_runs`.
- Recent MariaDB migrations were hardened for explicit deployment execution; do not depend on startup schema changes.
