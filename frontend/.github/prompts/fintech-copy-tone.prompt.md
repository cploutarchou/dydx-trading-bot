---
name: fintech-copy-tone
description: 'Produce consistent fintech product microcopy for statuses, errors, confirmations, loading labels, and operator helper text. Use when writing or refining UX copy for trading/backtest/bot interfaces.'
argument-hint: 'Paste current copy and context (surface, state, audience, objective).'
agent: 'Senior React DeFi Product'
---

Rewrite UI copy using a consistent fintech operator tone:

## Tone goals

- Clear, concise, and confidence-building
- Professional and direct (no fluff)
- Action-oriented with explicit next steps
- Calm under failure states

## Output format

Return a markdown table with columns:

1. `Location`
2. `Current Copy`
3. `Improved Copy`
4. `Why`

## Style rules

- Keep labels short and scannable.
- Prefer concrete state language (`Running`, `Recovering`, `Completed`, `Failed`).
- For errors, include next action where possible.
- For conflicts, preserve user intent and avoid blame language.
- Keep sentence case for helper text and title case only for headings/buttons where appropriate.

## Domain consistency

- Use financial terms consistently (PnL, drawdown, win rate, exposure, runtime).
- Respect backend boundary language (do not imply direct exchange calls from browser).
- Align with dark-theme, signal-rich operator UI expectations.

Now apply these rules to the provided copy.
