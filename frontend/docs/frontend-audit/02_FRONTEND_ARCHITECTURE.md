# 02 — Frontend Architecture

All claims verified against source (2026-09-04). Line references are current HEAD.

## Stack

| Concern | Technology | Evidence |
|---|---|---|
| Framework | React 19.2.7 | `package.json` |
| Language | TypeScript 6.0.3, `strict`, `noUnusedLocals/Parameters`, `noFallthroughCasesInSwitch` | `tsconfig.json` |
| Build | Vite 8.0.16, `manualChunks` vendor splitting, chunkSizeWarningLimit 700 | `vite.config.ts` |
| Rendering | CSR only (no SSR/SSG); `React.lazy` code-splitting (7 lazy in `App.tsx`, 20 in `routeManifest.tsx`) | `src/App.tsx`, `src/app/routeManifest.tsx` |
| Routing | react-router-dom 7.17.0, flat routes + nested portal routers | `src/App.tsx:301`, `src/pages/crm/index.tsx`, `src/pages/ib/index.tsx` |
| State | Zustand 5 (auth `persist` key `auth-store-legacy` partialized to `user`; strategies; uiPreferences) | `src/store/auth.ts:336-339` |
| Server state | TanStack Query 5.101, 58 hooks, 5 cache tiers (realtime 1s/5s poll → historical 24h) | `src/api/hooks.ts`, `src/api/queryClient.ts` |
| Styling | Tailwind CSS 4.1.14 via `@import 'tailwindcss'` + **7,431-line hand-written `src/index.css`** with ~120 `:root` CSS variables; `tailwind.config.js` is vestigial (no `@config` reference) | `src/index.css`, `tailwind.config.js` |
| HTTP | Axios 1.17 (`src/api.ts`) **and** a parallel fetch client (`src/api/enhancedClient.ts`) | see "Dual API layer" |
| Charts | lightweight-charts 5.2 (`createTradingChart` theme factory); recharts 3.3 only imported by dead `pages/BacktestDetails.tsx` | `src/components/charts/lightweightTheme.ts` |
| Icons | lucide-react (90 imports) | grep |
| Forms | react-hook-form in exactly 1 file (`StrategyBuilder.tsx:4`); everything else manual useState | grep |
| Dates | Native `input[type=date]`, `new Date()` ×132, `toFixed` ×172; **date-fns installed, 0 imports** | grep |
| i18n | `src/i18n/useI18n.ts` — inline `t(en, el)` helper used by 3 components (~31 strings) | `src/i18n/` |
| Tests | Vitest 4.1.8 only; no jsdom/Testing Library/Playwright | `package.json` |
| Lint | ESLint 9 flat config wrapping legacy `.eslintrc.cjs`; jsx-a11y + react-hooks + import plugins; `--max-warnings 0` passes clean | `eslint.config.cjs` |
| WS | `WebSocketManager` (backoff+jitter, 30s heartbeat, message queue) + 4 endpoint builders | `src/api/websocket.ts`, `src/api.ts:4259-4283` |

## Portal system

- `src/app/portal.ts` — single source of truth. Resolution: URL prefix (`/crm/*`, `/ib-portal/*`, `/admin*`) → dev-only `?portal=` override (`localStorage['dev.portal.override']`) → `VITE_APP_PORTAL_TYPE` → hostname (`crm.*` / `ib.*`) → default client.
- `apps/client-portal`, `apps/backoffice`, `apps/ib-portal` and `packages/shared-*` are **1-line re-export shims** of `src/*`, not real workspace packages yet (documented intent in README).
- Route manifests (`src/app/routeManifest.tsx`): client 22 routes, backoffice 8, IB 3; global routes in `App.tsx` (public `/`, `/services/:slug`, `/pricing`, `/ico/*`, auth `/login`, `/register`, `/2fa-setup`, `/force-password`, `/unauthorized`, catchall → `/unauthorized`).

## Application area map

| Area | Surfaces | Notes |
|---|---|---|
| Public site | Landing, Pricing (519 ln), PublicServicePage ×4, ICO launchpad/docs/token-actions | Editorial-band style; route-based nav; SEO meta + sitemap refs in `index.html` |
| Auth | Login (282), Register (481, Turnstile), TwoFactorAuth (351), ForcePasswordChange (136), Unauthorized (34) | MFA challenge, privileged-MFA step-up, password rotation gates |
| Client workspace | Dashboard (1,076), Backtests hub (2,153), BacktestDetailsV2 (3,241), StrategyBuilder (2,214)/Library (781)/Manager (2,971), BotManager (1,360), Codex (537), News (180), ClientArea (408), Settings (1,156) | Core product flow: Research → Strategy → Backtest → Deploy → Monitor |
| Backoffice | AdminHub, AdminICO, AdminCelery (894), ClickHouseAnalytics, CRM suite (10 files, `src/pages/crm/`), access-control settings (1,741) | Role-gated to 13 BACKOFFICE_ROLES; privileged MFA enforced pre-route |
| IB portal | `src/pages/ib/` (9 files incl. IBTierRates 542) | ib/sub_ib roles; tokens+tier-rates admin-gated |
| ICO | whitelist submit/confirm/unsubscribe/withdraw + admin readiness | email-token capability links; no on-chain payment |

