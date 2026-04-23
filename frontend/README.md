# Frontend Service

The frontend is the React application for the public website, authentication flows, and operator workspace.

## Responsibilities

- render the public marketing site and pricing pages
- handle login, registration, 2FA, and account flows
- provide the authenticated trading workspace
- display live backtests, strategies, bots, and market views
- consume backend HTTP and websocket routes only

## Runtime

- framework: React 19 + TypeScript + Vite
- default dev port: `5173`
- API target: backend on `8888`
- registration verification: set `VITE_TURNSTILE_SITE_KEY` to a Cloudflare Turnstile
  Managed widget site key. Widget mode is configured in Cloudflare; the frontend
  render options only control client presentation such as size and theme.

## Integration Rule

The frontend must never talk directly to the Python bot API in product code.

Allowed:

- backend HTTP routes
- backend websocket routes

Not allowed:

- direct bot HTTP or websocket routes
- direct database access

## Commands

```bash
npm install
npm run dev
npm run build
npm run lint
npm run preview
npm run test:contracts
```

## Key Directories

- `src/pages` for route-level screens
- `src/components` for reusable UI blocks
- `src/api` for API and websocket helpers
- `src/store` for Zustand state
- `src/navigation` for workspace navigation and command palette

## UI Standard

The current UI direction is production DeFi:

- websocket-first live surfaces
- backend-only integration
- trading-terminal style density where appropriate
- responsive layouts across mobile, tablet, and desktop
- smaller, intentional surfaces instead of oversized marketing boxes

## Shared Product Patterns

- public pages should explain workflow, trust posture, and pricing before auth
- public navigation is route-based rather than anchor-based: Home, Research, Runtime, Market Intel, Security, and Pricing are separate journeys
- pre-auth public pages should favor editorial bands, thin separators, and row-based comparison over long one-page scrolls or stacked rounded cards
- auth screens should expose access state, security expectations, and next-step clarity
- workspace chrome should keep grouped navigation, command access, environment context, and operator identity visible
- operator pages should use control-room headers, compact status pills, and reusable terminal-style cards/grids
- the workspace shell uses sharper 8px surfaces, neutral dark panels, and restrained cyan/emerald/amber state color so data hierarchy stays stronger than decoration
- dashboard quick-launch and activity-tape surfaces should refresh softly and preserve visible data while active jobs update
- risky mutations should use consistent confirmation dialogs rather than browser-native confirms
- inline notices and toast feedback should use human operator language with next-step guidance
- setup flows such as backtest launch and runtime creation should show summary context before submission
- live-state semantics should stay consistent:
  - healthy/positive: emerald
  - live/realtime: cyan
  - warning/recovering: amber
  - negative/failure: rose/red

## Supporting Docs

- [Frontend Architecture Notes](/home/chris/workspace/dydx-trading-bot/frontend/docs/architecture/README.md)
- [Fintech UI Standards](/home/chris/workspace/dydx-trading-bot/frontend/docs/architecture/FINTECH_UI_STANDARDS.md)
- [Troubleshooting](/home/chris/workspace/dydx-trading-bot/frontend/docs/guides/TROUBLESHOOTING.md)
- [Root Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
