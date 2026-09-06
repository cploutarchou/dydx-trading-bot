# Frontend audit cycle — COMPLETE (2026-09-06, pass 16)

**The 38-item audit backlog is fully green.** All work pushed; both CI
workflows green through the final commit. Scoreboard: ~39 ✅ / 0 🟡 / 0 ⬜,
plus one optional perf item re-filed below.

## Final state

- **FE-038**: all 238 lint findings across 6 categories at zero; every rule
  enforced at error level (no carve-outs).
- **FE-022**: money formatting centralized in `src/utils/format.ts`.
- **FE-009**: self-serve password reset, live-verified end-to-end.
- **FE-015**: single HTTP stack — `src/api.ts` axios client with one
  interceptor chain (cookie auth, trace, 401-refresh); the fetch-era
  `enhancedClient` facade is deleted, its endpoint surface is
  `src/api/botApi.ts`, auth/session calls go direct to `api.ts`.
- **FE-023**: React Query everywhere it belongs — Settings, BacktestList,
  BacktestDetailsV2, plus the earlier 5 surfaces. SyncHealthPanel stays
  manual BY DESIGN (adaptive 10s→60s backoff).

## PERF-1: closed by measurement (2026-09-06)

Per-portal endpoint modules were investigated to a decision with two data
points: a manualChunks carve costs **+16KB gzip** first load (shared helpers
hoisted eager), and stripping all 48 admin-only methods from the class
before building caps the extraction win at **−1.5KB gzip** (10.3KB raw) —
gzip flattens the repetitive axios/try-catch bodies. Realizing that ceiling
means re-plumbing the 7.3KB auth/interceptor core (the FE-002/003 P1
security code) plus ~20 call-site migrations. Negative ROI; closed. Reopen
only if api.ts grows an order of magnitude or portals diverge further.

**Nothing else remains — the audit cycle is 100% closed:** every item is
either shipped or rejected-on-data.

## Environment (for future work)

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 24.19.0
cd /home/chris/workspace/dydx-trading-bot && make infra-up          # if rebooted
# backend:  cd backend && DB_AUTO_MIGRATE=true nohup go run ./cmd/server > /tmp/backend-server.log 2>&1 &
# frontend: cd frontend && npm run dev                               # :5173
```

Validation gate: `npm run lint` · `tsc --noEmit` · `npm test -- --run` ·
`npm run build` · `npx playwright test` (**backend-FREE — that's CI's mode**).
For UX surfaces, add a throwaway live spec in `e2e/`, run against the real
backend, DELETE it before committing.

## Lessons worth keeping

- A vite dev server that outlives backend restarts serves a dead proxy —
  restart `npm run dev` when browser requests 404 through :5173.
- Live verification catches what lint/tests/backend-free e2e can't: the
  useAIProviderAvailability render loop shipped green through the whole
  automated gate and only surfaced on a real page render.
- Money strings go through `src/utils/format.ts`; render-time state
  adjustment is the house pattern for reset-on-change (see pass 11-12 notes
  in 19_PRIORITY_BACKLOG.md).
