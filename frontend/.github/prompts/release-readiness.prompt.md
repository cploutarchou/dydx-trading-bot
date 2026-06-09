---
name: release-readiness
description: 'Run a release-readiness pass for frontend changes: lint/build/tests/contracts/responsive checks, risk summary, and go/no-go recommendation with follow-up actions.'
argument-hint: 'Provide target scope (files/features), release context, and required quality gates.'
agent: 'Senior React DeFi Product'
---

Perform a production-focused release readiness evaluation for the requested scope.

## Required checks

1. **Code quality**
   - Lint status
   - Type safety implications
   - Architecture consistency (shared hooks/clients, portal boundaries)

2. **Build and runtime safety**
   - Build viability for affected portal(s)
   - Route/auth/role guard impact
   - Error-state resilience

3. **Test and contract safety**
   - Existing tests coverage relevance
   - Needed regression tests for changed behavior
   - API envelope/normalizer/contract guard risk

4. **Responsive and UX safety**
   - Breakpoint integrity (mobile/tablet/laptop/widescreen)
   - Control reachability and layout stability
   - Loading/error/empty/live-state coherence

## Output format

Return:
- **Gate table** (`Pass`, `Needs Action`, `Blocked`) for each category
- **Risk list** with severity (`P0`, `P1`, `P2`)
- **Required fixes before release** (must-do)
- **Optional hardening tasks** (nice-to-have)
- **Final decision**: `Go` or `No-Go` with rationale

## Constraints

- Keep recommendations scoped to the requested release surface.
- Prefer concrete, verifiable checks over generic advice.
- Do not claim checks were run unless explicitly run in-session.
