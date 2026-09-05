# CONTINUE — Frontend audit cycle (updated 2026-09-06, after pass 15)

Cycle state: **FE-038 complete** (238 lint findings at zero, enforced),
**FE-022 complete**, **FE-009 complete + live-verified**, **FE-015 nearly
done** (single HTTP stack; enhancedClient deleted → `src/api/botApi.ts`;
Settings + BacktestList on React Query). Remaining: ONE file —
BacktestDetailsV2 → React Query — plus the deferred per-portal endpoint-module
refactor. All commits pushed through `cc7231cc`; both CI workflows green.

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

### A. FE-023 tail — ONE file left: `src/pages/BacktestDetailsV2.tsx`

Manual fetch effects for metadata/candles/positions/trades (with loaded-state
cache guards keyed on runId + detailSyncCursor). Map to query keys like
`['backtests', 'detail', runId]`; the existing detailSyncCursor (from the WS
progress hook) works as an invalidation signal. Model after the Settings
migration (900e4d41) and BacktestList migration (d848f2aa):
- pure queryFn (no setState), staleTime to preserve cache-guard semantics,
  render-time adjust to seed any local draft state,
  `api.getBacktest` / `botApi.getBacktestStatus` calls stay as-is.
- Verify live: the local DB has 0 backtest_runs — a detail URL like
  /backtest/nonexistent exercises the fallback shell (no crash) — and run the
  backend-free e2e suite (CI's mode).

### B. FE-015 deferred: per-portal endpoint modules (deliberately deferred)

The api.ts chunk split was ATTEMPTED AND MEASURED (2026-09-06) and REJECTED:
a manualChunks 'api-client' rule for src/api.ts hoists shared helper modules
eager, growing first-load gzip 45.2 → 61.1 KB — cache-stability is not worth
+16KB on every cold visit. The real fix (deferred): move admin/backoffice-only
endpoint groups out of the monolithic ApiClient class into per-portal modules
so unused class methods tree-shake (class methods never tree-shake), then
re-measure all three portal builds.

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
