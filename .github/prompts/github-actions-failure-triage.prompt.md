---
agent: Senior Deploy GitHub Actions
name: github-actions-failure-triage
description: 'Diagnose GitHub Actions and release pipeline failures for this repo, especially CI/CD or StackForge-related deploy workflows; return root cause, blast radius, and the smallest safe fix path.'
argument-hint: 'What workflow run, job failure, log excerpt, PR, or release problem should be triaged?'
---

Related skill: `deployment-github-actions`
Related prompt: `deploy-go-no-go`

Perform focused GitHub Actions failure triage.

## Objective

Identify:

1. the most likely root cause,
2. the affected scope/blast radius,
3. the smallest safe fix,
4. whether the workflow should be retried as-is.

## Inputs

Collect or infer:

- Workflow file and triggering event
- Failing job/step name
- Error output or symptom
- Whether failure affects CI only, release automation, or live deployment path

If logs are incomplete, state the highest-value missing evidence.

## Triage Procedure

1. Classify the failure:
   - syntax/configuration
   - dependency/cache/tooling
   - test/lint/build regression
   - artifact/release packaging
   - environment/secret/permission issue
   - deployment/runtime verification failure

2. Trace the failure boundary:
   - first failing step vs downstream fallout
   - whether `needs` / artifact flow is broken
   - whether branch/tag/environment protections are implicated

3. Check StackForge-specific signals when relevant:
   - release packaging mismatch with binary/checksum expectations
   - deployment assumptions contradict StackForge CLI safety behavior
   - env/config mismatch between `.env.stackforge*` and `stackforge.yaml`

4. Determine retry posture:
   - safe to retry unchanged
   - retry only after config/workflow fix
   - hold release/deploy entirely

## Output Format

1. **Root Cause**
2. **Confidence**: `High` / `Medium` / `Low`
3. **Affected Scope**
4. **Smallest Safe Fix**
5. **Retry Recommendation**: `Retry now` / `Fix first` / `Hold release`
6. **Evidence Reviewed**
7. **Follow-up Hardening**

## Guardrails

- Distinguish the first real failure from secondary noise.
- Prefer narrow fixes over workflow rewrites.
- If a deployment-impacting permission/secret/config issue is unresolved, recommend `Hold release`.
