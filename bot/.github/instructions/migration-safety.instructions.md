---
description: "Use when writing or reviewing Alembic/database migrations, schema changes, data backfills, or downgrade plans. Enforces phased non-null rollout, lock-risk callouts, and downgrade validation expectations."
name: "Migration Safety Standard"
applyTo: "migrations/**/*.py"
---

# Migration Safety Standard

Use this guidance for migration design/review work in this repository.

## Required output sections

Always include:

1. **Change summary**
2. **Forward safety checks**
3. **Lock/performance risk**
4. **Downgrade plan**
5. **Verification checklist**
6. **Rollout and rollback notes**

## Phased non-null and default rules

- Do **not** add a non-nullable column to populated tables in a single step unless proven safe.
- Prefer phased rollout:
    1. add nullable column,
    2. backfill in batches,
    3. enforce non-null constraint in a follow-up migration.
- Avoid long-lived server defaults unless they are intentional and documented.

## Destructive change rules

- Avoid destructive operations (drop column/table, type narrowing) in the same release as application code removal.
- Prefer expand/contract migration strategy.
- If destructive change is unavoidable, require explicit data retention and backup notes.

## Lock and performance expectations

- Call out operations likely to lock large tables (index builds, column rewrites, type conversions).
- Prefer lock-minimizing patterns where possible (phased changes, online-safe approaches).
- For heavy backfills, document batching strategy and idempotency behavior.

## Downgrade expectations

- Provide a realistic downgrade path for schema and data implications.
- If downgrade cannot be lossless, explicitly state what is irreversible.
- Include downgrade validation expectations (at minimum: migration down executes cleanly in test/staging).

## Verification checklist (minimum)

- Upgrade applies successfully from current head.
- Downgrade applies successfully to previous revision (or documented limitation).
- Application boot and critical DB paths still work after upgrade.
- Any data backfill query is validated for correctness and runtime safety.

## Rollout and rollback notes

- State rollout risk as **Low**, **Medium**, or **High**.
- Include operational notes: ordering, maintenance window needs, monitoring signals.
- Provide concrete rollback steps (target revision, app deploy coordination, and data caveats).
