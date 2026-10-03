# 10 — UI Audit (visual design review)

Evidence: rendered-app visual reviews (1440×900 desktop, 375×812 mobile) of landing, dashboard, backtests/new, bots, plus DOM/structure inspection of all major surfaces; production bundle inventory. Grading against production DeFi/trading-terminal standards.

## Overall grade: **7 / 10** — coherent brand system, inconsistent density and component discipline.

## Typography
- Strong: distinctive pairing (Sora/Manrope/JetBrains Mono per vestigial config — fonts actually ship); clear hierarchy eyebrow→h1→lede on every page; tabular numbers not used where they matter (use `font-variant-numeric: tabular-nums` for P&L/KPIs — P3).
- Issues: eyebrow/label sizes crowd at 375px (mobile review); long page-headers repeat the same sentence twice (nav description + page lead) — pick one.

## Color & semantics
- Consistent state palette (emerald/cyan/amber/rose) as documented; charts themed via `createTradingChart` factory ✅.
- Issues: `+$0` in profit green (UX-07); contrast in secondary text blocks flagged in landing review (slate-400 on slate-950 at small sizes); financial red/green not colorblind-paired (no icons/underline differentiation on P&L) — P2 a11y-adjacent.

## Layout & spacing
- Shell: sidebar (~300px) + sticky header + single-column content with 4-up KPI strips — correct terminal skeleton.
- Issues from visual review: dashboard hero consumes first fold with an oversized greeting while KPIs clip below fold (density complaint); card padding varies subtly across desks (12/16/20px mixes); sidebar descriptions double the height of every nav group — demote to tooltip/hover.

## Component consistency matrix

| Component | Variants found | Problem | Proposed standard |
|---|---:|---|---|
| Primary button | 3 (`premium-button-primary`, page-specific `rounded-*` overrides) | radius/height drift (8/12/16px radii) | one `Button` with size+variant props; tokenized radius |
| Inputs | 2 systems (`premium-input` vs legacy `border-slate-600` in older forms) | focus ring + height differ | all forms on `premium-input` + shared `Field` wrapper (also fixes a11y labels) |
| Cards/panels | 3 (`premium-panel`, `operator-section-card`, ad-hoc `bg-slate-800 rounded-lg`) | padding/radius/border mixes | `PlatformPanel` everywhere; deprecate ad-hoc |
| Status badges/pills | 3 (StatusBadge, `operator-status-pill`, inline span pills) | tone naming differs | one `StatusPill` with semantic tones |
| Tables | 3 (`TerminalDataGrid` ×4 files, hand-rolled tables in BacktestList/CRM) | zebra/hover/density differ | TerminalDataGrid or a thin table primitive; density prop |
| Empty states | 2 (EmptyState component vs ad-hoc paragraphs) | illustration/copy rhythm differs | EmptyState with icon+action slot |
| Toasts | 1 (global ToastContainer) — good | — | keep |
| Modals/dialogs | 2 (ActionDialog vs HeadlessUI-pattern remnants) | focus-trap behavior differs | ActionDialog only (already the README standard) |
| Skeletons | ad-hoc/absent | flash-of-empty-state | `Skeleton` primitive tied to query status |

## Navigation & chrome
- Sidebar nav = buttons (JS navigation): loses middle-click/open-in-tab — acceptable SPA tradeoff, but consider `<Link>` for route items (also improves a11y semantics).
- Breadcrumb + page header + jump bar are excellent; "Environment/Network/Local time" status strip is a differentiator — keep.
- Theme combobox naming is clean; disabled Light option is a visual bug (UX-03).

## Charts
- lightweight-charts themed centrally ✅; empty chart states handled ("No completed backtests yet…") ✅; ensure all charts set tabular numerals + min-height to prevent CLS (P3).

## Responsive (visual)
- 1440/1920: clean. 768: sidebar collapses to drawer (OK). 375: no horizontal overflow ✅ (measured), but KPI 2-up squeeze + label crowding. 320: still no overflow ✅ (measured on form-heavy page).
- Wide tables rely on page-level horizontal scroll — add scroll affordance (shadow/gradient) at mobile.

## Bundle/render quality signals
- Build splits sanely (page chunks 11–111KB; vendors isolated). `index-*.js` 217KB monolith holds eagerly-loaded shared code — audit its imports during Stage 6.
- TanStack devtools button appears in dev only ✅ but rendered as unlabeled floating icon — add aria-label (P3).

## What to keep (differentiators)
Execution-desk framing; status strip in header; command palette; workflow rails; themed chart factory; consistent dark palette; restrained motion (animejs confined to background canvas).
