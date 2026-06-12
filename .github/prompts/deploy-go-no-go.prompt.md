---
agent: Senior Deploy GitHub Actions
name: deploy-go-no-go
description: 'Run a strict StackForge-aware deployment go/no-go gate for CI/CD, release, and rollout changes; return APPROVE or HOLD with blockers, rollback requirements, and operator-ready next steps.'
argument-hint: 'What deployment, workflow, release, PR, or change set should be evaluated for go/no-go?'
---

Related skill: `deployment-github-actions`

Perform a concise but strict deployment readiness gate.

## Objective

Return one final decision:

- `APPROVE`
- `HOLD`

The decision must be evidence-based and biased toward production safety.

## Inputs

Collect or infer:

- Scope (`PR`, workflow file, release plan, deployment config, env file)
- Target environment (`dev`, `staging`, `production`)
- Deployment path (`GitHub Actions`, `StackForge`, direct Docker/Compose, mixed)
- Rollback path (previous artifact/image/release or operational fallback)

If critical inputs are missing, state assumptions explicitly.

## Blocking Checks

### 1) Workflow and Release Safety

- Triggers are intentionally scoped (no accidental branch/event widening).
- Required checks run before deploy/release jobs.
- Job graph ordering is explicit and deterministic.
- Artifacts/images are produced and consumed consistently.

### 2) StackForge Production Safety

When StackForge is part of the path, verify:

- Live production actions assume `--confirm-production`.
- Non-interactive live actions assume `--yes` only after dry-run/review.
- Dry-run / validate / firewall-plan sequence is preserved where relevant.
- No break-glass flags are normalized (`--allow-example-config`, `--allow-public-ssh`, `--allow-no-firewall`) without explicit justification.

### 3) Config and Secret Hygiene

- Secret names are correct and values are never exposed.
- `.env.stackforge.example` is the shareable template; `.env.stackforge` is the live file. Keep both aligned with `stackforge.yaml` when touched.
- Placeholder/example values are not treated as production-ready.

### 4) Rollout and Recovery

- Post-deploy health verification exists.
- Rollback path is explicit and feasible.
- Failure handling is operationally clear (what to inspect, where, and who acts).

### 5) Evidence and Verification

- Relevant build/test/lint/deploy checks have run or are clearly specified.
- StackForge validation/install assumptions match documented CLI behavior.
- No unresolved critical gap remains in deployment sequencing.

## Decision Heuristic

- Any unresolved issue in sections 1-4 => `HOLD`
- Missing evidence in 2 or more blocking areas => `HOLD`
- Otherwise => `APPROVE` with residual risks and safeguards

## Output Format

1. **Decision**: `APPROVE` or `HOLD`
2. **Confidence**: `High` / `Medium` / `Low`
3. **Blocking Findings**
4. **Top Residual Risks**
5. **Required Actions Before Deploy**
6. **Rollback Plan Check**
7. **Evidence Summary**

## StackForge-Specific Guardrails

- Treat `stackforge validate --config ...`, `--live --production`, `firewall plan`, and `install --dry-run` as the default production-readiness sequence when infra rollout is involved.
- Call out example/demo values and public admin/SSH CIDRs as hard blockers for production.
- If StackForge live install/upgrade/rollback assumptions do not match documented behavior, default to `HOLD`.
