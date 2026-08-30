# 01 — Executive Summary

**Audit date:** 2026-09-04 · **Scope:** `frontend/` (React 19 + TypeScript 6 + Vite 8, three-portal workspace) · **Method:** static code audit + full local runtime (backend, infra) + real-browser inspection of the authenticated client area, backoffice portal, and public pages.

## Application readiness status

**Runnable and fundamentally sound — above-average engineering hygiene for this domain, with targeted security, accessibility, and test-automation gaps.**

The application was made fully runnable locally (frontend 5173/5174, Go backend 8888, PostgreSQL/Valkey/NATS/ClickHouse/MinIO via `make infra-up`) with **one legitimate environment blocker found and worked around**: the `make dev`-generated `run.json` ships `DB_POOL_SIZE=105 > DB_MAX_CONNECTIONS=100`, which hard-fails Go backend startup (strict validation runs before the pool clamp). The Python bot API logs the same misconfiguration. This is a real out-of-the-box defect for every developer following `LOCAL_SETUP_GUIDE.md`.

- **Frontend runs locally:** Yes — `npm run dev` (client 5173), `npm run dev:backoffice` (5174); lint ✅, typecheck ✅, contract tests 8/8 ✅, production build ✅ (661ms, well-split chunks).
- **Authenticated client-area testing achieved:** Yes — real login with a seeded client account (`auditclient`) plus a bootstrap admin on the backoffice portal; full journey walked (login → dashboard → backtests/new → bots → settings → client area → market intel → admin hub → logout paths).
- **Backend authorization verified independently:** client-role token gets 403 `insufficient_permissions` on `/api/v1/admin/users` and `PUT /api/v1/settings` — frontend role guards are backed by server enforcement.

## Finding counts

| Priority | Count | Notable |
|---|---:|---|
| P0 | **0** | No broken core flow, no XSS sink, no secret leak, no unguarded money path found |
| P1 | **4** | localStorage JWT fallback; WS token in URL; stale `token` key breaks live-WS auth on Backtests page; test gate runs 1 of 19 test files with zero component/E2E tests |
| P2 | **21** | Unlabeled form fields on financial forms; triple-H1 pages; no self-serve password reset; raw axios errors in UI; dead admin link; dual API stacks; ~3,650 lines dead code; stale 2024 backtest defaults; run.json blocker; stale QA evidence; and more |
| P3 | **19** | Mnemonic plaintext textarea in one of two managers; WS debug logging; CSV formula injection; density/typography polish; dep hygiene; i18n cosmetic |

## Top 10 problems (ranked)

1. **FE-ENV-01 (P2, blocks everything locally):** `run.json` pool misconfig kills backend startup — every new dev hits this (`backend/internal/db/db.go:348` validates before `db.go:363` clamps).
2. **FE-SEC-01 (P1):** Access JWT mirrored to `localStorage['_dydx_access_token']` (`src/api.ts:1972`) — XSS-stealable fallback credential on a trading app; cookie-primary posture makes this removable.
3. **FE-SEC-02 (P1):** All authenticated WebSockets pass the JWT as `?access_token=` query param (`src/api/origin.ts:222,234`) — leaks into proxy/server logs; cookie handshake already works.
4. **FE-FN-01 (P1):** `Backtests.tsx:710` reads `localStorage.getItem('token')` — a key nothing writes — so that page's live-progress WS connects unauthenticated and silently leans on 8s HTTP fallback polling.
5. **FE-QA-01 (P1):** CI (`bot-quality.yml` frontend-quality job) runs only `test:contracts` (1 of 19 test files); no `npm test` script exists; zero component-DOM or E2E tests; all auth/backtest/bot/CRM/IB surfaces untested.
6. **FE-A11Y-01 (P2):** Financial forms (BacktestRunner, BotManager) have no associated `<label>`s — verified live: every input `hasLabel:false`, accessible names come from placeholders that vanish on type; Settings forms do label properly (inconsistent).
7. **FE-UX-01 (P2):** No self-serve password reset — "Account recovery" is a `mailto:` to support; unacceptable friction for a fintech product's #1 account problem.
8. **FE-ARCH-01/02 (P2):** Two divergent HTTP stacks (axios `api.ts` 4,822 lines vs fetch `enhancedClient.ts`, duplicated 401-refresh logic) + ~3,650 lines of dead legacy pages (`BotDashboard.tsx`, `CRM.tsx`, `IBPortal.tsx`, `BacktestDetails.tsx` cluster).
9. **FE-UX-02/04/05 (P2):** Operator surfaces leak raw axios strings ("Request failed with status code 502"); backtest form still defaults to Jan–Mar 2024; AdminHub's "Open Settings" link is a dead end in the backoffice portal (all three verified live).
10. **FE-SEC-05 (P2):** No CSP / Referrer-Policy / frame-protection meta or header contract anywhere in `index.html`.

