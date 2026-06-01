# Fintech UI Standards

Use this document as the frontend quality bar for production-grade DeFi surfaces.

## Design principles

- Prefer terminal-style density over marketing-style emptiness.
- Keep live data stable on screen; update in place instead of flashing loaders or resetting panels.
- Use websocket-first delivery for live state and keep HTTP for bootstrap, recovery, and historical pulls.
- Surface market context, sync state, and data freshness visibly.
- Make tables actionable: search, sort, filter, paginate, sticky headers, and concise per-row hierarchy.

## Backtest standards

- The primary backtest screen should feel like a control room, not a static report.
- Price and equity charts should support timeframe switching and preserve viewport during live updates.
- Summary metrics must include both performance and stream health.
- Trades and positions should render inside fintech-grade data grids with search, filters, and pagination.
- Heavy datasets should lazy-load by tab, but once loaded they should refresh softly.

## Table standards

- Use sticky headers with uppercase micro-labels and clear sort affordances.
- Rows should have a primary field plus one secondary context line, not single-line flat cells everywhere.
- Monetary fields must use color semantics consistently:
  - positive: emerald
  - negative: rose
  - live/realtime: cyan
  - degraded/recovering: amber
- Pagination belongs inside the panel with visible row counts and page-size control.
- Search should be immediate but resilient; use deferred input handling for large tables.

## Live-state standards

- Show whether the stream is healthy, reconnecting, or degraded.
- Show “last updated” time near the surface, not hidden in logs.
- During live updates, never clear already-rendered data unless the underlying dataset is truly empty.
- Charts must not auto-jump or auto-fit on every tick.

## Navigation standards

- Navigation should be operator-first: fast to scan, keyboard-friendly, and grouped by workflow.
- Provide a global command palette for route jumping and quick actions.
- Keep quick actions close to the main navigation, not buried in page content only.
- Header chrome should expose environment, online state, and operator context without overwhelming the page.
- Breadcrumbs should reflect route intent, not raw URL segments.

## Public website standards

- The public website must explain the product before the user reaches auth.
- Marketing, pricing, and auth pages should share the same premium visual language as the operator platform.
- Pricing should describe operator value, not generic SaaS fluff.
- Registration and security setup should feel like premium onboarding, not disconnected utility forms.
- Public CTAs should move users cleanly into trial, subscription, or sign-in flows.

## Rollout targets

- Backtests: complete
  - control-room header
  - timeframe-aware lightweight chart
  - terminal-grade positions/trades grids
- Strategy Runtime: pending
  - shared live table shell
  - compact run-state chips
  - sortable signal/event tape
- Bot Manager: pending
  - reusable live stats cards
  - WS-connected exposure/health grid
  - clearer degraded-state UX

## Shared components to prefer

- `PlatformPageHeader`, `PlatformPanel`, `PlatformStatCard`, `StatusBadge`, `EmptyState`, and `PortalSubnav` from `src/components/ui/PlatformUI.tsx` for unified page structure, portal navigation, status semantics, and operational panels across public, client, CRM, admin, and IB surfaces.
- `BacktestLightweightChart` for live financial charting
- `CumulativePnlChart` for dashboard-level equity and cumulative-PnL trend views
- `createTradingChart` from `src/components/charts/lightweightTheme.ts` for consistent chart styling across surfaces
- `TerminalDataGrid` for dense searchable fintech tables
- websocket-managed hooks in `src/api/hooks.ts` for live state

## Platform design-system direction

- Use ExecutionLab as the product identity across public, client, CRM, admin, and IB portals.
- Keep page headers consistent: kicker, concise title, operational description, and only high-value actions.
- Prefer 8px radii for cards, buttons, tabs, panels, badges, and inputs.
- Use cyan for live/action context, emerald for positive/approved, amber for pending/review, rose for destructive or failed, violet for backoffice/admin segmentation, and slate for neutral states.
- Place secondary portal navigation in `PortalSubnav` so CRM and IB tabs share active states, overflow behavior, and subdomain affordances.
- Use `TerminalDataGrid` for high-density directories and audit tables before creating one-off table markup.
- Dangerous operational actions must include clear consequence copy and confirmation before mutation.

## Anti-patterns

- Full-card spinners during incremental refresh
- Reflow-heavy charts that re-fit content on every update
- Generic admin tables with no market context
- Repeated one-off table styling instead of reusable terminal patterns
