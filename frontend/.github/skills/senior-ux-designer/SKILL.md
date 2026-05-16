---
name: senior-ux-designer
description: 'Design and implement senior-level fintech UX for React operator surfaces. Use for UI hierarchy, responsive layout, usability of tables/charts/forms, interaction flows, status/error feedback, and high-confidence trading workflows.'
argument-hint: 'Describe user role, target page, pain points, constraints, and acceptance checks.'
user-invocable: true
disable-model-invocation: false
---

# Senior UX Designer

Create high-confidence product UX for DeFi/trading operators with fast scannability, stable live behavior, and clear decision affordances.

## Outcomes this skill drives

- Operators can identify system state and next action in seconds.
- Critical actions are obvious and safe.
- UI feels premium across device sizes.
- Backend-only integration boundary remains intact.

## Workflow

1. **Frame the operator decision**
   - Who is the user and what decision must be faster?
   - What is the success metric (speed, confidence, error reduction)?

2. **Map constraints**
   - Keep browser-to-backend boundary (`frontend -> backend`) strict.
   - Respect auth/session continuity and protected-route behavior.
   - Preserve live update stability (websocket-first + HTTP fallback).

3. **Design hierarchy before styling**
   - Top strip: status, freshness, source, critical controls.
   - Mid section: key performance/risk signals.
   - Lower detail: tabs/panels for drill-down and deferred load.

4. **Apply interaction safety**
   - Disable actions when state is ineligible.
   - Handle conflicts (e.g. `409`) with refresh + stable messaging.
   - Use explicit loading/error/empty/success states.

5. **Responsive acceptance pass**
   - Validate small/mobile, tablet, laptop, widescreen.
   - No clipped IDs/tokens, no hidden primary actions, no overflow traps.
   - Preserve readability density for operator workflows.

6. **Ship with consistency**
   - Reuse shared components/hooks over one-off logic.
   - Keep financial color semantics and copy tone consistent.
   - Keep motion meaningful (avoid decorative churn).

7. **Completion checks**
   - `npm run lint`
   - `npm run build`
   - `npm run typecheck` when type contracts or API shapes changed

## Decision branches

- If live updates feel unstable: prioritize clear freshness/recovery states before reconnection tweaks.
- If action conflict appears: refresh server state, keep user intent, avoid action-ping-pong behavior.
- If payload shapes vary: normalize at API boundary and add regression tests.

## Quality bar

- Operator clarity in under 5 seconds.
- No jarring reset behavior during live updates.
- Mobile layout remains premium and functional.
- Validation checks pass before completion.
