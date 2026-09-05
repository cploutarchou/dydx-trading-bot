# CONTINUE — Frontend audit cycle (paused 2026-09-05)

Pause point: mid **FE-038** (lint debt), last category `react-hooks/set-state-in-effect`
(31 findings left in 27 files). Everything committed so far is green
(lint 0 · tsc 0 · 25 files/133 tests · build 0). Nothing is stranded uncommitted.

## 1. Environment startup (fresh terminal)

```bash
# Node (required for every frontend command)
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 24.19.0

# Infra (Postgres 5432, Valkey 6379, NATS, ClickHouse, MinIO) — only if rebooted
cd /home/chris/workspace/dydx-trading-bot && make infra-up

# Backend :8888 (restart after ANY backend code change or new migration)
cd /home/chris/workspace/dydx-trading-bot/backend && DB_AUTO_MIGRATE=true nohup go run ./cmd/server > /tmp/backend-server.log 2>&1 &
# wait for: curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8888/api/v1/auth/forgot-password -H "Content-Type: application/json" -d '{"email":"x@y.z"}'  → 200
# To kill the old one first: pid=$(ss -tlnp | grep :8888 | grep -oP 'pid=\K[0-9]+' | head -1) && kill $pid

# Frontend dev :5173 (client portal)
cd /home/chris/workspace/dydx-trading-bot/frontend && npm run dev
```

## 2. Where things stand (commits on master, not yet pushed)

| Commit | What |
|---|---|
| `1b46cedc` | FE-009 backend — password reset endpoints + token repo + 6 tests |
| `151d8d81` | FE-009 frontend — screens/routes/e2e |
| `35b8a5e2` | fix: NULL full_name/avatar scan (found during live verify) |
| `3a3e1db9` | docs: FE-009 complete |
| `1f0e9662` | FE-038 — import-naming (24) + jsx-a11y interaction (14) → 0, rules ON |
| `b0fb2b41` | FE-038 — react-hooks compiler rules (15) → 0, rules ON (+ `src/hooks/useNow.ts`) |
| `a4f5724a` | FE-038 — exhaustive-deps (36) → 0, rule ON |
| `6e854e9d` | FE-038 partial — set-state-in-effect 55 → 31 (paused mid-category) |

**FE-009 is ✅ complete and live-verified** (forgot → cooldown → token row → reset →
replay rejected → new password logs in). Test user `auditclient` /
`audit.client@local.test`, current password after live test: `AuditClient-2026!y`.

## 3. Resume task A — finish FE-038 set-state-in-effect (31 findings / 27 files)

Rule still carved out in `eslint.config.cjs` (last `'off'` entry). Get the live list:

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 24.19.0
cd /home/chris/workspace/dydx-trading-bot/frontend
./node_modules/.bin/eslint src --rule '{"react-hooks/set-state-in-effect":"error"}' --format json 2>/dev/null | node -e "
const r=JSON.parse(require('fs').readFileSync(0,'utf8'));
const byFile={};
for(const f of r){ for(const m of f.messages){ if(m.ruleId==='react-hooks/set-state-in-effect'){ const fp=f.filePath.replace(process.cwd()+'/',''); (byFile[fp]=byFile[fp]||[]).push(m.line) } } }
Object.entries(byFile).sort().forEach(([k,v])=>console.log(v.length, k, '@', v.join(',')));
console.log('REMAINING:', Object.values(byFile).flat().length)"
```

Files remaining (as of pause): AIBacktestExplainer, AIRuntimeDigest,
AIStrategyAdvisor, ArbitrageRuntimeSettings, BacktestLightweightChart,
BacktestList (×2), BacktestResultsEnhanced (×2), BacktestRunner, BotManager,
CumulativePnlChart, DYDXKeyManager, MailgunSettings, MainLayout (×2),
MotionReveal, ProfileSettings, RegistrationDisabledLoginGate, StrategyLibrary,
StrategyManager (×2), TelegramScopeSettingsPanel, TurnstileWidget,
WorkspaceCommandPalette, AdminCelery, AdminICO, Backtests, ResetPassword,
CRMCommissions, IBNetwork.

### Established fix patterns (reuse these — see commit 6e854e9d for examples)

1. **"reset state when X changes"** → render-time adjust (sanctioned React pattern):
   ```tsx
   const [prevX, setPrevX] = useState(x);
   if (x !== prevX) { setPrevX(x); setThing(initialValue); }
   ```
2. **"clear/validate derived state"** → derive at consumption instead:
   `const effective = isActive ? thing : null;` and hide stale values at render.
3. **mount-fetch effects flagged for the loader's sync `setLoading(true)`** →
   `void Promise.resolve().then(() => loadThing());` inside the effect.
4. **page-index clamps** → compute `safePage` during render, use everywhere, drop the sync effect.
5. **refs may NOT be read/written during render** — keep ref resets in a dedicated effect.
6. When a pattern is genuinely load-bearing (loop risk, pass-through contract),
   keep it with a documented `// eslint-disable-next-line react-hooks/...` (precedents:
   `src/hooks/useFocusOnVisibleError.ts`, StrategyManager runtime-status sync,
   CumulativePnlChart creation effect).

When the count hits 0: remove the `react-hooks/set-state-in-effect: 'off'` carve-out
(and the now-obsolete debt block) from `eslint.config.cjs`, then update the FE-038
table in `docs/frontend-audit/19_PRIORITY_BACKLOG.md`.

## 4. Validation gate (run per task, check exit codes — never pipe to tail)

```bash
npm run lint          # LINT=0
./node_modules/.bin/tsc --noEmit -p tsconfig.json   # TS=0
npm test -- --run     # TEST=0 (25 files / 133 tests)
npm run build         # BUILD=0
npx playwright test   # only when auth/routing/markup changed (8 specs)
```

## 5. Remaining cycle after FE-038

1. **FE-022 tail** — adopt `src/utils/format.ts` (`formatUsd`, `formatUsdFixed`,
   `formatSignedUsd(Compact)`, `formatPct`, `formatCount`) across remaining ~50 local
   helper sites (`grep -rn "toFixed(2)\|toLocaleString" src/components src/pages`).
2. **FE-015 (L)** — dual API stack consolidation: port `src/api/enhancedClient.ts`
   (~40 fetch methods) onto the axios client in `src/api.ts`, delete enhancedClient,
   migrate FE-023 tail files (BacktestList, BacktestDetailsV2, Settings) to React
   Query, pursue the api.ts 45.6KB chunk split.
3. **Final** — update backlog statuses, push master via SSH
   (`git push origin master`), watch both CI workflows green
   (`Bot Quality` + `Build Service Images`).

## 6. Gotchas learned the hard way

- Shell cwd resets to `frontend/` after every command; always `cd` absolutely.
- Never stage blindly: `git status --short` first (user's own edits live in backend/;
  `.v2c/`, `.video_agent/`, and `docs/scree*` PNGs must NOT be committed).
- Validate with explicit exit codes; piping lint/test output through `tail` masks failures.
- Multi-directory codemods: re-run `git status` before `git add` (a pass-1 lesson).
- Local backend `go run` holds port 8888 via a cache binary — kill by pid from `ss -tlnp`.
