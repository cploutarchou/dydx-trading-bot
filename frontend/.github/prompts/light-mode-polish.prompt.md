---
name: light-mode-polish
description: 'Apply premium light-mode polish to a specific page or component. Use when: fixing light mode for a page, improving day-mode contrast, making light theme match dark theme quality.'
argument-hint: "e.g. 'authenticated dashboard tables and charts' or 'login page coming-soon surface'"
---

# Light Mode Polish Pass

Apply a premium fintech-grade light-mode refinement to `{{target}}`.

## Steps

1. Load and follow `.github/skills/light-mode-theme-fintech/SKILL.md`
2. Read the current file(s) for `{{target}}` to understand all Tailwind classes and semantic selectors.
3. Read relevant sections of `src/index.css` for existing `[data-theme='light']` rules.
4. Identify every surface type in scope:
   - Background / shell
   - Cards / panels (all elevation tiers)
   - Tables (header, row, hover, zebra)
   - Charts (tooltip, axis labels, gridlines)
   - Control rows (inputs, buttons, chips, badges)
   - Status indicators (profit, loss, info, warning, violet)
5. For each surface, apply overrides following the skill's token reference.
6. Verify with browser `data-theme="light"` — sample computed styles.
7. Run `npm run lint` — confirm zero new errors.
8. Confirm dark mode is untouched.

## Target: `{{target}}`
