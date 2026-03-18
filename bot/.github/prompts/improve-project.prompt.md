---
description: "Team prompt to improve the dYdX bot with prioritized, safe, validated changes"
name: "Improve Project (Team)"
argument-hint: "Focus area: reliability, strategy, API, DB, security, performance, tests"
agent: "agent"
---

Improve this dYdX trading bot project in a focused, high-impact way.

Focus area: ${input:Focus area (reliability/strategy/API/DB/security/performance/tests)}

## Team expectations

- Keep changes small, reviewable, and backward compatible.
- Follow existing architecture and coding conventions.
- Validate changes before finalizing.

## Workflow

1. Inspect relevant files and identify root causes.
2. Rank opportunities by impact and implementation risk.
3. Build a short checklist before editing.
4. Apply incremental fixes and verify each step.
5. Summarize what changed and why.

## Output format

1. **Findings** — ranked issues/opportunities
2. **Plan** — concise checklist
3. **Changes made** — files touched + purpose
4. **Validation** — tests/checks and outcomes
5. **Next steps** — 2–5 practical follow-ups

## Guardrails

- No hardcoded secrets; use environment-driven config.
- Preserve API contracts and bot lifecycle semantics unless explicitly changed.
- Prefer minimal-risk improvements over broad rewrites.
