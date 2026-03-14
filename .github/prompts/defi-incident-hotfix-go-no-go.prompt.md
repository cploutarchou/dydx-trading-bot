---
mode: agent
name: defi-incident-hotfix-go-no-go
description: 'Run an emergency hotfix go/no-go gate for Python DeFi trading incidents; return immediate APPROVE or HOLD with critical blockers and minimum safe mitigation steps.'
argument-hint: 'What incident hotfix, commit, PR, or file set should be emergency-evaluated?'
---

Related skill: `defi-python-algo-trading`
Related prompts: `defi-risk-review`, `defi-predeploy-go-no-go`

Perform an incident-mode, time-boxed release gate focused on immediate trading safety.

## Mode
- Assume urgency and limit analysis to highest-impact safety checks.
- Prefer false negatives over false positives (if uncertain on safety, HOLD).
- Keep output short and operational.

## Objective
Return exactly one decision:
- `APPROVE_NOW`
- `HOLD_NOW`

## Inputs
Collect or infer quickly:
- Incident summary and user impact
- Hotfix scope (files/functions changed)
- Target environment (`testnet`/`mainnet`)
- Rollback path availability

If critical inputs are missing, state assumptions and lower confidence.

## Emergency Gate Checks (Hard Blockers)

### A) Atomic Execution Safety (Mandatory)
- Any chance of orphaned positions after partial fills?
- Emergency cleanup/reduce-only path intact?
- Any new code path bypassing safety checks?

### B) Blast Radius Control (Mandatory)
- Is there a kill-switch / abort mechanism available now?
- Can exposure be capped immediately (size/concurrency limits)?
- Is rollback feasible within minutes?

### C) Market-Facing Correctness (Mandatory)
- Precision formatting preserved for all order parameters.
- No obvious slippage/liquidity assumption breakage in touched paths.
- Async order/API paths correctly awaited (no silent coroutine failures).

### D) Minimal Verification Evidence (Mandatory)
- At least one targeted test or deterministic check for the touched path.
- Log/trace evidence supports expected hotfix behavior.

## Decision Rules
- Any unresolved issue in A/B/C => `HOLD_NOW`
- Missing evidence in D => `HOLD_NOW`
- Otherwise => `APPROVE_NOW` with strict post-deploy safeguards

## Output Format
1. **Decision**: `APPROVE_NOW` or `HOLD_NOW`
2. **Confidence**: `High` / `Medium` / `Low`
3. **Critical Blockers** (max 5 bullets)
4. **Minimum Safe Actions** (what must happen before approval)
5. **30-Minute Post-Deploy Safeguards**
6. **Rollback Trigger Conditions**
7. **Evidence Reviewed** (tests/logs/files)

## Post-Deploy Safeguard Template (if APPROVE_NOW)
- Set temporary reduced exposure limits
- Enable enhanced logging/alerts for execution failures
- Monitor fill quality/slippage and cleanup events every 5 min
- Predefine rollback threshold and owner on-call

## Guardrails
- Do not output `APPROVE_NOW` if execution safety is uncertain.
- Prioritize capital preservation over feature completeness.
- Separate immediate blockers from follow-up debt.
