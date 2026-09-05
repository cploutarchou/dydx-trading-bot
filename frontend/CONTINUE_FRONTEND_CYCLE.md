# CONTINUE — Frontend audit cycle (updated 2026-09-06, after pass 14)

Cycle state: **FE-038 complete** (all 238 lint findings across 6 categories at zero,
every rule enforced), **FE-022 complete**, **FE-009 complete + live-verified**,
**FE-015 core complete** (single HTTP stack). Remaining work: two FE-015 sub-items.
All commits pushed through `1137a6a6`; both CI workflows green.

## 1. Environment startup (fresh terminal)

```bash
# Node (required for every frontend command)
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 24.19.0

# Infra (Postgres 5432, Valkey 6379, NATS, ClickHouse, MinIO) — only if rebooted
cd /home/chris/workspace/dydx-trading-bot && make infra-up

# Backend :8888 (DB_AUTO_MIGRATE applies migrations on boot)
cd /home/chris/workspace/dydx-trading-bot/backend && DB_AUTO_MIGRATE=true nohup go run ./cmd/server > /tmp/backend-server.log 2>&1 &
# health check: curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/health  → 200
# kill old instance first: pid=$(ss -tlnp | grep :8888 | grep -oP 'pid=\K[0-9]+' | head -1) && kill $pid

# Frontend dev :5173 (client portal)
cd /home/chris/workspace/dydx-trading-bot/frontend && npm run dev
```

Test user: `auditclient` / `audit.client@local.test`, password `AuditClient-2026!y`.

## 2. Remaining work

### A. FE-023 tail — migrate 3 files to React Query (also retires the enhancedClient facade)

`src/api/enhancedClient.ts` is now a thin axios-backed facade (public contracts
unchanged). Retire it by moving its last direct callers onto `src/api/hooks.ts`
React Query hooks:

1. **`src/components/BacktestList.tsx`** — manual `useState/useEffect` polling +
   `fetchAllRuns()` calling `api.listBacktests` + `enhancedApiClient.getBacktestStatus`.
   Model: `useBacktestProgress` in hooks.ts (websocket + polling fallback already
   exists). Keep the existing 4s-only-while-active poll semantics.
2. **`src/pages/BacktestDetailsV2.tsx`** — manual fetch effects for
   metadata/candles/positions/trades (with loaded-state cache guards). These map to
   query keys like `['backtests', 'detail', runId]` with the existing
   `detailSyncCursor` as a stale-time signal.
3. **`src/pages/Settings.tsx`** — `fetchSettingsData` useCallback loader (schema +
   form values); maps to a `['settings', 'schema']` query. `src/pages/settingsData.ts`
   already holds the loader.

After the three migrations: `grep -rn enhancedApiClient src/` should show only
`src/api/hooks.ts` (if anything) — then delete `src/api/enhancedClient.ts` +
`enhancedClient.test.ts`, and move the still-needed `getBacktestStatus` dedup logic
(covered by tests) into hooks.ts or api.ts. SyncHealthPanel + websocket.ts also
reference it — check whether they can use hooks/api directly.

### B. FE-015 tail — split the api.ts chunk (45.6KB gzipped-ish)

`src/api.ts` is ~4.8k lines and lands as one big chunk. Options (measure first with
`npm run build` + inspecting `dist/assets`):
- Route-lazy-load admin/backoffice-only endpoint groups by moving them to separate
  modules re-exported through the class (e.g. `api/analytics.ts`,
  `api/adminBackoffice.ts`) combined with dynamic `import()` at call sites, or
- `build.rollupOptions.output.manualChunks` to carve domain groups — verify the
  portal builds (`build:client`, `build:backoffice`, `build:ib`) each get smaller
  index chunks and nothing breaks tree-shaking of portal-gated routes.

## 3. Validation gate (per task — explicit exit codes, never pipe to tail)

```bash
npm run lint                                        # 0
./node_modules/.bin/tsc --noEmit -p tsconfig.json   # 0
npm test -- --run                                   # 25 files / 131 tests
npm run build                                       # 0
npx playwright test                                 # 10 specs — run with backend UP and also stopped (CI runs backend-free)
```

Commit per task, push, then confirm CI:
`gh run list --limit 2` → both `Bot Quality` and `Build Service Images` success.

## 4. Fix-pattern library (established in FE-038, reuse for any new lint findings)

1. Reset-state-on-change → render-time `if (x !== prevX) { setPrevX(x); setThing(...) }`
2. Derived display state → compute at consumption (`const display = cond ? a : b`)
3. Mount-fetch with sync `setLoading(true)` → `void Promise.resolve().then(() => load())`
4. Page clamps → derive `safePage` during render; use everywhere
5. Refs are never read/written during render — keep ref resets in effects
6. Load-bearing exceptions get documented `// eslint-disable-next-line` (precedents:
   useFocusOnVisibleError, StrategyManager runtime-status signature deps,
   CumulativePnlChart/BacktestLightweightChart creation effects)

## 5. Gotchas

- Shell cwd resets to `frontend/` after every command; `cd` absolutely each time.
- `git status --short` before staging — never stage `.v2c/`, `.video_agent/`, or
  `docs/scree*` PNGs (root .gitignore policy); don't touch backend/ unless intended.
- e2e must pass backend-FREE (that's how CI runs it) — intercept API routes in specs.
- Money strings go through `src/utils/format.ts`; lint runs with `--max-warnings 0`
  and ALL react-hooks/jsx-a11y/import rules are now enforced at error level.
