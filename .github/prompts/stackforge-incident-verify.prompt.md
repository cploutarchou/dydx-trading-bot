---
agent: Senior StackForge CLI Deployer
name: stackforge-incident-verify
description: 'Run an emergency StackForge incident verification for app + API + DB and return PASS_NOW or FAIL_NOW with critical blockers, immediate safeguards, and rollback triggers.'
argument-hint: 'What incident deployment should be emergency-verified (environment, config, manifest, env file, node, affected services/endpoints, and rollback path)?'
---

Related skill: `config-infrastructure-management`
Related prompts: `stackforge-deploy-go-no-go`, `stackforge-post-deploy-verify`

Perform an incident-mode, time-boxed post-deploy verification focused on immediate operational safety.

## Mode

- Assume urgency and prioritize highest-risk checks first.
- Prefer false negatives over false positives (if safety is uncertain, fail).
- Keep output concise and operator-ready.

## Objective

Return exactly one result:

- `PASS_NOW`
- `FAIL_NOW`

## Inputs

Collect or infer quickly:

- Incident summary and impact scope
- Target environment (`staging` or `production`)
- Cluster config path (for example `stackforge.yaml`)
- Deployment manifest path (for example `stackforge.yaml`)
- Deploy env file path (for example `.env.stackforge`)
- Target node and affected services/endpoints
- Rollback path availability

If critical inputs are missing, state assumptions and lower confidence.

## Emergency Checks (Hard Blockers)

### A) Critical Service Liveness (Mandatory)

- `stackforge status --config <config>` shows no critical service outage for affected scope.
- `stackforge components status --config <config>` confirms core runtime components reachable.
- API health endpoint and primary app entrypoint are reachable.

### B) Data and DB Safety (Mandatory)

- App/API can reach required database dependency.
- No evidence of unintended public DB exposure after incident changes.
- No unresolved migration/config mismatch that risks data integrity.

### C) Blast-Radius Control (Mandatory)

- Immediate rollback path is available and executable.
- Rollback trigger conditions are clear and measurable.
- On-call operator action path is explicit for next 30 minutes.

### D) Deployment Drift and Secrets Hygiene (Mandatory)

- Runtime behavior aligns with deployment intent from manifest/env inputs.
- No placeholder/demo values active in production paths.
- Secret values are not exposed in logs/summaries.

## Decision Rules

- Any unresolved issue in A/B/C/D => `FAIL_NOW`
- Missing evidence in 2+ mandatory checks => `FAIL_NOW`
- Otherwise => `PASS_NOW` with strict monitoring safeguards

## Output Format

1. **Result**: `PASS_NOW` or `FAIL_NOW`
2. **Confidence**: `High` / `Medium` / `Low`
3. **Critical Blockers** (max 5 bullets)
4. **Minimum Safe Actions Now**
5. **30-Minute Safeguards**
6. **Rollback Trigger Conditions**
7. **Evidence Reviewed**

## 30-Minute Safeguard Template (if PASS_NOW)

- Increase health polling frequency and alert sensitivity.
- Watch API/app error rates and dependency timeouts every 5 minutes.
- Track DB connectivity and critical endpoint success rate.
- Pre-stage rollback command ownership and execute-on-threshold conditions.

## Guardrails

- Do not return `PASS_NOW` if rollback path is unclear.
- Do not return `PASS_NOW` with unresolved critical health failures.
- Treat uncertain DB integrity posture as `FAIL_NOW`.
