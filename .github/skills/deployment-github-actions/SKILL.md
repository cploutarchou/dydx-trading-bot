---
name: deployment-github-actions
description: "Design, implement, debug, and validate deployment and GitHub Actions workflow changes for this monorepo. Use for CI/CD pipelines, workflow hardening, release automation, Docker/deploy sequencing, secrets/config checks, and go/no-go verification."
argument-hint: "What deployment or GitHub Actions outcome should this skill produce?"
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

3. **Is this stackforge deployment-path related?**
   - Yes -> validate `stackforge-deployment.yaml` service graph, `.env.stackforge` variable coverage, and image/build parity.
   - No -> continue.

4. **Does this change require secrets/config?**
   - Yes -> confirm secret names/availability and safe fallback behavior; never print secret values.
   - No -> continue.

5. **Does this change alter contract-critical services?**
   - Frontend/backend boundary changed -> validate API expectations from frontend perspective.
   - Backend/bot boundary changed -> validate delegated route behavior and bot API assumptions.

6. **Is deploy behavior branch-sensitive?**
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
   - Validate rollback path (previous artifact/image tag or stack rollback plan).
   - Confirm environment protection expectations (manual approvals, branch restrictions, required checks).
   - For stackforge path, verify `.env.stackforge(.example)` values map cleanly to `stackforge-deployment.yaml` services.

7. **Finalize with evidence**
   - Summarize changed workflow/deploy files and reasons.
   - Record what was validated and what remains as follow-up.
   - Include explicit operator notes for failure handling.

## StackForge Rollout Path

Use this path when the deployment touches StackForge-managed infrastructure, StackForge release automation, or repo assets that must remain aligned with StackForge operational safety.

### Default rollout sequence

1. **Prepare and inspect config**
   - Confirm production values are real, not example/demo placeholders.
   - Confirm cluster name, domains, node addresses, admin CIDRs, and SSH CIDRs are production-safe.
   - Confirm `.env.stackforge`, `.env.stackforge.example`, and `stackforge-deployment.yaml` stay aligned when container/env wiring changes.

2. **Run validation before any live action**
   - `stackforge validate --config stackforge.yaml`
   - `stackforge validate --config stackforge.yaml --live --production`
   - Treat failures on example values, public admin CIDRs, public SSH CIDRs, unsupported OS, missing UFW, or production confirmation as hard blockers.

3. **Review network exposure**
   - `stackforge firewall plan --config stackforge.yaml`
   - Confirm only intended ports are public by default.
   - Treat public database/internal API exposure as a blocker unless explicitly designed and reviewed.

4. **Dry-run install or rollout**
   - `stackforge install --dry-run --config stackforge.yaml`
   - Review plan output, generated reports, and any state changes expected under `~/.stackforge/<cluster>/`.

5. **Run live production action only after review**
   - `stackforge install --config stackforge.yaml --confirm-production`
   - In non-interactive automation, require prior review and then use `--yes` deliberately.
   - Never normalize break-glass flags like `--allow-example-config`, `--allow-public-ssh`, or `--allow-no-firewall` into standard workflow behavior.

6. **Verify and capture evidence**
   - `stackforge status --config stackforge.yaml`
   - `stackforge verify --config stackforge.yaml`
   - Review inventory, install reports, rollback records, and backup posture.

### Release automation checks

- If GitHub Actions packages or releases StackForge artifacts, verify versioning, checksum generation, and release asset naming remain deterministic.
- If using StackForge release install paths, verify assumptions still match the documented installer environment variables and release behavior.
- If workflow changes affect release publishing, confirm the release step cannot run before verification/build steps succeed.

### Operator checkpoints

- Know where to inspect failures: `install-report.json`, `inventory.yaml`, `generated-secrets.yaml`, rollback records, and systemd/service health outputs.
- Require an explicit rollback or recovery note before approving production rollout changes.
- For destructive or recovery actions, prefer dry-run first and verify whether StackForge marks the action safe for automatic apply.

## Quality Gates (Must Pass)

- [ ] Workflow triggers match intended branches/events (no accidental broad triggers)
- [ ] Job dependency graph (`needs`) is correct and deterministic
- [ ] Required test/lint/build checks run before deployment paths
- [ ] Secrets are referenced safely (names only; no value exposure)
- [ ] Build/deploy commands align with repo canonical commands
- [ ] A rollback path is defined for deployment-impacting changes
- [ ] Service-boundary assumptions are preserved (`frontend -> backend -> bot`)
- [ ] Verification notes capture what was tested and any residual risk
- [ ] Stackforge deployment/env mapping is consistent (`stackforge-deployment.yaml` + `.env.stackforge*`) when touched

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
- `/deployment-github-actions Validate stackforge deployment env-variable parity and strict production release gates.`
