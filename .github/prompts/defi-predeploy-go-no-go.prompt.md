---
agent: agent
name: defi-predeploy-go-no-go
description: "Run a pre-deploy go/no-go gate for Python DeFi trading changes and return a clear APPROVE or HOLD decision with blocking risks and mitigation steps."
argument-hint: "What release, PR, or change set should be evaluated for go/no-go?"
---

Related skill: `defi-python-algo-trading`
Related prompt: `defi-risk-review`

Perform a concise but strict pre-deploy release gate review.

## Objective

Return one final decision for deployment readiness:

- `APPROVE`
- `HOLD`

The decision must be evidence-based and tied to specific checks below.

## Inputs

Collect or infer:

- Scope (`PR`, files, feature, release notes)
- Environment (`testnet` or `mainnet`)
- Strategy family (mean reversion / momentum / market making / hybrid)
- Capital/risk constraints (if available)

If any critical input is missing, state assumptions explicitly.

## Gate Checks (Blocking)

### 1) Execution Safety

- Atomic paired order behavior is preserved.
- No orphaned-leg path exists after partial failures.
- Emergency cleanup path is validated and reachable.

### 2) Risk Controls

- Exposure limits are defined and enforced.
- Kill-switch/circuit-breaker behavior is present for repeated failures.
- Drawdown or equivalent capital-protection controls are not weakened.

### 3) Market/DeFi Constraints

- Precision formatting is correct for all exchange-bound values.
- Slippage and liquidity assumptions are reasonable for sizing.
- Funding/mark/oracle anomalies are handled or explicitly bounded.

### 4) Correctness & Regression

- Relevant tests for touched paths pass.
- Strategy behavior remains valid for the target strategy family.
- No known high-severity regression remains unresolved.

### 5) Operability

- Critical telemetry/logging is present for key events.
- Alerting exists for catastrophic execution failures.
- Emergency operational path is documented or obvious.

## Scoring Heuristic

- Any unresolved critical finding in checks 1-3 => `HOLD`
- Missing evidence in 2+ blocking checks => `HOLD`
- Otherwise => `APPROVE` with residual risks listed

## Output Format

1. **Decision**: `APPROVE` or `HOLD`
2. **Confidence**: `High` / `Medium` / `Low`
3. **Blocking Findings** (if any)
4. **Top Residual Risks**
5. **Required Actions Before Deploy** (for HOLD)
6. **Post-Deploy Safeguards** (for APPROVE)
7. **Evidence Summary** (tests/logs/files reviewed)

## Guardrails

- Never give `APPROVE` if execution safety is uncertain.
- Prefer smallest set of concrete mitigation steps.
- Separate hard blockers from nice-to-have improvements.
- Keep final answer concise and operations-friendly.
