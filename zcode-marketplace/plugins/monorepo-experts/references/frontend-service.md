# Service Profile — frontend/ (React dashboard)

Read before any change under `frontend/`.

## Scope and responsibility

Operator dashboard (dev :5173): strategies, backtests (dashboard/new/runs +
active-run quick access), live positions/market data, settings, auth flows
(MFA login, password-change redirect), CRM/portal surfaces.

## Stack

React 19, TypeScript 6, Vite 8, TanStack Query v5, Zustand 5, Tailwind CSS 4,
Recharts 3, Axios 1, React Router 7, ESLint 9 + Vitest (contract tests).

## Entry points

- `frontend/src/main.tsx` (Vite app), `src/App.tsx` routing via `src/app/routeManifest.tsx`
- API client: `frontend/src/api.ts` (token handling, interceptors) + `src/api/hooks.ts` (query hooks)

## Important files

- `src/pages/Backtests.tsx`, `src/components/BacktestList.tsx` — backtest UX + polling
- `src/components/StrategyManager.tsx` — runtime heartbeat/status UX
- `vite.config.ts` — startup loads structured config; honors `APP_RUN_CONFIG_FILE` (hermetic CI uses `.ci-run.json`)
- `src/api/contractGuards.test.ts` — contract tests (`npm run test:contracts`)

## Dependencies and interfaces

- Inbound: browser only. Outbound: backend :8888 exclusively (never bot :8889).
- Multi-portal behavior keyed by `VITE_APP_PORTAL_TYPE`; routing guardrails
  documented in `.github/skills/portal-routing-guardrails/SKILL.md`.

## Local development and validation

```
cd frontend
npm run dev
npm run lint          # eslint --max-warnings 0 (zero-warning policy)
npm run typecheck
npm run test:contracts
npm run build
```

## Testing strategy

Vitest contract guards against the API layer; typecheck is strict. Visual/UX
conventions live in `frontend/docs/architecture/FINTECH_UI_STANDARDS.md`.

## Deployment

Static build (`dist/`) shipped in the frontend image (root
`make images-build`); served behind backend origin.

## Security and reliability concerns

- Auth tokens only via the api client interceptors; never log tokens.
- Password-change flow must handle backend `password_change_required` 403s.
- No direct exchange/bot connections from the browser.

## Generated/protected files

`dist/`, `node_modules/`, `coverage/`.

## Common failure modes

Bypassing `src/api.ts` for ad-hoc fetches (loses interceptors/auth);
letting warnings creep above zero (lint gate); stale polling after
unmount; breaking portal routing invariants.

## Cross-service coordination

Contract tests pin backend response shapes; update them together with
backend route changes. Status/progress fields come pre-normalized from the
backend — prefer the canonical field names.

## Evidence sources

`frontend/package.json`, `frontend/README.md`, `frontend/AGENTS.md`,
`frontend/docs/architecture/README.md`, `frontend/.github/` customization
files.
