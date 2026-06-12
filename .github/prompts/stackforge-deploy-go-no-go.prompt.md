---
agent: Senior StackForge CLI Deployer
name: stackforge-deploy-go-no-go
description: 'Run a strict StackForge deployment go/no-go gate for app + API + DB rollout, returning APPROVE or HOLD with concrete blockers, verification evidence, and rollback-safe next steps.'
argument-hint: 'What StackForge deployment change or plan should be evaluated (config, manifest, env file, target cluster/node, and environment)?'
---

Related skill: `config-infrastructure-management`

Perform a concise but strict StackForge deployment readiness gate.

## Objective

Return one final decision:

- `APPROVE`
- `HOLD`

The decision must be evidence-based and biased toward production safety.

## Inputs

Collect or infer:

- Target environment (`dev`, `staging`, `production`)
- Cluster config path (for example `stackforge.yaml`)
- Deployment manifest path (for example `stackforge-deployment.yaml`)
- Deploy env file path (for example `.env.stackforge`)
- Node targeting mode (auto or explicit `--node`)
- Rollback/restore posture

If critical inputs are missing, state assumptions explicitly.

## Blocking Checks

### 1) Preflight and Safety Sequence

Verify that deployment planning preserves this default sequence where relevant:

1. `stackforge validate --config <config>`
2. `stackforge validate --config <config> --live --production` (for live prod readiness)
3. `stackforge firewall plan --config <config>`
4. `stackforge install --dry-run --config <config>` (if infra changes are in scope)

Block if production rollout skips preflight evidence without explicit, approved rationale.

### 2) Production Guardrails

For production live actions, verify:

- `--confirm-production` is required for live production operations.
- `--yes` is used only after plan/dry-run review.
- Break-glass flags are not normalized without explicit risk acceptance:
  - `--allow-example-config`
  - `--allow-public-ssh`
  - `--allow-no-firewall`

### 3) Manifest and Environment Integrity

- `stackforge-deployment.yaml` contains a valid non-empty `services` map.
- `.env.stackforge.example` should be the template source; `.env.stackforge` keys must align with manifest/runtime expectations.
- Placeholder/demo values are not treated as production-ready.
- Secret values are never printed in logs or summaries.

### 4) App + API + DB Deployment Readiness

- Target node selection is explicit and operationally safe.
- DB posture is safe (health checks and no public DB exposure assumptions).
- Post-deploy checks are defined (`status`, `components status`, `inventory refresh`, app/API health probes).
- Known StackForge command limitations are acknowledged when relevant.

### 5) Recovery and Rollback

- Backup plan exists before risky changes (`stackforge backup run ...`).
- Rollback path is explicit (`stackforge rollback list`, safe rollback applicability).
- Destructive restore behavior is acknowledged (`backup restore` requires explicit intent).

## Decision Heuristic

- Any unresolved issue in sections 1–5 => `HOLD`
- Missing evidence in 2 or more blocking areas => `HOLD`
- Otherwise => `APPROVE` with residual risks and safeguards

## Output Format

1. **Decision**: `APPROVE` or `HOLD`
2. **Confidence**: `High` / `Medium` / `Low`
3. **Blocking Findings**
4. **Top Residual Risks**
5. **Required Actions Before Deploy**
6. **Rollback/Restore Plan Check**
7. **Evidence Summary**

## Guardrails

- If production assumptions conflict with documented StackForge CLI behavior, default to `HOLD`.
- If example/demo values or unsafe CIDRs are present for production, default to `HOLD`.
- If rollback path is unclear or untested for risky operations, default to `HOLD`.
