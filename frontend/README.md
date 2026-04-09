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

## Supporting Docs

- [Frontend Architecture Notes](/home/chris/workspace/dydx-trading-bot/frontend/docs/architecture/README.md)
- [Fintech UI Standards](/home/chris/workspace/dydx-trading-bot/frontend/docs/architecture/FINTECH_UI_STANDARDS.md)
- [Troubleshooting](/home/chris/workspace/dydx-trading-bot/frontend/docs/guides/TROUBLESHOOTING.md)
- [Root Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
