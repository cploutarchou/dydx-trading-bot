---
name: deployment-github-actions
description: 'Design, implement, debug, and validate deployment and GitHub Actions workflow changes for this monorepo. Use for CI/CD pipelines, workflow hardening, release automation, Docker/deploy sequencing, secrets/config checks, and go/no-go verification.'
argument-hint: 'What deployment or GitHub Actions outcome should this skill produce?'
user-invocable: true
---

# Deployment + GitHub Actions Workflow

Use this skill when changing or validating deployment automation, CI/CD workflows, release gates, or runtime rollout behavior for this repository.

## Outcome

Produce a safe, reproducible deployment/workflow change that:

1. Preserves service boundaries (`frontend -> backend -> bot`)
2. Uses canonical build/test commands from repo guidance
3. Enforces correct job dependencies and failure gates
4. Verifies secret/config assumptions without leaking sensitive values
5. Includes clear verification evidence and rollback notes

## Decision Logic

1. **What kind of change is this?**
   - CI-only (test/lint/build checks) -> optimize validation jobs and required checks.
   - CD/release -> add/adjust deployment stages, protection gates, and rollout strategy.
   - Infra/runtime orchestration -> verify service startup ordering, health checks, and port assumptions.

2. **Does this change touch deployment risk?**
   - Yes -> require explicit rollback path and go/no-go criteria.
   - No -> continue with standard CI validation.

3. **Does this change require secrets/config?**
   - Yes -> confirm secret names/availability and safe fallback behavior; never print secret values.
   - No -> continue.

4. **Does this change alter contract-critical services?**
   - Frontend/backend boundary changed -> validate API expectations from frontend perspective.
   - Backend/bot boundary changed -> validate delegated route behavior and bot API assumptions.

5. **Is deploy behavior branch-sensitive?**
   - Yes -> enforce branch/tag filters and environment protections.
   - No -> keep triggers minimal and explicit.

## Multi-Phase Procedure

1. **Scope and risk framing**
   - Define target environment(s): dev, staging, production.
   - Define success criteria and blast radius.
   - Identify whether this is CI reliability, deployment correctness, or both.

2. **Baseline workflow mapping**
   - Locate affected files (`.github/workflows/*.yml`, `Makefile`, `docker/*`, service build scripts).
   - Trace trigger -> jobs -> artifacts -> deploy step sequence.
   - Identify current required checks and deployment blockers.

3. **Plan minimal changes**
   - Prefer small, isolated workflow edits.
   - Keep matrix/build fan-out manageable; avoid unnecessary parallelization.
   - Explicitly define `needs` relationships for deterministic ordering.

4. **Implement incrementally**
   - Add or adjust jobs/steps with clear names and fail-fast conditions.
   - Keep caching deterministic (keyed by lockfiles + relevant config).
   - Avoid hidden shell behavior; keep scripts explicit and portable.

5. **Validate locally and logically**
   - Run service-level checks for touched areas (frontend/backend/bot).
   - Validate command parity with canonical repo commands.
   - Confirm no workflow syntax regressions and no dangling job references.

6. **Deployment safety hardening**
   - Verify health-check/wait strategy after deploy operations.
   - Validate rollback path (previous artifact/image tag or operational rollback plan).
   - Confirm environment protection expectations (manual approvals, branch restrictions, required checks).

7. **Finalize with evidence**
   - Summarize changed workflow/deploy files and reasons.
   - Record what was validated and what remains as follow-up.
   - Include explicit operator notes for failure handling.

## Deployment Rollout Path

Use this path when the deployment touches production infrastructure, release automation, or assets that must remain aligned with operational safety.

### Default rollout sequence

1. **Prepare and inspect config**
   - Confirm production values are real, not example/demo placeholders.
   - Confirm environment, domains, node addresses, and network constraints are production-safe.

2. **Run validation before any live action**
   - Run static and runtime validation for deployment manifests and required variables.
   - Treat validation failures as hard blockers.

3. **Review network exposure**
   - Confirm only intended ports are public by default.
   - Treat public database/internal API exposure as a blocker unless explicitly designed and reviewed.

4. **Dry-run install or rollout**
   - Execute dry-run paths before any live production action.
   - Review plan output and expected state changes.

5. **Run live production action only after review**
   - Require explicit production confirmation for live actions.
   - In non-interactive automation, use auto-confirmation only after prior human review.

6. **Verify and capture evidence**
   - Collect component status and app health evidence.
   - Review rollback records and backup posture.

### Release automation checks

- Verify versioning, checksum generation, and release asset naming remain deterministic.
- If workflow changes affect release publishing, confirm the release step cannot run before verification/build steps succeed.

### Operator checkpoints

- Know where to inspect deployment failures for the active platform/tooling.
- Require an explicit rollback or recovery note before approving production rollout changes.
- For destructive or recovery actions, prefer dry-run first.

## Quality Gates (Must Pass)

- [ ] Workflow triggers match intended branches/events (no accidental broad triggers)
- [ ] Job dependency graph (`needs`) is correct and deterministic
- [ ] Required test/lint/build checks run before deployment paths
- [ ] Secrets are referenced safely (names only; no value exposure)
- [ ] Build/deploy commands align with repo canonical commands
- [ ] A rollback path is defined for deployment-impacting changes
- [ ] Service-boundary assumptions are preserved (`frontend -> backend -> bot`)
- [ ] Verification notes capture what was tested and any residual risk

## Completion Criteria

Task is complete only when:

- Intended automation behavior is achieved and reproducible
- Validation evidence is documented
- Risk and rollback handling are explicit
- Checklist items are complete, skipped (with reason), or blocked

## Suggested Invocation Prompts

- `/deployment-github-actions Harden CI by splitting lint/test/build while preserving required checks.`
- `/deployment-github-actions Add a gated deploy workflow for main branch with manual production approval.`
- `/deployment-github-actions Refactor workflow dependencies to remove flaky race conditions in artifacts.`
- `/deployment-github-actions Add safe rollback notes and post-deploy health verification for stack deploy.`
- `/deployment-github-actions Validate deployment env-variable parity and strict production release gates.`
