---
name: tailwind-dark-theme-fintech
description: 'Apply consistent fintech dark-theme design in React/Tailwind surfaces: hierarchy, token usage, financial color semantics, density, and responsive behavior for operator-grade pages.'
argument-hint: 'Describe the component/page, target user, and layout or styling issue to solve.'
user-invocable: true
disable-model-invocation: false
---

# Tailwind Dark Theme Fintech

Use this skill to produce cohesive, high-confidence UI styling for trading/backtest workflows.

## Core palette conventions

- Page base: `bg-slate-900`
- Card/surface: `bg-slate-800`
- Interactive hover: `bg-slate-700`
- Borders: `border-slate-700` (default), `border-slate-600` (inputs)
- Primary text: `text-white`
- Secondary text: `text-gray-300` / `text-slate-300`

## Financial semantics

- Positive/profit: `text-green-400`
- Negative/loss/error: `text-red-400`
- Running/info: `text-blue-300`
- Pending/warn: `text-yellow-300`

Always pair semantic text with accessible contrast and, where helpful, icon or label cues.

## Layout and density rules

1. Put status and critical controls in the top strip.
2. Group metrics by decision context (performance, risk, runtime health).
3. Keep table/chart density high but readable for operators.
4. Avoid visual noise; use motion only for state transitions.

## Responsive checks

- No clipped IDs/hashes/symbols.
- Primary actions remain visible without horizontal scrolling.
- Chips, badges, and filters wrap gracefully on small screens.
- Preserve hierarchy at `sm`, `md`, `lg`, `xl`, and widescreen.

## State design requirements

- Explicit loading, empty, error, success states.
- Error surfaces should include next action (retry, refresh, inspect logs).
- Live views should show freshness and source cues where applicable.
