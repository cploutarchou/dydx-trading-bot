---
description: "Use when improving project quality, reliability, security, performance, API behavior, or migrations. Enforces consistent findings/plan/changes/validation output with risk and rollback notes."
name: "Improvement Output Standard"
---

# Improvement Output Standard

Use this when doing project-improvement work (for example via improvement, hardening, optimization, API enhancement, or migration-review prompts).

## Response structure (required)

Always provide results in this order:

1. **Findings**
2. **Plan**
3. **Changes made**
4. **Validation**
5. **Risk & rollback**
6. **Next steps**

## Findings requirements

- Rank findings by impact and risk (high/medium/low).
- Separate root causes from symptoms.
- Call out security or data-integrity implications explicitly.

## Plan requirements

- Keep the plan short and incremental.
- Prefer backward-compatible changes.
- Mention dependencies or prerequisites before edits.

## Changes made requirements

- List each touched file with one-line purpose.
- Highlight any behavior or contract changes.
- If no code was changed, explain why.

## Validation requirements

- Include what was validated (tests, lint, type checks, smoke checks).
- Report pass/fail outcomes and notable warnings.
- If a check was skipped, state why and the risk.

## Risk & rollback requirements

- Assign an overall rollout risk: **Low**, **Medium**, or **High**.
- Provide a concrete rollback approach (what to revert, stop, or disable).
- For DB or stateful changes, include data-safety notes.

## Style

- Keep it concise and actionable.
- Avoid vague statements like “looks fine”; use concrete evidence.
- Prefer small next steps (2–5 items) over broad rewrites.
