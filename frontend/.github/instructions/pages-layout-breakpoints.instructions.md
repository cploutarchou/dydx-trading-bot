---
description: 'Use when editing React route pages in src/pages. Enforces layout hierarchy, breakpoint behavior, and operator-grade responsive acceptance checks for trading/fintech surfaces.'
name: 'Pages Layout + Breakpoints Acceptance'
applyTo: 'src/pages/**'
---

# Pages layout and breakpoint acceptance checks

When editing files under `src/pages/**`, follow these rules before finishing:

## Layout hierarchy

- Keep a clear top-level information hierarchy:
  1. status + critical controls
  2. key metrics/signals
  3. detailed panels/tabs
- Preserve scannability with meaningful grouping and spacing.
- Avoid generic admin layout patterns when a product workflow pattern fits better.

## Responsive behavior

- Validate small/mobile, tablet, laptop, and widescreen layouts.
- No clipped content for IDs, run hashes, market symbols, or status chips.
- Primary actions must remain reachable without horizontal scrolling.
- Avoid layout shifts that move controls unpredictably.

## Live-data UX safeguards

- Show freshness and source cues when the page is live-data driven.
- Distinguish running vs recovering vs stale states with consistent semantics.
- Keep action availability aligned with normalized backend state.

## Component/style consistency

- Reuse shared UI primitives/hooks where available.
- Keep dark-theme and financial color semantics consistent.
- Keep status/error copy concise and action-oriented.

## Required validation

- Run `npm run lint`.
- Run `npm run build`.
- If API/contract typing changed, run `npm run typecheck`.
