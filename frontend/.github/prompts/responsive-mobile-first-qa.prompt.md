---
name: responsive-mobile-first-qa
description: 'Run a structured responsive QA pass for fintech/operator pages across mobile, tablet, laptop, and widescreen. Use when validating breakpoints, layout integrity, and control accessibility before sign-off.'
argument-hint: 'Provide page/component, key user flow, and breakpoints/devices to validate.'
agent: 'Senior React DeFi Product'
---

Perform a responsive QA review and propose concrete fixes.

## QA checklist

Validate these for `sm`, `md`, `lg`, and widescreen:

1. **Hierarchy**
   - Status + critical controls appear first
   - Key metrics are immediately scannable
   - Detail panels/tabs are reachable without confusion

2. **Layout integrity**
   - No clipped hashes/IDs/symbol chips
   - No horizontal scroll to reach primary actions
   - Tables/charts keep usable density and readability

3. **State UX**
   - Loading/error/empty states are visible and actionable
   - Live surfaces show freshness and source cues when relevant
   - Critical actions remain stable during state transitions

4. **Accessibility & ergonomics**
   - Tap targets remain practical on mobile
   - Contrast is sufficient in dark theme
   - Keyboard focus order is predictable

## Output format

Return:
- A pass/fail table by breakpoint and area
- Prioritized fixes (`P0`, `P1`, `P2`)
- Suggested implementation snippets/changes only where needed
- Final go/no-go recommendation for release