## Data & control flows (verified live where marked)

- **Session bootstrap:** `App.tsx` `bootstrapAuth` (12s timeout) → `initializeSession()` single-flight → `restoreSession()` (HttpOnly cookie refresh) → `getCurrentUser()` fallback probe. ✅ login→dashboard verified.
- **Token model:** HttpOnly cookie primary; JWT Bearer fallback mirrored to localStorage (`api.ts:1972`); refresh single-flight with queue + 10s cooldown (`api.ts:1818-1952`); window events `auth:session-expired` / `auth:refresh-warning`.
- **Backtest run:** BacktestRunner form → `api.runBacktest()` → navigate `/backtest/:runId` → `useBacktestProgress` (WS-first, 10s WS status requests, 8s HTTP recovery polling). Client-side validation of window/markets verified live (reversed dates blocked with inline error + toast).
- **Polling inventory:** AdminCelery 10s; Dashboard clocks 1s/15s freshness; Header clock 1s; BotManager refetch 30s; React Query `refetchInterval` 5s–5min across CRM/IB/dashboard surfaces; `websocket.ts:498` 1s auth watcher interval.
- **Role guard:** `ProtectedRoute` waits `sessionInitialized`, enforces auth → password rotation → privileged MFA → `allowedRoles`. ✅ client hitting `/admin` lands `/dashboard`; ✅ backend returns 403 independently.

## Architecture debt register

1. **Dual API layer (P2):** axios `api.ts` (4,822 lines, 208 methods, own refresh queue) vs fetch `enhancedClient.ts` (849 lines, ~40 methods, own 401 retry). `src/api/client.ts` exports the *fetch* client as `apiClient` while the app root uses the *axios* default — importing the wrong one silently changes auth behavior. `Backtests.tsx:18-19` imports both.
2. **Dead legacy cluster (P2):** `pages/BotDashboard.tsx` (752), `pages/CRM.tsx` (663), `pages/IBPortal.tsx` (614), `pages/BacktestDetails.tsx` (562) + `components/BacktestDetailsPage.tsx` (529) + `hooks/useBacktestProgress.ts` have zero importers — superseded by `pages/crm/*`, `pages/ib/*`, `BacktestDetailsV2`.
3. **God modules:** `api.ts` 4,822; `BacktestDetailsV2.tsx` 3,241; `StrategyManager.tsx` 2,971; `StrategyBuilder.tsx` 2,214; `Backtests.tsx` 2,153.
4. **Half-finished migration:** 48 files use React Query; 21 files still use manual `useState(true)` loading + `useEffect` fetch (`Settings.tsx:347`, `BacktestDetailsV2.tsx:516`, `BacktestList.tsx:355`, …).
5. **CSS architecture:** 7,431-line `index.css`, 41 hand-maintained `premium-*`/`operator-*`/`workspace-*` class families, ~737 selectors; vestigial `tailwind.config.js`; light-theme `[data-theme='light']` blocks (~5,600 lines effect) unreachable because `uiPreferences.ts:18 FORCE_DARK_THEME=true` and `ThemeToggle.tsx:9` disables the option (README contradicts this).
6. **StrictMode inverted:** `main.tsx:15` enables StrictMode only in production — backwards vs React convention; masks double-render bugs during development.
7. **Persistent typo route:** `/strategies/managet` kept as a permanent redirect (`routeManifest.tsx:90`).

## What is genuinely good

Zero `any`/`@ts-ignore`/`eslint-disable` in 62,294 LOC; disciplined effect cleanup (no uncleaned interval/listener found); single global ErrorBoundary + `unhandledrejection`/`error` handlers with toast store; trace headers (`src/api/trace.ts`); perf marks (`utils/perf.ts`, DEV-gated); code splitting with sane vendor chunks (build output: react-core 189KB, index 217KB, biggest page 111KB); encrypted structured build config (AES-256-GCM profiles → `import.meta.env` defines); per-portal build outputs.
