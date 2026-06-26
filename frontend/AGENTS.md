# AGENTS.md

## Mission-critical context
- Frontend is React 19 + TypeScript + Vite, now a multi-portal workspace (`client`, `backoffice`, `ib`) selected by `VITE_APP_PORTAL_TYPE` (`src/app/portal.ts`, `src/App.tsx`).
- Backend base URL is `VITE_API_BASE_URL` (`VITE_API_URL` fallback), default `http://localhost:8888` when unset (`src/api/origin.ts`, `vite.config.ts`).
- Service boundary: this UI does not call dYdX directly; backend orchestrates auth, backtests, bots, Valkey/Redis-compatible cache flows, and strategy APIs.
- Root app wiring is in `src/App.tsx`: `QueryProvider` + global `ErrorBoundary` + `ToastContainer` + route guards.

## Start-of-task checklist

1. Read `../.github/copilot-instructions.md`
2. Read `.github/copilot-instructions.md`
3. Read `README.md` (portal split, commands, env/domain mapping)
4. Prefer `.github/agents/senior-react-defi-product.agent.md` for frontend implementation work

## Actual architecture in this repo (important)
- There are two API access styles in production code:
  - `src/api.ts`: Axios client with auth token persistence, refresh-on-401, and many typed endpoints.
  - `src/api/enhancedClient.ts`: wrapper used by React Query hooks; many methods use `fetchWithAuth` + cookie-aware 401 retry.
- React Query layer lives in `src/api/hooks.ts` + `src/api/queryClient.ts` (`queryKeys`, cache tiers, invalidation helpers).
- Auth state used by routing is `src/store/auth.ts` (legacy store), not `src/store/enhancedAuth.ts`.
- Many major UI screens still fetch directly with `useState/useEffect` (for example `src/components/BacktestList.tsx`, `src/components/BotManager.tsx`); do not assume hooks are universal.
- Backtest progress has two patterns: `src/components/BacktestProgress.tsx` uses polling via `useBacktestProgress` in `src/api/hooks.ts`, while legacy websocket hook logic remains in `src/hooks/useBacktestProgress.ts`.

## Latest frontend context (2026-05)

- `src/pages/Backtests.tsx` now provides a dashboard-first workflow (`dashboard` / `new` / `runs`) with strategy leaderboard + active-run quick access.
- Active backtest cards now poll per-run status and show normalized runtime progress and freshness (`updated ... ago`) cues.
- Freshness severity is visualized with tone + border escalation in active run cards (fresh, delayed, stale).
- `src/components/StrategyManager.tsx` is a major operator surface with heartbeat-aware runtime status, stale/delayed indicators, and runtime summary cards.
- Route registration is portal-gated in `src/App.tsx`: client/backoffice/IB routes mount from `getCurrentPortalType()` and are role-checked with `ProtectedRoute` + `allowedRoles`.

## Key data and control flows
- Login/session bootstrap: `useAuthStore.initializeSession()` in `src/App.tsx` -> `api.restoreSession()` -> `api.getCurrentUser()`.
- Protected route check in `src/App.tsx` waits for `sessionInitialized`, then enforces `isAuthenticated()` + `user`, password rotation (`/force-password`), privileged MFA setup, and `allowedRoles`.
- Backtest run flow: `BacktestRunner` posts `api.runBacktest()` then navigates to `/backtest/:runId` (`src/components/BacktestRunner.tsx`).
- Backtest list polling: `BacktestList` polls every 4s only while runs are `PENDING/RUNNING` (`src/components/BacktestList.tsx`).
- Realtime progress in current UI uses `useBacktestProgress` in `src/api/hooks.ts` (websocket updates + 5s polling fallback/recovery); legacy websocket-only hook remains in `src/hooks/useBacktestProgress.ts`.

## Response-shape and typing gotchas
- Backend envelope is usually `{ success, message, data, timestamp }`; components often need nested extraction (example: `response.data?.backtests`).
- Shapes are inconsistent (`{ count, data }` vs envelope with `data.backtests`); check callers before refactoring.
- `src/api.ts` normalizes some strategy fields (`resolution`/`candle_resolution`) and token storage (localStorage + cookie).

## UI and debugging conventions you should follow
- Dark theme is the baseline: `bg-slate-900/800/700`, `text-white`, and financial colors (`text-green-400` profit, `text-red-400` loss).
- Existing codebase uses emoji-prefixed logs (`🔐`, `📊`, `🔌`, `❌`, `🔧`) for quick console filtering.
- Error UX pattern is inline red cards for component errors plus global toasts from `src/components/ErrorBoundary.tsx`.

## Developer workflows (verified from repo files)
- Local dev: `npm run dev` (default client portal on `5173`) plus `npm run dev:client`, `npm run dev:backoffice` (`5174`), and `npm run dev:ib` (`5175`) (`package.json`).
- Build targets now include portal-specific outputs: `npm run build:client`, `npm run build:backoffice`, `npm run build:ib` (`package.json`).
- Validation commands include `npm run test:contracts` and responsive QA scripts (`npm run qa:screenshots:plan|capture|sync`) (`package.json`, `scripts/`).
- API proxy in dev server maps `/api` and `/ws` to `VITE_API_BASE_URL || VITE_API_URL` (`vite.config.ts`).
- Root Makefile workflows are documented in `README.md` (`make infra-up`, `make stack-up-dev`, `make stack-down`); expected local service ports are backend `8888`, PostgreSQL `5432`, Valkey `6379`, NATS `4222/8222`, ClickHouse `8123`, and MinIO `9010/9011`.
- TypeScript is strict (`strict`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`) in `tsconfig.json`.

## High-value files to read before major edits
- `src/App.tsx`, `src/api.ts`, `src/api/enhancedClient.ts`, `src/api/hooks.ts`, `src/api/queryClient.ts`
- `src/app/portal.ts`, `src/auth/roles.ts`, `src/api/origin.ts`
- `src/store/auth.ts`, `src/components/BacktestRunner.tsx`, `src/components/BacktestList.tsx`, `src/components/BotManager.tsx`, `src/components/BacktestProgress.tsx`
- `.github/copilot-instructions.md`, `README.md` (project conventions, portal architecture, workflows)
