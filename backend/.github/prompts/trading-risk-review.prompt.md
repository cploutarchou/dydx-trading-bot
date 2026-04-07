---
name: "Trading Risk Review"
description: "Review Go backend changes in this dYdX backend for trading risk, execution safety, precision issues, retries, idempotency, exchange integration hazards, and database consistency problems. Use when auditing bot, backtest, order, position, or delegated bot API behavior."
argument-hint: "Describe the feature, file, diff, endpoint, or trading workflow to review"
agent: "agent"
---

Perform a focused trading risk review for this repository.

Use the repository guidance in [Go API, Database, and Crypto Trading Backend](../skills/go-api-db-crypto-trading/SKILL.md).

Review the requested code, files, or changes with emphasis on execution safety rather than style.

## Review for these risks

- numerical precision or rounding issues for price, size, pnl, fees, or leverage
- non-idempotent retries that can duplicate orders, fills, writes, or side effects
- inconsistent state transitions for orders, positions, strategies, or bot instances
- divergence between backtest behavior and live or delegated execution behavior
- stale data, race conditions, lock gaps, or transaction-boundary problems
- incorrect auth propagation, token forwarding, or service-token usage in delegated bot API flows
- network or environment mixups such as mainnet vs testnet behavior
- missing validation, circuit breakers, or defensive checks around risky actions
- database integrity problems including uniqueness, foreign keys, nullability, or rollout hazards
- weak error handling that hides whether a failure is transport, validation, business-rule, or persistence related

## Output format

Provide:

1. **Overall risk summary** — low, medium, or high
2. **Findings** — bullet list ordered by severity
3. **Why it matters** — tie each issue to trading, money, or operational impact
4. **Recommended minimal fix** — smallest safe change first
5. **Residual risks** — note anything uncertain, untested, or environment-dependent

## Review rules

- Prioritize correctness, safety, and operational resilience over style comments.
- Be specific about affected files, routes, services, repositories, SQL, and state transitions.
- If something looks safe, say so briefly instead of inventing issues.
- Distinguish confirmed defects from plausible concerns.
- Call out hidden edge cases such as duplicate webhook delivery, partial fills, replayed jobs, and stale snapshots.
- Include migration or rollout concerns if schema or query behavior is involved.
- If the change touches delegated bot API behavior, explicitly review timeout, auth, and compatibility-route impacts.
