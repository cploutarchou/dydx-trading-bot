# 15 — Performance Audit

Environment note: local dev server (unbundled) + local backend — absolute timings are not production-representative; structural findings and bundle inventory are. No Lighthouse run (headless env); Web-Vitals instrumentation absent in app (see Observability).

## Measured (dev, localhost)

| Metric | Value | Context |
|---|---|---|
| Market Intel DCL / Load | 342ms / 345ms | unbundled dev modules; healthy |
| API call latency (local backend) | 3–14ms typical | includes React Query bootstrap calls |
| Data-fetch count on Market Intel mount | 10 requests | 1 duplicate (below) |
| Dashboard initial visible content | under ~2s | no skeleton flash observed for empty states |

## Bundle inventory (production build, 2026-09-04)

Largest chunks: `index-*.js` **217KB** (57.7 gzip) · `react-core` 189KB (59.7) · `vendor-lightweight-charts` 166KB (55.0, lazy) · `Settings` 111KB · `BacktestDetailsV2` 102KB · `Backtests` 99.7KB · `StrategyManager` 67.9KB · vendor utils/router/query/ui 29–42KB each. Pages are lazy-loaded and split correctly; **initial JS ≈ react-core + router + utils + ui + query-core + index ≈ 555KB raw / ~180KB gzip** — acceptable, with three clear trims:

1. **`index-*.js` 217KB monolith** — audit eager imports in `App.tsx`/shell (Landing/Login/Register/Pricing are eager by design); move Landing-only deps (CryptoBackground + animejs timer, 15KB) behind lazy; check `enhancedClient`+`api.ts` both loading eagerly (dual-stack cost).
2. **Unused prod deps** (framer-motion, @headlessui, @react-buddy/ide-toolbox, date-fns; recharts only feeds a dead page) — remove; shrinks install + attack surface even where tree-shaking saves bytes.
3. **Fonts**: no external font requests (good); confirm self-hosted subsets stay ≤2 weights per family (Sora+Manrope+JetBrains all present).

## Network findings

| ID | Finding | Evidence | Priority |
|---|---|---|---|
| NP-1 | Duplicate `/codex/market/overview?network=1&limit=6` on Market Intel mount (two consumers, distinct query identities; doubled 503s observed) | live performance entries | P2 |
| NP-2 | Polling inventory is broad but disciplined (intervals 5s–5min, mostly `refetchIntervalInBackground:false`; BacktestList polls only while PENDING/RUNNING — good); `websocket.ts:498` runs a 1s interval forever (auth watcher) — replace with event-driven check | `src/api/websocket.ts:498` | P3 |
| NP-3 | No request cancellation on unmount for the 11 manual-fetch components (React Query covers the rest) | code | P3 |
| NP-4 | No `staleTime` differentiation abuse found; cache tiers sane (1s realtime → 24h historical) | `queryClient.ts` | — |

## Rendering findings

- Re-render hygiene: memoization sparse but data flows are query-driven; no pathological render loop observed live (clock intervals are isolated components).
- CLS risk: chart containers without min-height before data (U4.1 fixes); KPI cards stable.
- Long tasks: none measurable in dev for audited pages; CryptoBackground canvas runs rAF with intensity presets + reduced-motion fallback + print CSS off (verified by its test suite) — keep an eye on low-end mobile (intensity default).
- StrictMode inversion (prod-only) hides double-render costs in dev profiling — flip it before optimizing (P3).

## Priorities

| Action | Est | Impact |
|---|---|---|
| Dedupe NP-1 query key | S | −1 dup call + faster intel paint |
| Dep cleanup (5 deps) | S | smaller graph, faster CI |
| `index-*.js` eager-import audit + Landing lazy-fication | M | −40–60KB initial gzip-est |
| WS auth watcher event-driven | S | removes perpetual 1s timer |
| Chart min-heights + tabular-nums | XS | CLS/visual |
| Add Web-Vitals reporting (see 18, observability) before micro-tuning | S | real-user baselines |
