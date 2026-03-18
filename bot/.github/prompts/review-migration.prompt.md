---
description: "Review or implement Alembic migrations with strict safety checks, lock-risk analysis, and rollback readiness"
name: "Review Migration"
argument-hint: "Migration scope: revision file(s), schema change, or backfill goal"
agent: "agent"
---

Review (or implement) a database migration in this repository with production-safe rigor.

Migration scope: ${input:Migration scope (revision file, table/column/index change, or backfill goal)}

## Required standards

- Follow migration safety guidance for phased non-null rollout.
- Explicitly call out lock/performance risk.
- Provide realistic downgrade and rollback notes.
- Keep changes backward compatible when possible.

## Workflow

1. Inspect migration files and affected models/repositories.
2. Identify unsafe patterns (single-step non-null, destructive changes, high-lock operations).
3. Propose or apply safer expand/contract alternatives.
4. Define downgrade feasibility and data-loss caveats.
5. Produce a deployment-safe verification checklist.

## Output format

1. **Change summary**
2. **Forward safety checks**
3. **Lock/performance risk**
4. **Downgrade plan**
5. **Verification checklist**
6. **Rollout and rollback notes**

## Validation expectations

- Confirm upgrade path from current head.
- Confirm downgrade path (or explicitly document limitations).
- Note any required operational sequencing or maintenance windows.
