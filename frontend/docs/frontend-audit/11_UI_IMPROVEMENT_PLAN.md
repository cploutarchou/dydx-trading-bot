# 11 — UI Improvement Plan

Progressive standardization — no rewrite. Prerequisite for several items: `12_DESIGN_SYSTEM_RECOMMENDATIONS.md` tokens.

## Wave U1 — Quick visual wins (XS–S, no token work needed)

| # | Change | Fixes | Est |
|---|---|---|---|
| U1.1 | Standardize radii: buttons/inputs 8px, cards 8px, dialogs 12px (grep `rounded-` and replace drift) | UI-10 radius drift | S |
| U1.2 | `font-variant-numeric: tabular-nums` on all P&L/KPI/metric values | terminal readability | XS |
| U1.3 | Zero-P&L neutral gray (pairs with UX 1.5) | UI color semantics | XS |
| U1.4 | P&L indicators gain an icon/arrow so color is not the only signal | colorblind safety | XS |
| U1.5 | KPI strip: 1-col wrap below 400px; reduce label size step at <768px | mobile crowding | S |
| U1.6 | Scroll-shadow affordance on horizontally-scrollable tables | mobile tables | XS |
| U1.7 | Sidebar: descriptions demoted to `title`/tooltip; groups collapse to icon+label at ≤1280px | chrome noise/density | S |
| U1.8 | Remove duplicated sentence pattern (nav description vs page lead) — page lead wins | copy redundancy | S |

## Wave U2 — Component unification (S–M each; do with design tokens)

| # | Change | Replaces | Est |
|---|---|---|---|
| U2.1 | `Button` primitive (variant × size × loading) — migrate 46 `premium-button` usages mechanically | 3 button systems | M |
| U2.2 | `Field` wrapper (label + input + hint + error) — fixes FE-A11Y-01 while unifying inputs; migrate BacktestRunner + BotManager first (financial forms) | 2 input systems | M |
| U2.3 | `StatusPill` semantic component (tone + dot + label); migrate StatusBadge + operator-status-pill + inline pills | 3 pill variants | S |
| U2.4 | Table primitive (or adopt TerminalDataGrid everywhere) with density prop tied to `operator-ui-density` | 3 table styles | M |
| U2.5 | `Skeleton` primitive wired to query `isFetching` for the 6 highest-traffic lists | flash-of-empty | S |
| U2.6 | Dialog consolidation on ActionDialog (focus-trap verified once, reused) | 2 modal systems | S |

## Wave U3 — Density & hierarchy (dashboard/bots operator screens)

| # | Change | Rationale | Est |
|---|---|---|---|
| U3.1 | Dashboard: compact hero (greeting + date one-liner), KPIs above the fold at 900px | visual review: fold waste | S |
| U3.2 | Dashboard: KPI cards get context microcopy in empty state ("run a backtest to populate") | KPIs clipped w/o context | XS |
| U3.3 | Bots desk: reduce repeated section headers; merge "Operator notes" into a collapsible | density | S |

## Wave U4 — Chart & data-display polish

| # | Change | Est |
|---|---|---|
| U4.1 | Min-height reservation on all chart containers (kills CLS on data arrival) | XS |
| U4.2 | Tooltip standardization across lightweight-charts + any list-based figures | S |
| U4.3 | Number formatting via shared `formatUsd/formatPct` (see code-quality duplication) so all desks render identical money strings | S |

## Sequencing & risk

- U1 is safe any time (visual only, screenshot tests in Suite H protect it).
- U2.2 is the highest-leverage item (unifies inputs AND closes the P2 a11y finding) — schedule immediately after tokens exist; do forms in pairs (Runner+BotManager, then settings panels).
- U2.1/U2.4 are mechanical migrations — split per desk to keep PRs reviewable.
- Everything is additive to existing classes; no big-bang swap.

## Definition of done (UI track)

1. `rounded-` audit passes with ≤3 distinct radii.
2. Zero ad-hoc `bg-slate-800` panels in desks (grep clean on migrated surfaces).
3. Every form field has a real `<label>` (a11y gate doubles as UI gate).
4. Screenshot suite green at 375/768/1440 for the 8 canonical screens.
