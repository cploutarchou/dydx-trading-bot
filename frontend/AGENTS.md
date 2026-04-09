# AGENTS.md

## Mission-critical context
- Frontend is React 19 + TypeScript + Vite, talking to backend at `VITE_API_URL` (default `http://localhost:8888`) via `/api/v1/*` endpoints (`src/api.ts`, `vite.config.ts`).
- Service boundary: this UI does not call dYdX directly; backend orchestrates auth, backtests, bots, Redis, and strategy APIs.
- Root app wiring is in `src/App.tsx`: `QueryProvider` + global `ErrorBoundary` + `ToastContainer` + route guards.

## Start-of-task checklist

1. Read `../.github/copilot-instructions.md`
2. Read `.github/copilot-instructions.md`
3. Read `.github/CUSTOMIZATION_INDEX.md`
4. Prefer `.github/agents/senior-react-defi-product.agent.md` for frontend implementation work

## Actual architecture in this repo (important)
- There are two API access styles in production code:
  - `src/api.ts`: Axios client with auth token persistence, refresh-on-401, and many typed endpoints.
  - `src/api/enhancedClient.ts`: wrapper used by React Query hooks; many methods use `fetch` and include mock fallbacks on error.
- React Query layer lives in `src/api/hooks.ts` + `src/api/queryClient.ts` (`queryKeys`, cache tiers, invalidation helpers).
- Auth state used by routing is `src/store/auth.ts` (legacy store), not `src/store/enhancedAuth.ts`.
- Many major UI screens still fetch directly with `useState/useEffect` (for example `src/components/BacktestList.tsx`, `src/components/BotManager.tsx`). Do not assume hooks are universally adopted.
- Backtest progress has two patterns: current UI component `src/components/BacktestProgress.tsx` uses polling via `useBacktestProgress` in `src/api/hooks.ts`, while legacy websocket hook logic remains in `src/hooks/useBacktestProgress.ts`.

## Key data and control flows
- Login/session bootstrap: `useAuthStore.initializeSession()` in `src/App.tsx` -> `api.restoreSession()` -> `api.getCurrentUser()`.
- Protected route check currently requires both `isAuthenticated()` and `user` (`src/App.tsx`).
- Backtest run flow: `BacktestRunner` posts `api.runBacktest()` then navigates to `/backtest/:runId` (`src/components/BacktestRunner.tsx`).
- Backtest list polling: `BacktestList` polls every 4s only while runs are `PENDING/RUNNING` (`src/components/BacktestList.tsx`).
- Realtime progress in current UI polls backtest status every 2s via `useBacktestProgress` in `src/api/hooks.ts`; websocket support still exists through `api.connectBacktestSocket(runId, token)` and `src/hooks/useBacktestProgress.ts`.

## Response-shape and typing gotchas
- Backend envelope is usually `{ success, message, data, timestamp }`; components often need nested extraction (example: `response.data?.backtests`).
- Shapes are inconsistent across files (`{ count, data }` vs envelope with `data.backtests`); check the caller before refactoring.
- `src/api.ts` normalizes some strategy fields (`resolution`/`candle_resolution`) and token storage (localStorage + cookie).

## UI and debugging conventions you should follow
- Dark theme is the baseline: `bg-slate-900/800/700`, `text-white`, and financial colors (`text-green-400` profit, `text-red-400` loss).
- Existing codebase uses emoji-prefixed logs (`🔐`, `📊`, `🔌`, `❌`, `🔧`) for quick console filtering.
- Error UX pattern is inline red cards for component errors plus global toasts from `src/components/ErrorBoundary.tsx`.

## Developer workflows (verified from repo files)
- Local dev: `npm run dev` (Vite on `5173`), build: `npm run build`, preview: `npm run preview`, lint: `npm run lint` (`package.json`).
- API proxy in dev server maps `/api` to `VITE_API_URL` (`vite.config.ts`).
- Root Makefile workflows are documented in `README.md` (`make infra-up`, `make stack-up-dev`, `make stack-down`); expected local service ports are backend `8888`, Postgres `5432`, Redis `6379`.
- TypeScript is strict (`strict`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`) in `tsconfig.json`.

## High-value files to read before major edits
- `src/App.tsx`, `src/api.ts`, `src/api/enhancedClient.ts`, `src/api/hooks.ts`, `src/api/queryClient.ts`
- `src/store/auth.ts`, `src/components/BacktestRunner.tsx`, `src/components/BacktestList.tsx`, `src/components/BotManager.tsx`, `src/components/BacktestProgress.tsx`
- `.github/copilot-instructions.md` (project conventions and intended patterns)
