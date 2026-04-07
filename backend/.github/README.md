# Copilot Customizations for the Backend

This folder contains project-specific Copilot customizations for the dYdX backend.

These customizations are split into three types:

- **Skills** — reusable multi-step workflows you can invoke from chat
- **Prompts** — focused, on-demand review or generation tasks you can invoke from chat
- **Instructions** — guidance that loads automatically when relevant files are being edited

## What is configured

### Skills

- [`skills/go-api-db-crypto-trading/SKILL.md`](./skills/go-api-db-crypto-trading/SKILL.md)
  - Main senior-backend workflow for Go API, PostgreSQL, delegated bot API behavior, and crypto trading tasks
  - Use for implementation, debugging, design review, migrations, and trading-aware backend changes
  - Invoke with `/go-api-db-crypto-trading`

### Prompts

- [`prompts/trading-risk-review.prompt.md`](./prompts/trading-risk-review.prompt.md)
  - Focused review for execution safety, retries, idempotency, precision, and trading-domain risk
  - Invoke with `/trading-risk-review`

- [`prompts/postgres-migration-review.prompt.md`](./prompts/postgres-migration-review.prompt.md)
  - Focused review for migrations, schema changes, indexes, constraints, and rollout safety
  - Invoke with `/postgres-migration-review`

- [`prompts/delegated-bot-api-review.prompt.md`](./prompts/delegated-bot-api-review.prompt.md)
  - Focused review for delegated bot API behavior, upstream proxying, auth forwarding, service-token mode, WebSocket relays, and compatibility routes
  - Invoke with `/delegated-bot-api-review`

### Instructions

- [`instructions/go-backend-api.instructions.md`](./instructions/go-backend-api.instructions.md)
  - Auto-applies to backend Go code under `cmd/**/*.go`, `config/**/*.go`, and `internal/**/*.go`
  - Reinforces layered architecture, Gin auth context, PostgreSQL-safe changes, delegated bot API behavior, and trading safety

- [`instructions/go-tests.instructions.md`](./instructions/go-tests.instructions.md)
  - Auto-applies to backend Go test files under `cmd/**/*_test.go`, `config/**/*_test.go`, and `internal/**/*_test.go`
  - Reinforces route testing, persistence testing, delegated bot API tests, and regression-focused coverage

## How to use these in chat

### Use a skill

Skills are best for broader engineering work.

Examples:

- `/go-api-db-crypto-trading add a protected endpoint for storing exchange credentials`
- `/go-api-db-crypto-trading debug duplicated orders after retry logic changes`
- `/go-api-db-crypto-trading design a migration and repository update for bot snapshots`

### Use a prompt

Prompts are best for focused reviews.

Examples:

- `/trading-risk-review review the bot instance changes for duplicate execution risk`
- `/postgres-migration-review review this migration for rollout and index safety`
- `/delegated-bot-api-review inspect bot_api_delegate_routes.go for auth forwarding and websocket compatibility`

## When things load automatically

- **Instructions** load automatically when you edit matching files.
- **Skills** and **prompts** appear as slash commands in chat.
- Skills can also be loaded automatically by the model when your request matches their description, but using the slash command is the most explicit option.

## Recommended usage pattern

- Use the **skill** when implementing or debugging a backend feature.
- Use a **prompt** when you want a sharp review lens on a specific risk area.
- Let the **instructions** provide always-on guardrails while editing code and tests.

## Tips for better results

When invoking a skill or prompt, include one or more of the following:

- file paths
- route or endpoint names
- the migration name
- the failure mode or risk you are worried about
- whether the change affects live trading, backtests, or delegated bot API behavior

The more concrete the target, the better the result.