## Top 10 UX improvements

1. Add self-serve password reset (email-token flow) instead of `mailto:` recovery.
2. Humanize all error surfaces (map axios/502/503 to operator language + next step) — pattern already exists in `InlineNotice`.
3. Default backtest window to a recent, data-backed range (e.g. trailing 90 days) instead of 2024-01-01→2024-03-31.
4. Fix AdminHub "Open Settings" dead link (route to `/admin/settings` in backoffice portal).
5. Remove the disabled "Light" option from the Theme combobox (or ship light mode — today it's a visible dead control).
6. Single-H1 page discipline; sidebar brand should not be an h1.
7. Neutral color for zero P&L (`$0` gray, not `+$0` green).
8. Explain silent portal redirects (client hitting `/admin` just lands on `/dashboard` with no message).
9. Username truncation in sidebar needs a tooltip/full display.
10. Mobile KPI strip: allow 1-column wrap below 400px instead of squeezed 2-up cards.

## Top 10 UI improvements

1. Tokenize spacing/radii in the hand-written 7,431-line `index.css` (41 `premium-*`/`operator-*` classes) behind the existing CSS variables.
2. Delete the vestigial `tailwind.config.js` or wire it via `@config` (Tailwind v4 currently ignores it).
3. Standardize card paddings/radii across Dashboard/Bots/Settings (visual review found mixed density).
4. Raise dashboard density (trading-terminal standard) — hero + large cards push KPIs below the fold at 900px.
5. Consistent focus-visible ring across all `premium-*` interactive elements.
6. Reduce sidebar item description noise at default width (or make descriptions hover/disclosure-only).
7. Align button heights (primary vs ghost) across desks.
8. Consistent skeleton treatment (some lists flash empty state before load completes).
9. Typography scale audit: eyebrow/label sizes crowd at 375px (mobile review).
10. Empty-state illustrations/states reuse — currently good but inconsistently styled across desks.

## QA automation recommendation

Adopt **Playwright** for E2E (repo has none; the hand-rolled CDP script proves the team can drive Chrome), **Vitest + Testing Library + jsdom** for component tests (neither installed today), and promote the existing 19-file Vitest suite into CI via a real `npm test` script. Target the E2E matrix in `07_E2E_TEST_MATRIX.md`: login/MFA, backtest run→progress→results, bot create/start/stop guardrails, role boundaries, and the ICO whitelist flow. Do not chase coverage numbers — guard the money paths.

## Proposed implementation order

Stage 0 environment fix → Stage 1 correctness/security P1s → Stage 2 test foundation → Stage 3 UX critical paths → Stage 4 a11y forms → Stage 5 UI consistency → Stage 6 perf/dep hygiene → Stage 7 architecture consolidation (API unification, dead-code deletion, design tokens). Full detail in `20_IMPLEMENTATION_ROADMAP.md`.

## Skills/agents created

None added to the repo — deliberately. The existing `.github/agents/senior-react-defi-product.agent.md` already covers implementation standards; the audit itself was executed with ephemeral specialized subagents (architecture, code quality, test/QA infra, security). Rationale and future recommendations in `21_AGENT_SKILLS_CREATED.md`.

## Blockers

- Python bot API exits during startup migrations in this environment → live backtest execution and bot-API-dependent surfaces were audited in their **degraded states** (which usefully exercised error UX). Not a frontend defect; flagged to backend.
- Registration flow not E2E-tested in browser (Turnstile site key absent locally; policy defaults verified via API instead — registration of the test account succeeded).

## Document index

All 22 documents live in `frontend/docs/frontend-audit/` (per repo docs governance: service-specific supplements live under the service).
