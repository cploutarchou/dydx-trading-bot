# 22 — Evidence & Screenshots

## Environment snapshot (all claims reproducible)

| Item | Value |
|---|---|
| Date | 2026-09-04 |
| Stack | client portal `http://localhost:5173`, backoffice `http://localhost:5174`, Go backend `:8888` (healthy), infra via `make infra-up` (Postgres/Valkey/NATS/ClickHouse/MinIO healthy), bot API `:8889` **down** (startup-migration exit) |
| Accounts | bootstrap `admin` (env-provisioned, local throwaway password); `auditclient` (registered via API, local throwaway) |
| Browser | in-app Chromium, viewports 1440×900, 375×812, 320×690 |

## Verification gates (commands + results)

```
npm run lint            → pass (0 warnings, --max-warnings 0)
npm run typecheck       → pass
npm run test:contracts  → 8/8 pass (0.23s)
npm run build           → pass (661ms; chunks listed in 15_PERFORMANCE_AUDIT)
curl :8888/health       → {"status":"healthy","database.healthy":true,"bot_api.reachable":false}
```

## Live behavioral evidence (key items)

| Claim | How verified |
|---|---|
| Login happy path client→`/dashboard`, admin→`/admin` | browser navigation + URL assertions |
| Wrong-credentials UX: generic inline `alert`, no enumeration | DOM snapshot of `/login` after failed submit |
| Client-role blocked from admin surfaces | `/admin` → lands `/dashboard`; API probe with client token → **403** `insufficient_permissions` on `/api/v1/admin/users` and `PUT /api/v1/settings` |
| Backtest date validation fires (reversed range) | second-click DOM check found inline error + toast (first click during re-render was swallowed — see FE-FN-05) |
| Bot create form: mnemonic masked | DOM query → `type:"password"`; all other inputs `hasLabel:false` (FE-006 evidence) |
| Double-submit protection on money forms | code + rendered `disabled` attr + pending labels (BacktestRunner.tsx:1028-1036, BotManager.tsx:1143-1150) |
| Bots desk surfaces raw axios error string | DOM snapshot: `"Request failed with status code 502"` in Arbitrage panel |
| AdminHub "Open Settings" dead link | navigation to `/settings` on 5174 → redirected `/dashboard` |
| Duplicate codex fetch | `performance.getEntriesByType('resource')` → `/api/v1/codex/market/overview?network=1&limit=6` ×2 |
| No horizontal overflow at 320/375 | `scrollWidth === clientWidth` measured on `/dashboard` (375) and `/backtests/new` (320) |
| Theme combobox renders disabled Light option | DOM snapshot (header, every authed page) |
| Bot-API-down degradation (markets picker) | DOM snapshot: disabled "First 5"/"Clear" + explicit reason paragraph |
| run.json pool defect | backend startup log `Failed to initialize database: invalid config: MaxIdleConns cannot exceed MaxOpenConns` (×2); bot API warning `DB_MAX_CONNECTIONS (100) is lower than DB_POOL_SIZE (105)` |

## Visual review captures (this session)

Rendered and machine-reviewed (layout/typography/defect analysis in 10_UI_AUDIT): landing 1440, dashboard 1440, dashboard 375. Raw PNGs live in the audit session's artifact store, not the repo — **repo-native evidence should be regenerated via the existing tooling**:

```
npm run qa:screenshots:capture   # needs Chrome on PATH + dev server; authenticated routes need --user-data-dir per docs/guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md
npm run qa:crypto-background     # CDP checks: reduced-motion, print, CLS/LCP, console errors on /ico + /login
```

Do not commit the stale checklist state: until captures exist, `docs/RESPONSIVE_SCREENSHOT_CHECKLIST.md` should read `[ ]` (today it falsely reads `[x]` with no PNGs — FE-024).

## Static-analysis evidence pointers (file:line index)

- Token storage: `src/api.ts:1972,2022,2118` · WS token URL: `src/api/origin.ts:222,234` · stale key: `src/pages/Backtests.tsx:710`
- Refresh single-flight: `src/api.ts:1818-1952` · role leniency: `src/auth/roles.ts:101-117` · guards: `src/App.tsx:91-126`
- Stale defaults: `src/components/BacktestRunner.tsx:110-111` · mnemonic textarea: `src/components/DYDXKeyManager.tsx:354-364`
- Dead pages: `src/pages/{BotDashboard,CRM,IBPortal,BacktestDetails}.tsx` (zero importers, grep-verified)
- CI gate: root `.github/workflows/bot-quality.yml` job `frontend-quality` (runs `test:contracts` only)
- Env defect: `backend/internal/db/db.go:344-364` (validate-before-clamp) + generated `run.json` database block

## Reproduction script (fresh machine)

```bash
nvm use 24 && cd frontend && npm install
make infra-up                      # repo root
# backend (until FE-005 lands): copy run.json → set DB_POOL_SIZE=25 → APP_RUN_CONFIG_FILE=<copy>
cd backend && BOOTSTRAP_ADMIN_PASSWORD=<local throwaway> go run ./cmd/server
cd ../frontend && npm run dev & npm run dev:backoffice &
# test users: register via POST /api/v1/auth/register; admin from BOOTSTRAP_ADMIN_PASSWORD
```
