---
name: "Go Backend API Conventions"
description: "Use when creating or modifying Go backend routes, handlers, services, repositories, middleware, config, database logic, migrations, or delegated bot API behavior in this dYdX backend. Covers layered architecture, auth context, PostgreSQL, response handling, and trading-safety conventions."
applyTo: ["cmd/**/*.go", "config/**/*.go", "internal/**/*.go"]
---

# Go Backend API Conventions

Follow these conventions when editing backend Go code in this repository.

## Architecture and flow

- Preserve the layered flow: route -> handler -> service -> repository -> database.
- Keep dependency injection explicit in route wiring instead of hiding it behind global state.
- Prefer small, focused changes that match the existing feature structure.
- Do not collapse handler, service, and repository responsibilities together unless the feature already does so and there is a strong reason.

## Routes, handlers, and auth

- Keep API routes under `/api/v1/...` unless extending an existing compatibility route.
- Protected routes should use `RequireAuth()` consistently.
- Handlers should read the existing Gin auth context keys exactly as provided: `user_id`, `username`, `email`, `is_admin`.
- Match the response envelope and status-code style already used in the same feature area.
- Validate request input explicitly and fail with clear JSON errors.

## Services and business rules

- Put business logic in services, not in handlers.
- Keep validation, transformations, encryption, and domain invariants explicit.
- Be conservative with money-sensitive and automation-sensitive behavior.
- When logic differs between backtest, delegated execution, and live-like behavior, make that boundary explicit.

## Repositories and database behavior

- PostgreSQL is the primary runtime target; prefer patterns that are safe for PostgreSQL behavior.
- Keep SQL and data access explicit and understandable.
- Wrap database errors with context using `%w`.
- Think about indexes, uniqueness, nullability, foreign keys, and transaction boundaries before changing persistence logic.
- Favor additive, rollout-safe schema changes when compatibility matters.

## Delegated bot API behavior

- Preserve caller compatibility for delegated routes.
- Review timeout handling, auth forwarding, and service-token behavior when changing delegated bot API behavior.
- Distinguish upstream transport failures from business-rule failures in returned errors.

## Trading and backtest safety

- Treat precision, idempotency, retries, timestamps, and state transitions as first-class concerns.
- Guard against duplicate execution, stale data, replayed events, and partial-fill edge cases.
- Call out risk-sensitive behavior clearly when changing order, position, strategy, or bot-instance flows.

## Tests and verification

- Add or update tests close to the changed behavior when practical.
- Cover success cases, validation failures, auth failures, persistence failures, and delegated integration failures when relevant.
- Re-check public contract changes, migration impact, and hidden compatibility risks before considering the work complete.
