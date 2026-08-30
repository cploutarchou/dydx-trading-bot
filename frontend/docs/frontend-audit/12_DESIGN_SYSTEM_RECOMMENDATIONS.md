# 12 — Design System Review & Recommendations

## Current state: tokens exist; a system is half-born

**What exists (real):**
- ~120 CSS custom properties in `src/index.css` `:root`: `--color-*`, `--app-*`, `--panel-*`, `--execution-*`, `--chart-*`, `--body-gradient-*`, `--duration-*` + full `[data-theme='light']` override blocks (unreachable today).
- Tailwind v4 maps `execution.*` colors to those variables (README claims; verify after config cleanup).
- Shared primitives: `PlatformPageHeader`, `PlatformPanel`, `PlatformStatCard`, `StatusBadge`, `EmptyState`, `InlineNotice`, `ActionDialog`, `PortalSubnav` (`src/components/ui/PlatformUI.tsx`), `TerminalDataGrid`, `LiveState`, `PageContainer`, `ErrorBoundary`.
- Class families: `premium-*` (×246 usages), `operator-*` (×86), `workspace-*` (×18), `terminal-*` (×5) — 41 classes defined in the 7,431-line index.css.
- Theme infra: `ThemeProvider` + pre-paint inline script + `ui.theme` persistence; chart theming factory.

**What's missing (gaps):**
- No spacing scale token (paddings are per-component literals).
- No z-index scale, no radii scale, no elevation/shadow tokens.
- No interaction-state tokens (focus ring spec differs per component family).
- No breakpoint tokens documented for the custom classes.
- Component variants are class strings, not typed props (no single source of "button has variants x/y/z").
- `tailwind.config.js` (fonts Manrope/Sora/JetBrains Mono + execution colors) is **vestigial** under Tailwind v4 — no `@config` reference in index.css, so its content/extend is inert. Confusing trap.

## Recommendation: lightweight token + primitive completion (not a rewrite)

### Step 1 — Make the tailwind config truthful (XS)
Either delete `tailwind.config.js` and move font/color mapping into Tailwind v4 `@theme` in index.css (preferred — one source), or reference it via `@config`. Today the file lies to every new engineer.

### Step 2 — Add the missing scales to `:root` (S)
```css
--space-1..--space-8 (4/8/12/16/24/32/48/64), --radius-sm/md/lg (8/12/16),
--z-base/overlay/dialog/toast (0/40/60/80), --focus-ring (width+color),
--shadow-panel, --shadow-dialog, --transition-fast/normal (map --duration-*)
```
Then replace literals inside the 41 `premium/operator/workspace` classes — contained, mechanical.

### Step 3 — Type the variants of the top-6 primitives (M; = U2 in 11_UI_IMPROVEMENT_PLAN)
`Button(variant: primary|ghost|danger, size: sm|md, loading)`, `Field(label, hint, error, required)`, `StatusPill(tone, pulse?)`, `Panel(pad, density)`, `DataGrid(density)`, `Dialog(danger?)`. Keep classNames as implementation detail.

### Step 4 — Document the system in-repo (XS)
One page: token list, primitive API, tone semantics (emerald=healthy, cyan=live, amber=warning, rose=failure — already the README contract), do/don't screenshots. Update `FINTECH_UI_STANDARDS.md` to point at it.

### Step 5 — (Roadmap) light mode re-enablement
All light overrides already exist; re-enabling is a product decision + contrast audit (see 13_ACCESSIBILITY_AUDIT), then flip `FORCE_DARK_THEME` and restore the ThemeToggle option.

## Interaction states checklist (apply during Step 3)
- Hover/focus-visible/active/disabled for Button, nav items, tabs.
- Focus-visible ring token applied to all interactive elements (currently inconsistent — a11y finding).
- Loading states: buttons get spinner+label (exists on financial forms — generalize).
- Disabled: current `disabled:opacity-50/60` drift → one token.

## Explicitly avoid
- Introducing a component library (shadcn/MUI) — 68 components already exist; wrapping would churn every screen.
- CSS-in-JS or tailwind@v4 re-migration — the utility + custom-class hybrid is working; finish tokenizing instead.
- Building a Storybook now — the Playwright screenshot suite (Suite H) gives the same regression protection with less upkeep; revisit if the team grows.
