---
name: "Go Backend Test Conventions"
description: "Use when creating or modifying Go tests for backend routes, handlers, services, repositories, middleware, delegated bot API behavior, or MariaDB-backed behavior in this dYdX backend. Covers test scope, fixtures, auth context, HTTP assertions, persistence checks, and trading-safety edge cases."
applyTo: ["cmd/**/*_test.go", "config/**/*_test.go", "internal/**/*_test.go"]
---

# Go Backend Test Conventions

Follow these conventions when writing or updating backend Go tests in this repository.

## Test design

- Prefer targeted tests near the changed behavior instead of broad speculative suites.
- Keep each test focused on one behavior, one failure mode, or one regression risk.
- Use table-driven tests when they improve clarity, but do not force them for tiny cases.
- Choose descriptive names that explain the scenario and expected outcome.

## What to cover

- Cover the primary success path first.
- Add failure-path tests for validation, auth, persistence, upstream transport, and domain-rule errors when relevant.
- For delegated bot API paths, include timeout, auth forwarding, compatibility route, and upstream-failure scenarios.
- For database-backed logic, cover constraint assumptions, not-found behavior, transaction-sensitive behavior, and mapping between SQL rows and Go models.
- For trading or backtest logic, cover precision-sensitive values, idempotency, replay or duplicate-event scenarios, stale-state handling, and risky state transitions.

## HTTP and route tests

- Assert meaningful status codes and response bodies, not just that the request completed.
- Verify auth behavior explicitly when routes are protected.
- Preserve existing route and response-envelope conventions used by nearby tests.
- Prefer testing observable API behavior over implementation details.

## Repository and persistence tests

- Test the contract of the repository method, not just the raw SQL text.
- Assert returned models, empty results, wrapped errors, and persistence side effects when relevant.
- Be careful with time handling, nullable fields, and ordering assumptions.
- Add migration-sensitive tests only when they protect a real compatibility or schema risk.

## Delegated bot API tests

- Verify header and token forwarding rules explicitly.
- Distinguish local validation failures from upstream transport or upstream application failures.
- For WebSocket-related tests, check both directions of forwarding and connection-close behavior when practical.
- Keep caller compatibility front and center for legacy or frontend-consumed routes.

## Test style

- Follow existing helper, fixture, and setup patterns already used in nearby test files.
- Keep test setup readable; avoid hiding essential expectations inside large helpers.
- Prefer stable assertions over brittle timing-dependent checks.
- Do not add mocks or abstractions that are heavier than the behavior under test.

## Completion bar

A test update is strong when it:

- would fail before the bug fix or feature completion
- proves the intended behavior after the change
- covers the most important regression risk introduced by the edit
- stays readable enough for future debugging
