---
name: senior-ui-designer
description: 'Design and implement fintech-grade React UI/UX with strong hierarchy, responsive behavior, live-data stability, and backend-safe integration. Use when tasks mention UI, UX, styling, layout, table/chart usability, operator workflow, or responsiveness.'
argument-hint: 'Describe the page/surface, user goal, constraints, and acceptance checks.'
user-invocable: true
disable-model-invocation: false
---

# Senior UI Designer (DeFi Frontend)

Use this skill to ship premium product UX for trading/operator workflows while preserving data correctness and backend boundaries.

## When to use

- New page or component UX
- Redesigning existing layouts for speed/scannability
- Improving live status/readiness/failure communication
- Responsive issues across mobile/tablet/laptop/widescreen
- Trading tables/charts/cards that need dense but clear information hierarchy

## Workflow

1. **Define operator outcome first**
   - Who is acting (operator/admin/trader)?
   - What decision/action must become faster or safer?
   - What is the minimum signal needed above the fold?

2. **Map constraints before design**
   - Backend-only integration boundary (`frontend -> backend`)
   - Session/auth continuity and route guard behavior
   - Live update model (websocket-first + HTTP bootstrap/recovery)
   - Existing shared primitives/hooks to reuse

3. **Design the information hierarchy**
   - Primary status strip: state, freshness, source, control readiness
   - Secondary metrics: risk/return/context
   - Deep detail tabs/panels: deferred loading where appropriate
   - Ensure clear visual grouping and strong scanning paths

4. **Apply UX patterns for trading surfaces**
   - Dense but readable cards/tables/charts
   - Explicit empty/loading/error states
   - Financial color semantics (profit/loss/neutral)
   - Action controls should be state-safe and conflict-tolerant

5. **Responsive pass (required)**
   - Validate breakpoints at small/medium/large/wide
   - Prevent clipped IDs/labels and overflow regressions
   - Keep critical actions visible without layout jumps

6. **Implement with minimal-risk edits**
   - Prefer shared UI utilities/components over one-off logic
   - Keep naming and styling conventions consistent
   - Avoid unnecessary page reset/flicker in live views

7. **Validation and completion checks**
   - Run `npm run lint`
   - Run `npm run build`
   - Run `npm run typecheck` when TypeScript contracts changed
   - Add targeted regression tests when API/normalization logic changes

## Decision branches

- **If live stream is unstable**: prefer stale/recovery UI state first, then reconnect behavior tuning.
- **If control actions conflict (`409`)**: refresh status and preserve user intent; avoid action-flip loops.
- **If backend payload shape is inconsistent**: normalize at API boundary and test contract behavior.
- **If design density hurts readability**: reduce visual noise, not information quality.

## Quality bar (must be true)

- Operators can identify state, risk, and next action in under 5 seconds.
- Live state changes do not cause jarring resets or ambiguity.
- UI remains premium and legible on small screens.
- Integration boundary remains backend-only.
- Lint/build pass before completion.
