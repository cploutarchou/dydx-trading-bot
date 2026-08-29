# Bot Customization Index

Use this file when the task is primarily inside the Python bot service.

## Read in this order

1. `../AGENTS.md`
2. `.github/copilot-instructions.md`
3. This file
4. The most relevant agent, instruction, or prompt below

## Preferred agent

- `.github/agents/senior-python-defi-runtime.agent.md`
  Use for runtime lifecycle, FastAPI, backtests, websocket, exchange, and execution-safety work.
- `.github/agents/senior-bot-project-manager.agent.md`
  Use for scoped bot project planning and multi-step improvement coordination.
- `../.github/agents/senior-prod-backtest-defi-auditor.agent.md`
  Use when bot work is part of a production-readiness audit, long-running backtest hang investigation, or DeFi
  trading-risk review.

## Instructions

- `.github/copilot-instructions.md`
- `.github/instructions/runtime-safety.instructions.md`
- `.github/instructions/migration-safety.instructions.md`
- `.github/instructions/improvement-output.instructions.md`
- `.github/instructions/api-route-safety.instructions.md`
- `.github/instructions/trading-strategy.instructions.md`
- `.github/instructions/trading-strategy-implementation.instructions.md`

## Shared repo skills

- `../.github/skills/defi-python-algo-trading/SKILL.md`
- `../.github/skills/dydx-pairs-arbitrage/SKILL.md`

## Bot-local skills (`.agents/skills/`)

- `.agents/skills/multi-worker-broadcast-test/SKILL.md` — cross-worker broadcast regression workflow (`make test-multiworker`).
- `.agents/skills/bot-improvements-workflow/SKILL.md` — scoped IMPROVEMENTS.md workflow with required checks.
- `.agents/skills/coverage-ratchet/SKILL.md` — coverage floor ratchet (82% in CI).
- `.agents/skills/portfolio-risk-burn-in/SKILL.md` — portfolio risk guard burn-in harness (`make portfolio-burn-in`).

## Prompts

- `.github/prompts/improve-project.prompt.md`
- `.github/prompts/review-migration.prompt.md`
- `.github/prompts/performance-profiling.prompt.md`
- `.github/prompts/incident-response.prompt.md`
- `.github/prompts/document-bot-flows.prompt.md`

## Hooks

- `.github/hooks/preflight-validation.json` — preflight syntax/import checks for
  `src/trading` and API files. NOTE: this is a bespoke location; no agent runtime
  auto-loads it. Run its checks manually or wire it into your tooling before
  relying on it.

## Current implementation hotspots (2026-05)

- `src/api/server.py` — canonical API assembly, auth envelope behavior, readiness contract.
- `src/bot_instance_manager.py` — lifecycle ownership, per-instance safety, subprocess logging.
- `src/main_instance.py` — runtime worker orchestration and trading execution entrypoint.
