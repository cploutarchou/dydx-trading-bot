# 04 — Code Quality Audit

Static audit of `src/` — 178 TS/TSX files, **62,294 LOC** (60,929 excl. tests), avg ~350 lines/file. `useEffect` ×143 (57 with cleanup closures). Every claim below was measured, not estimated.

## Metrics dashboard

| Check | Result | Verdict |
|---|---|---|
| `any` / `as any` / `<any>` | **0** | Excellent |
| `@ts-ignore` / `@ts-expect-error` / `@ts-nocheck` | **0** | Excellent |
| `eslint-disable` comments | **0** (and `lint --max-warnings 0` passes) | Excellent |
| Non-null assertions | ~10 (e.g. `Codex.tsx:149,159`, `BacktestResultsEnhanced.tsx:181,270-276`) | Fine |
| `dangerouslySetInnerHTML` / `innerHTML` / `eval` / `new Function` | **0** | Excellent |
| TODO/FIXME/HACK/XXX | **0** | Unusual but true |
| Empty catch blocks | **0** (≈25 console-only catches, mostly justified localStorage best-effort) | Good |
| `console.*` statements | 111 across 29 files (api layers lead with 30) — no token/password **values** logged; WebSocketManager logs full WS payloads (`websocket.ts:241`, debug default true) | P3 prod noise |
| Index-as-key | 9 (mostly static lists/skeletons; `Backtests.tsx:1336,1350` data-driven) | P3 |
| AbortController usage | 0 (React Query owns most fetch lifecycles; manual WS effects have cleanup) | P3 |

## Hotspots (files > 800 lines)

| File | Lines | Class |
|---|---:|---|
| `src/api.ts` | 4,822 | God module: auth + session + refresh queue + ~208 endpoint methods |
| `src/pages/BacktestDetailsV2.tsx` | 3,241 | Page-sized monolith |
| `src/components/StrategyManager.tsx` | 2,971 | Operator surface monolith |
| `src/components/StrategyBuilder.tsx` | 2,214 | Only react-hook-form consumer |
| `src/pages/Backtests.tsx` | 2,153 | Hub page |
| `components/AdminAccessControlSettings.tsx` | 1,741 | Settings monolith |
| `src/api/hooks.ts` | 1,718 | 58 hooks (cohesive, acceptable) |
| BotManager 1,360 · BacktestComparator 1,316 · BacktestList 1,261 · Settings 1,156 · Dashboard 1,076 · BacktestRunner 1,039 | | |

Not P1s — the app works — but each is a P2/P3 maintainability drag that slows every future change.

## Duplication

- **Two HTTP stacks** with duplicated 401-refresh control flow: axios interceptor queue (`api.ts:1818-1952`) vs fetch retry (`enhancedClient.ts:114-143`). `src/api/client.ts` aliases the *fetch* client as `apiClient`; the app uses the *axios* default. `Backtests.tsx:18-19` imports both.
- **21 files** with manual `const [loading, setLoading] = useState(true)` + error state alongside 48 React-Query files — the migration stopped halfway.
- **Formatting scatter:** 65 local `formatX` helpers across ~40 files, `toFixed` ×172, `new Date` ×132, `Intl.NumberFormat` ×4; **date-fns installed with 0 imports**; a good `formatUsd/formatPct` exists in `features/codex/marketIntel.ts` but only Codex uses it.

## Dead code (verified zero importers)

- `pages/BacktestDetails.tsx` (562) — also the **only recharts consumer**, so the dependency is dead weight too.
- `pages/BotDashboard.tsx` (752), `pages/CRM.tsx` (663), `pages/IBPortal.tsx` (614) — superseded by `pages/crm/*`, `pages/ib/*`.
- `components/BacktestDetailsPage.tsx` (529), `components/BacktestProgress.tsx` (only imported by dead page), `hooks/useBacktestProgress.ts`.
- `src/dev/*` React-Buddy scaffolding + `@react-buddy/ide-toolbox` **in prod dependencies, 0 imports**.
- Shims kept intentionally: `api/client.ts`, `store/enhancedAuth.ts`.

**Total removable: ~3,650 lines + 5 dependencies.**

## Correctness findings

| ID | Finding | Evidence | Priority |
|---|---|---|---|
| FE-FN-01 | `localStorage.getItem('token')` — key never written anywhere; real key is `_dydx_access_token` (`api.ts:1972`). The live-progress WS built from it connects unauthenticated; page silently relies on the 8s HTTP fallback poll | `pages/Backtests.tsx:710`; WS builders `api.ts:4259-4265` | **P1** |
| FE-FN-02 | Duplicate `codex/market/overview` request fired twice on Market Intel mount (React Query dedup gap — two consumers, distinct query identity) | verified live in performance entries | P2 |
| FE-FN-03 | Backtest default window frozen at `2024-01-01→2024-03-31` (verified live in form + summary card) | `BacktestRunner.tsx:110-111` | P2 |
| FE-FN-04 | Financial number inputs unclamped client-side; `Number(formValues.x)` NaN-capable on emptied fields (server revalidation assumed but undocumented) | `StrategyBuilder.tsx:529-539`, `BotManager.tsx:1083-1105` | P2 |

## React & hook hygiene

- Effect cleanup discipline is genuinely good (verified `App.tsx:251-255`, `Dashboard.tsx:87-99,494-495`, `Header.tsx:17-18`, `CryptoBackground.tsx:846-867` 7/7 listeners removed, `BotManager.tsx:576-582`, `AdminCelery.tsx:224-229`).
- One clickable non-button element: `Sidebar.tsx:59` overlay div (jsx-a11y clean otherwise).
- StrictMode inverted (`main.tsx:15`: dev skips it) — reduces double-render protection exactly where devs iterate. P3.

## TypeScript & lint configuration

- `tsconfig.json`: strict ✅, include covers `src` fully (tests typechecked too). Missing hardening: `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` (P3).
- ESLint: flat config wraps legacy `.eslintrc.cjs` (both coexist — consolidate, P3). `.prettierrc` exists but prettier is not installed (P3). No husky/lint-staged.

## Dependencies

| Dependency | Status | Action |
|---|---|---|
| framer-motion | **0 imports** (animejs won) | remove |
| date-fns | **0 imports** | remove or adopt as THE date util (preferred) |
| @headlessui/react | **0 imports** | remove |
| @react-buddy/ide-toolbox | 0 runtime imports (dev plugin scaffolding) | move out of prod deps or remove with `src/dev` |
| recharts | only dead page imports | remove with dead code |
| vite, tailwindcss | listed in `dependencies` | move to devDependencies (P3) |
| react-hook-form | 1 file | either adopt for auth/operator forms or remove (P2 consistency) |

## Strengths worth protecting

Zero suppression comments; zero XSS sink primitives; zero empty catches; zero TODO debt; strict TS with full include; jsx-a11y active; single-flight token refresh with cooldown; trace IDs on requests; graceful degradation patterns (bot API down → inline operator messaging, verified live).
