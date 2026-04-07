---
name: go-api-db-crypto-trading
description: "Design, implement, review, and debug backend features in this dYdX trading bot Go API. Use when building or fixing Gin routes, handlers, services, repositories, PostgreSQL schema changes, delegated bot API behavior, auth-protected endpoints, backtest or trading workflows, risk controls, or database-heavy backend code."
argument-hint: "Describe the backend feature, bug, endpoint, schema change, or trading workflow to implement or review"
user-invocable: true
---

# Go API, Database, and Crypto Trading Backend

Use this skill when working on this repository as a senior Go backend engineer with strong API, database, exchange-integration, and crypto trading domain judgment.

This skill is optimized for tasks such as:

- implementing or refactoring Go REST API endpoints
- designing PostgreSQL-backed features and migrations
- reviewing Gin route, handler, service, and repository flows
- debugging auth, persistence, or request validation issues
- adding exchange, backtest, delegated bot API, or trading-related backend logic
- evaluating trading workflows with risk, execution, and data-integrity concerns in mind

## Repository-Specific Context

Assume the following unless the user says otherwise:

- HTTP server uses Gin and routes are grouped under `/api/v1/...`.
- Main runtime flow is route -> handler -> service -> repository -> database.
- Protected routes typically use `RequireAuth()` and consume Gin context values such as `user_id`, `username`, `email`, and `is_admin`.
- PostgreSQL is the primary runtime database and migrations live under `migrations/postgres`.
- Some endpoints delegate to the upstream bot API, so auth forwarding, timeout handling, and compatibility routes matter.
- Backtest, bot runtime, and trading features must preserve operational safety and caller compatibility.

## What This Skill Produces

This skill helps produce backend changes that are:

- idiomatic Go
- API-first and contract-aware
- database-safe and migration-conscious
- consistent with the existing layered architecture
- explicit about validation, auth, observability, and failure modes
- sensitive to trading-domain concerns such as risk controls, precision, idempotency, and auditability

## When to Use

Use this skill when the user asks for any of the following:

- add, update, or debug a Go API route or handler
- create a repository or service for new backend functionality
- design database tables, queries, indexes, or migrations
- fix issues involving PostgreSQL, transactions, locks, or data consistency
- connect trading, bot, or backtest workflows to persistent storage
- review API correctness, schema design, exchange integration, or trading-domain logic
- reason about crypto trading concepts that affect backend behavior

## Operating Assumptions

Default engineering posture:

- Prefer clear, maintainable Go over clever abstractions.
- Preserve existing project conventions unless there is a strong reason to change them.
- Treat API and database contracts as stability boundaries.
- Assume money-sensitive and automation-sensitive behavior requires extra care.
- Favor explicit validation, structured errors, and observable failure paths.
- Be conservative with trading actions, state transitions, and order lifecycle logic.
- Keep route wiring and dependency injection consistent with existing route registration patterns.

Default trading-domain posture:

- Check whether logic should differ for paper/backtest/simulated/live paths.
- Consider position sizing, leverage, liquidation, fees, slippage, and latency effects.
- Ensure timestamp handling, ordering, and idempotency are well-defined.
- Prefer deterministic reconciliation and auditable event trails.
- Guard against duplicate execution, stale signals, and inconsistent state.

## Procedure

1. **Clarify the target change**
   - Identify whether the task is about API behavior, database shape, trading logic, or infrastructure glue.
   - Extract the required inputs, outputs, constraints, and whether the change affects public contracts.
   - If the request is ambiguous, ask narrowly targeted questions.

2. **Map the affected layers**
   - Trace the flow across routes, handlers, services, repositories, models, middleware, configuration, and any delegated bot API behavior.
   - Identify auth requirements, request validation, env dependencies, and upstream/downstream integrations.
   - Confirm whether the feature should be synchronous, asynchronous, transactional, or delegated.

