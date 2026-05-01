# Backend Customization Index

Use this file when the task is primarily inside the Go backend service.

## Read in this order

1. `../AGENTS.md`
2. `.github/copilot-instructions.md`
3. This file
4. The most relevant agent, instruction, skill, or prompt below

## Preferred agent

- `.github/agents/senior-go-defi-backend.agent.md`
  Use for most backend feature, bug, auth, contract, websocket, repository, and migration work.
- `../.github/agents/senior-prod-backtest-defi-auditor.agent.md`
  Use when backend work is part of a production-readiness audit, delegated backtest timeout/cancellation investigation, or DeFi trading-risk review.

## Instructions

- `.github/copilot-instructions.md`
- `.github/instructions/go-backend-api.instructions.md`
- `.github/instructions/go-tests.instructions.md`

## Skills

- `.github/skills/go-api-db-crypto-trading/SKILL.md`

## Prompts

- `.github/prompts/delegated-bot-api-review.prompt.md`
- `.github/prompts/postgres-migration-review.prompt.md`
- `.github/prompts/trading-risk-review.prompt.md`

## Current implementation hotspots (2026-05)

- `internal/routes/bot_api_delegate_routes.go` — delegated contract normalization + backtest route ownership.
- `internal/repository/backtest_repo.go` — DB-backed backtest list and user-scoped run retrieval.
- `migrations/postgres/000047`, `000051`, `000053` — transaction-safe index migration posture.
