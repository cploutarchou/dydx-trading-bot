---
agent: Senior StackForge CLI Deployer
name: stackforge-post-deploy-verify
description: 'Run a strict StackForge post-deploy verification for app + API + DB, returning PASS or FAIL with health evidence, drift findings, and rollback confidence.'
argument-hint: 'What deployment should be verified (environment, cluster config, manifest, env file, target node, and expected services/endpoints)?'
---

Related skill: `config-infrastructure-management`
Related prompt: `stackforge-deploy-go-no-go`

Perform a concise but strict post-deploy verification and operational confidence check.

## Objective

Return one final result:

- `PASS`
- `FAIL`

The result must be evidence-based and biased toward production safety.

## Inputs

Collect or infer:

- Target environment (`dev`, `staging`, `production`)
- Cluster config path (for example `stackforge.yaml`)
- Deployment manifest path (for example `stackforge.yaml`)
- Deploy env file path (for example `.env.stackforge`)
- Target node mode (auto-selected or explicit `--node`)
- Expected app/API domains, ports, and core services

If critical inputs are missing, state assumptions explicitly.

## Verification Checks (Blocking)

### 1) Cluster and Component Health

Verify evidence from:

- `stackforge status --config <config>`
- `stackforge components status --config <config>`
- `stackforge inventory refresh --config <config>`
- `stackforge inventory show --cluster <cluster>`

Block on failed/unreachable critical components or unresolved unhealthy state.

### 2) Application and API Smoke Checks

- API health endpoint is reachable and reports healthy.
- App endpoint is reachable and serves expected frontend/application response.
- Expected service ports and ingress behavior match deploy intent.
- No obvious app-to-api connectivity break after deploy.

### 3) Database Safety and Availability

- Database dependency is healthy for the deployed app/API path.
- No evidence of unintended public database exposure.
- App/API database connectivity assumptions are satisfied.
- Migration/config drift indicators are absent or explicitly accepted.

### 4) Manifest/Runtime Drift

- Deployed service set aligns with `stackforge.yaml` intent.
- `.env.stackforge` runtime keys match expected deploy-time config.
- Placeholder/example values are not active in production runtime.

### 5) Rollback Confidence

- Rollback candidates and strategy are identifiable (`stackforge rollback list`).
- Backup/restore posture is clear for this deployment scope.
- If a rollback would be unsafe/unclear, mark verification `FAIL` for production readiness.

## Decision Heuristic

- Any unresolved issue in checks 1-5 => `FAIL`
- Missing evidence in 2 or more blocking areas => `FAIL`
- Otherwise => `PASS` with residual risks and monitoring follow-ups

## Output Format

1. **Result**: `PASS` or `FAIL`
2. **Confidence**: `High` / `Medium` / `Low`
3. **Blocking Findings**
4. **Health Evidence Summary**
5. **Drift/Config Mismatches**
6. **Rollback Confidence Assessment**
7. **Required Immediate Actions**
8. **Monitoring Watchlist (next 30-60 min)**

## Guardrails

- For production, do not return `PASS` with unresolved critical health failures.
- Treat unclear rollback posture as a deployment risk, not a documentation nit.
- Never print secret values from env/config/state files.