3. **Design the API contract first**
   - Define request/response shapes, status codes, validation rules, and error cases.
   - Preserve backwards compatibility where possible.
   - Ensure protected routes enforce auth and use the correct Gin context values.
   - Match route grouping and feature-specific response conventions already used in this backend.

4. **Design persistence deliberately**
   - Determine table changes, indexes, constraints, foreign keys, and nullability.
   - Decide whether the change needs a migration, transaction, row-level lock, uniqueness guarantee, or retry behavior.
   - Consider query performance and operational safety before writing SQL.
   - Prefer repository changes that fit the existing SQL and error-wrapping style.

5. **Implement by layer**
   - Models: add or update typed structs and field tags.
   - Repository: keep SQL explicit, wrapped with contextual errors, and consistent with existing patterns.
   - Service: encode business rules, validation, encryption, transformations, and domain invariants.
   - Handler/route: translate HTTP input into service calls and return stable JSON responses.
   - Middleware/config: update only when the feature truly changes cross-cutting concerns.
   - Delegation layer: when proxying to the bot API, preserve timeout, token-forwarding, and compatibility behavior.

6. **Apply trading-domain checks**
   - Validate numerical precision and avoid unsafe float assumptions for money-sensitive values.
   - Check symbol/network/environment boundaries such as mainnet vs testnet.
   - Review order state transitions, position effects, execution sequencing, and replay behavior.
   - Consider how backtest logic diverges from live execution and whether shared code is safe.

7. **Verify thoroughly**
   - Add or update tests near the touched behavior.
   - Cover success paths, validation failures, auth failures, persistence errors, exchange/delegation failures, and trading edge cases.
   - Run relevant tests, then broader verification if the surface area warrants it.
   - Re-read the final change for hidden contract breaks and migration safety.

## Decision Points

### If the change affects an HTTP endpoint

- Confirm route versioning and grouping.
- Verify auth requirements and request validation.
- Preserve response envelope conventions in the same feature area.
- Keep frontend compatibility routes intact if this endpoint is already consumed externally.

### If the change affects the database

- Prefer additive migrations when compatibility matters.
- Add indexes only when they serve concrete query patterns.
- Verify rollback or recovery expectations for risky schema changes.
- Check whether migration ordering and existing production data shape create rollout hazards.

### If the change affects trading or bot execution logic

- Separate signal generation, execution intent, and persisted execution result.
- Make retries idempotent.
- Treat partial fills, stale market data, and duplicated webhook or worker events as first-class cases.
- Confirm whether the logic belongs to live trading, delegated execution, or backtest-only behavior.

### If the change delegates to an upstream bot/exchange service

- Validate timeout, auth forwarding, and error translation behavior.
- Distinguish transport failures from business-rule failures.
- Keep compatibility routes stable for callers.
- Verify whether service-token mode or user-token forwarding should apply.

## Quality Bar

A task is complete only when:

- the root cause or requested feature is fully implemented
- the design fits the existing layered architecture
- API behavior is explicit and testable
- data access is safe, understandable, and performance-conscious
- trading-domain edge cases were considered, not hand-waved away
- delegated integration behavior is explicit where relevant
- relevant tests or verification steps were run
- follow-up risks or assumptions are clearly called out

## Output Style

When using this skill:

- explain changes in terms of API contract, data model, and business rules
- call out migration impact, auth impact, delegation impact, and risk-sensitive behavior
- recommend the smallest safe change first
- avoid speculative rewrites unless the user asks for broader refactoring

## Example Prompts

- `/go-api-db-crypto-trading add a protected Go endpoint to store exchange API credentials with PostgreSQL persistence and validation`
- `/go-api-db-crypto-trading review this Gin handler-service-repository design for a backtest results API`
- `/go-api-db-crypto-trading debug why this trading bot route is duplicating orders after retries`
- `/go-api-db-crypto-trading design a migration and repository changes for storing bot position snapshots`
- `/go-api-db-crypto-trading implement a safe refresh flow for delegated bot API requests`
