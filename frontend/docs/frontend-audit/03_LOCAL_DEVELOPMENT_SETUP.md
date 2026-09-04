# 03 — Local Development Setup (verified 2026-09-04)

Everything below was executed end-to-end during this audit. No production configuration was changed.

## What is required

| Component | Command | Port | Status |
|---|---|---|---|
| Node | nvm: 24.19.0 (26.7.0 also present; ≥20.19 required by Vite 8) | — | ✅ node_modules already installed |
| Infra (PostgreSQL, Valkey, NATS, ClickHouse, MinIO) | `make infra-up` (repo root) | 5432/6379/4222+8222/8123/9010+9011 | ✅ all healthy |
| Go backend | `cd backend && make run` | 8888 | ⚠️ blocked by run.json defect — see below |
| Frontend client portal | `npm run dev` | 5173 | ✅ |
| Frontend backoffice | `npm run dev:backoffice` | 5174 | ✅ |
| Frontend IB portal | `npm run dev:ib` | 5175 | not started this session |
| Python bot API | `cd bot && .venv/bin/python -m uvicorn src.api.server:app --port 8889` | 8889 | ⚠️ exits during startup migrations in this env |

## Environment defect found (FE-ENV-01, P2 — fix first)

`make dev` generates a repo-root `run.json` with:

```
database.DB_POOL_SIZE = 105   >   database.DB_MAX_CONNECTIONS = 100
```

- Go backend: `internal/db/db.go:348` returns `"MaxIdleConns cannot exceed MaxOpenConns"` **before** the clamp at `db.go:357-364` could repair it → startup fatal on a fresh checkout. Verified twice.
- Python bot API: logs the same misconfig (`Effective max_overflow is clamped to 0`) — corroborating a profile-level bug, not a service-level one.
- `cmd/server/main.go:34` calls `config.AutoLoadStructuredConfigEnv(true)` — `override=true` means run.json **always beats environment variables**, so `DB_POOL_SIZE=10 go run ...` does not work.

**Audit workaround (local-only, documented for reproducibility):**

```bash
python3 - <<'EOF'
import json
d = json.load(open('run.json')); d['database']['DB_POOL_SIZE'] = 25
json.dump(d, open('/tmp/run-audit.json','w'), indent=2)
EOF
cd backend && APP_RUN_CONFIG_FILE=/tmp/run-audit.json \
  BOOTSTRAP_ADMIN_PASSWORD='<local throwaway>' go run ./cmd/server
```

**Proper fixes (pick one, backend repo):** clamp `MaxIdleConns` to `MaxOpenConns` in validation; or fix the dev profile's `DB_POOL_SIZE`; or reorder validate-after-clamp. Frontend impact: none once backend runs.

## Test accounts (how auth testing was achieved)

- **Bootstrap admin:** backend idempotently provisions `admin` on first start (`backend/internal/startup/bootstrap_admin.go`). Outside production with `BOOTSTRAP_ADMIN_PASSWORD` unset it generates a one-time password logged once and forces rotation; setting the env var explicitly yields a stable local login (no rotation). Used for backoffice portal (5174).
- **Client user:** `POST /api/v1/auth/register` (`auditclient` / local throwaway) — registration policy defaulted to open in the dev profile. Used for the client portal journey.
- No production credentials were touched; both passwords are local-only throwaways.

## Verification results

| Gate | Result |
|---|---|
| `npm install` | already satisfied (node_modules present, lockfile consistent) |
| `npm run lint` (`--max-warnings 0`) | ✅ pass |
| `npm run typecheck` | ✅ pass |
| `npm run test:contracts` | ✅ 8/8 (only test script that exists — see 18_TEST_AUTOMATION_STRATEGY) |
| `npm run build` | ✅ 661ms; portal chunks as designed; no sourcemaps emitted |
| Backend `/health` | ✅ healthy (DB healthy, bot_api unreachable → degraded) |
| Login (client + admin) | ✅ flat token payload `{access_token, refresh_token, token_type, expires_in, session_expires_at}` — note: **not** the documented `{success,data}` envelope |

## Vite dev server & proxy

- Proxy: `/api` and `/ws` → `VITE_API_BASE_URL || VITE_API_URL || http://localhost:8888`, `ws: true`, `changeOrigin` (`vite.config.ts`).
- Build-time config: `vite.config.ts` discovers the monorepo root, decrypts `config/profiles/{env}.config.enc.json` (AES-256-GCM, key `.configkey.bin` from `make config-keygen`) and `define`-injects every `VITE_*` value; real `process.env.VITE_*` overrides win. CI writes a hermetic `.ci-run.json` + `APP_RUN_CONFIG_FILE` for the same reason.
- Env vars read by src: `VITE_API_BASE_URL`, `VITE_API_URL`, `VITE_AUTH_BASE_URL`, `VITE_APP_PORTAL_TYPE`, `VITE_TURNSTILE_SITE_KEY`, `VITE_DISABLE_TURNSTILE`, `VITE_CLIENT_HOST`, `VITE_CRM_HOST`, `VITE_IB_PORTAL_HOST`, `VITE_LIVE_URL`, `VITE_FLOWER_URL`, `VITE_ENABLE_SUBDOMAIN_PORTAL_NAV`, `VITE_DEBUG_LEGACY_FALLBACKS`. Last five are absent from `.env.example` (P3 doc gap).

## CORS / cookies / HTTPS locally

- Dev uses the Vite proxy (same-origin) — no CORS friction. Tokens: HttpOnly cookie set by backend + Bearer fallback; `withCredentials: true` everywhere.
- No local HTTPS or domain aliases required. Turnstile self-disables on localhost (`TurnstileWidget.tsx:45-59`), so registration is testable without a site key; server-side enforcement of Turnstile when configured is a backend concern.

## Known limitations during this audit

1. **Python bot API exits during Alembic startup migrations** in this environment (last log line `Running pending Alembic migrations...`, process gone). Consequence: live backtest *execution*, real market lists, and bot runtime stats were audited in their degraded/error states. This is a backend/bot issue, not frontend; the degraded-state UX was itself valuable evidence (see 05_QA_AUDIT).
2. Full 19-file Vitest suite runs only via `npx vitest run` (no script) — executed by the audit's static pass, not in CI.
3. The repo's responsive screenshot QA scripts require a locally installed Chrome/Chromium on PATH; the headless environment used for this audit used in-app browser tooling instead (evidence in 22_EVIDENCE_AND_SCREENSHOTS).
