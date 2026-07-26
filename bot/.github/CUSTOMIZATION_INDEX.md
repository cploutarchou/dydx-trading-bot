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
- `../.github/agents/senior-prod-backtest-defi-auditor.agent.md`
  Use when bot work is part of a production-readiness audit, long-running backtest hang investigation, or DeFi
  trading-risk review.

## Instructions

- `.github/copilot-instructions.md`
- `.github/instructions/runtime-safety.instructions.md`
- `.github/instructions/migration-safety.instructions.md`
- `.github/instructions/improvement-output.instructions.md`

## Shared repo skill

- `../.github/skills/defi-python-algo-trading/SKILL.md`

## Prompts

- `.github/prompts/improve-project.prompt.md`
- `.github/prompts/review-migration.prompt.md`

## Current implementation hotspots (2026-05)

- `src/api/server.py` — canonical API assembly, auth envelope behavior, readiness contract.
- `src/bot_instance_manager.py` — lifecycle ownership, per-instance safety, subprocess logging.
- `src/main_instance.py` — runtime worker orchestration and trading execution entrypoint.
