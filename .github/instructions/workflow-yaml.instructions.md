---
description: 'Use when editing GitHub Actions workflow YAML files for CI/CD or release automation. Enforce explicit triggers, deterministic job ordering, safe secret handling, and production deployment checks.'
applyTo: '.github/workflows/**'
---

# Workflow YAML Instructions

Apply these rules when editing files under `.github/workflows/**`.

## Primary goals

- Keep workflow behavior explicit and deterministic.
- Preserve safe CI-before-CD ordering.
- Avoid accidental trigger expansion.
- Keep secrets and protected environment behavior safe.

## Required practices

1. **Use explicit triggers**
   - Scope `push`, `pull_request`, `workflow_dispatch`, `schedule`, and tag patterns tightly.
   - Do not broaden branches or tags unless the task explicitly requires it.

2. **Use explicit job dependencies**
   - Define `needs` for deployment/release jobs.
   - Ensure required build/test/lint/package checks complete before deploy paths.

3. **Keep steps operator-readable**
   - Use clear step names.
   - Prefer direct shell commands over opaque indirection when safety matters.
   - Use `set -euo pipefail` for multi-line shell scripts where appropriate.

4. **Handle secrets safely**
   - Reference secret names only.
   - Never echo secret values.
   - Avoid writing secrets into logs, summaries, or artifacts.

5. **Respect environment protections**
   - If production deployment is involved, prefer protected environments, required checks, and manual approval where available.
   - Keep rollback or failure-handling notes obvious in workflow structure or adjacent docs.

## Avoid

- Hidden coupling between unrelated jobs
- Broad `if:` conditions that are hard to reason about
- Silent fallback behavior for missing artifacts or missing secrets
- Release jobs that publish before verification steps finish

## Verification expectations

- Confirm referenced jobs, outputs, and artifacts exist.
- Confirm trigger conditions match intended rollout scope.
- Confirm deployment-affecting changes have an explicit rollback story.
- Update adjacent docs/prompts if deployment behavior meaningfully changes.
