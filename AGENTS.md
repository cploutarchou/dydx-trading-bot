# AGENTS.md

Repository-level startup guidance for coding agents working in this monorepo.

## Start every new task with this checklist

1. Read `.github/copilot-instructions.md`
2. Read `.github/CUSTOMIZATION_INDEX.md`
3. Load and apply the most relevant skill/agent/prompt from the index before implementation

## Primary customization files

- Workspace defaults: `.github/copilot-instructions.md`
- Customization index: `.github/CUSTOMIZATION_INDEX.md`
- Main trading agent: `.github/agents/senior-defi-dev.agent.md`
- Python trading skill: `.github/skills/defi-python-algo-trading/SKILL.md`
- Risk/deploy prompts: `.github/prompts/*.prompt.md`

## Operating notes

- Treat this file as a startup pointer; keep details in `.github/*` customization files.
- If there is any conflict, prefer the more specific instruction file for the affected scope.
