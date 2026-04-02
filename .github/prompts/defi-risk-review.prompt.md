---
agent: agent
name: defi-risk-review
description: "Perform a focused risk review for Python DeFi trading changes (execution safety, exposure, slippage, liquidity, funding, and failure handling). Use this for pre-merge or pre-deploy safety checks."
argument-hint: "What change, PR, file, or behavior should be risk-reviewed?"
---

Related skill: `defi-python-algo-trading`

Run a focused risk review only (not full implementation) for the provided scope.

## Inputs to Collect

- Scope target (file, function, PR, or feature)
- Strategy family (mean reversion / momentum / market making / hybrid)
- Deployment context (testnet/mainnet, expected cadence, capital constraints)

If an input is missing, infer from code/comments first. Ask only minimal clarification questions if still ambiguous.

## Risk Review Procedure

1. Identify the critical path affected by the change (signal generation, sizing, execution, close, persistence, recovery).
2. Check **atomic pair safety**:
   - Any path where one leg can remain open unintentionally?
   - Is emergency cleanup present and reliable?
3. Check **exposure controls**:
   - Max per-trade risk and total concurrent exposure boundaries
   - Position sizing behavior under volatile market moves
4. Check **execution quality risks**:
   - Precision formatting correctness (`format_number` + exchange metadata)
   - Slippage assumptions vs current sizing and market liquidity
   - Rate-limit/throttling sensitivity and retry behavior
5. Check **DeFi-specific market risks**:
   - Funding impact for expected holding durations
   - Liquidity degradation / spread blowout handling
   - Oracle/mark-price anomaly handling and fallbacks
6. Check **state and recovery risks**:
   - JSON state consistency (`bot_agents.json`, `cointegrated_pairs.json`)
   - Restart/recovery behavior after partial failures
7. Check **observability and operational readiness**:
   - Are critical events logged with enough dimensions?
   - Are high-severity failures alerting correctly?
   - Is there a clear emergency-close runbook path?

## Output Format

Return:

1. **Risk Verdict**: `LOW`, `MEDIUM`, or `HIGH`
2. **Top Findings**: short bullet list of concrete risks
3. **Required Fixes Before Merge/Deploy**
4. **Recommended Improvements** (non-blocking)
5. **Verification Plan**: exact tests/checks to run next

## Guardrails

- Prefer concrete evidence from code paths over speculation.
- Call out unknowns explicitly.
- If a HIGH risk is found in execution safety, propose a minimal immediate mitigation path first.
- Keep review concise and actionable.
