---
name: "MariaDB Migration Review"
description: "Review MariaDB migrations, schema changes, repository query updates, indexes, constraints, and rollout safety in this dYdX backend. Use when auditing migrations, database refactors, persistence changes, or production rollout risks."
argument-hint: "Describe the migration, schema change, repository diff, or rollout concern to review"
agent: "Senior Go DeFi Backend"
---

Perform a focused MariaDB migration review for this repository.

Use the repository guidance in [Go API, Database, and Crypto Trading Backend](../skills/go-api-db-crypto-trading/SKILL.md) and [Go Backend API Conventions](../instructions/go-backend-api.instructions.md).

Review the requested migrations, SQL, models, repository changes, and related API or service updates with emphasis on correctness, compatibility, and rollout safety.

## Review for these risks

- destructive or hard-to-rollback schema changes
- missing indexes for new query paths or unnecessary indexes that add write cost
- incorrect uniqueness, foreign-key, nullability, or default-value decisions
- migration ordering problems or assumptions that break on existing production data
- lock-heavy operations, table rewrites, or long-running changes that are risky during rollout
- mismatches between migrations, Go models, repository SQL, and handler or service expectations
- unsafe backfills, data transforms, or enum-like state migrations
- query regressions, N+1 style repository changes, or transaction-boundary mistakes
- silent behavior changes caused by renamed columns, changed semantics, or altered constraints
- poor error wrapping or missing visibility into persistence failures

## Output format

Provide:

1. **Overall migration risk** — low, medium, or high
2. **Schema and rollout findings** — ordered by severity
3. **Why each finding matters** — operational, data-integrity, or performance impact
4. **Recommended minimal fix** — smallest safe rollout path first
5. **Deployment notes** — migration order, backfill strategy, compatibility window, or rollback concerns

## Review rules

- Prioritize rollout safety, data integrity, and compatibility over style comments.
- Be explicit about affected migration files, repository methods, tables, indexes, constraints, and queries.
- If a change looks safe, say so briefly instead of manufacturing issues.
- Distinguish confirmed defects from cautionary rollout concerns.
- Call out whether the change is additive, contract-preserving, and safe against live data.
- If the API contract depends on the schema change, mention the cross-layer impact.
- Prefer the smallest compatible migration strategy before suggesting bigger refactors.
