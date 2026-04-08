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

- `BacktestLightweightChart` for live financial charting
- `TerminalDataGrid` for dense searchable fintech tables
- websocket-managed hooks in `src/api/hooks.ts` for live state

## Anti-patterns

- Full-card spinners during incremental refresh
- Reflow-heavy charts that re-fit content on every update
- Generic admin tables with no market context
- Repeated one-off table styling instead of reusable terminal patterns
