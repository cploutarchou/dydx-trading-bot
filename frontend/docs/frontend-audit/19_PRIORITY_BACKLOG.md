# 19 — Priority Backlog

Legend — Priority: P0 critical · P1 high · P2 medium · P3 low. Complexity: XS <½d · S ~1d · M days · L ~week · XL architectural. Deps: FE=frontend-only · BE=needs backend · API=backend contract.
Status marks: ✅ done (2026-09-04 implementation pass 1) · 🟡 partially done · ⬜ open.

## Completion log

| Date | Completed |
|---|---|
| 2026-09-04 | FE-005, FE-001, FE-004a (`npm test` + full suite in CI; full Playwright/jsdom foundation still open under FE-004), FE-011, FE-012, FE-013 (hidden Light option; full light mode still deferred), FE-010, FE-014, FE-031, FE-007, FE-027, FE-026 |
| 2026-09-05 (pass 3) | FE-006 (Field primitive + both financial forms), FE-022 (started: shared format util + Dashboard), FE-018 (partial: referrer meta), FE-028 (CSV injection guard), FE-029 (partial: https allowlist + host suffix guard) |
| 2026-09-05 (pass 5) | FE-023 (partial: 5 components to React Query), FE-008 (P&L direction arrows) |
| 2026-09-05 (pass 4) | FE-030 (partial: naming + keyboard + skip link), FE-033 (partial: StrictMode, tailwind config, eslint comment), FE-035 |
| 2026-09-05 | FE-016 (7 dead files + `src/dev` deleted), FE-021 (framer-motion/@headlessui/@react-buddy/date-fns/recharts removed; vite+tailwindcss+forms → devDeps), FE-017 (roleMatches fail-closed + tests), FE-020 (RouteErrorBoundary via pathless errorElement), FE-004 **complete** (jsdom + Testing Library + Playwright, 2 component tests, 7 backend-free E2E smoke specs, CI runs unit+e2e; suite now 21 files / 116 tests + 7 e2e) |

## P1 — correctness & security high

| ID | Area | Issue | Impact | Complexity | Deps | Regression risk |
|---|---|---|---|---|---|---|
| ✅ FE-001 | Correctness | Stale `localStorage['token']` read → Backtests page live-progress WS unauthenticated; silently falls back to 8s polling | Live progress integrity | XS | none | none — now uses `api.connectSocket` (verified: import removed, socket built with stored token) |
| ⬜ FE-002 | Security | Access JWT persisted in localStorage (XSS-stealable fallback bearer) | Session theft surface | M | API (confirm cookie-only auth incl. WS handshake) | medium — verify all endpoints accept cookie session |
| ⬜ FE-003 | Security | WS `?access_token=` in URL on all auth'd sockets → log/proxy leakage | Credential leakage | M | API (WS auth via cookie/first-message) | medium |
| 🟡 FE-004 | Test/QA | CI runs 1/19 test files; no `npm test`; zero component/E2E coverage on money paths | Regression blindness | M | none | none (additive) — **partially done (a): `npm test` script added, full 20-file/111-test suite now the CI gate; Playwright+jsdom+Testing Library still open** |

## P2 — this quarter

| ID | Area | Issue | Impact | Complexity | Deps |
|---|---|---|---|---|---|
| ✅ FE-005 | Environment | run.json `DB_POOL_SIZE(105)>DB_MAX_CONNECTIONS(100)` hard-fails backend startup (validate-before-clamp); bot API logs same | Every new dev blocked | S | BE (clamp or fix profile) — **done in BE: `db.go` now clamps with warning; backend boots on stock run.json (verified live)** |
| ✅ FE-006 | A11y | Financial forms lack label association (names from placeholders) — BacktestRunner, BotManager | SR users locked out of core flows | M | none — **done: `Field` primitive (label/hint/error + aria wiring) + 5 component tests; 12 BacktestRunner + 7 BotManager fields migrated; verified live: 15/15 controls label-associated on /backtests/new** |
| ✅ FE-007 | A11y/UI | Multiple h1 per page (3 on dashboard) | Navigation semantics | S | none — **done: sidebar brand → p, all main-content h1 → h2, banner is canonical h1 (verified: exactly 1 h1 on dashboard & backtests/new)** |
| ✅ FE-008 | A11y | P&L color-only signaling | Colorblind operators | S | U4.3 formatter — **done: ▲/▼ direction glyphs on signed P&L via shared formatter (Dashboard hero, avg, lifetime inherit)** |
| ⬜ FE-009 | UX | No self-serve password reset (mailto only) | Lockout = support ticket | M | BE (token endpoints) |
| ✅ FE-010 | UX | Raw axios strings in operator surfaces (Bots 502 case) | Trust, actionability | S | none — **done: `src/utils/apiErrors.ts` (+8 tests) applied to Arbitrage panel; adopt gradually elsewhere** |
| ✅ FE-011 | UX | Backtest defaults frozen at 2024-01→03 | Stale research defaults | XS | none — **done: trailing 90-day window (verified live: 2026-06-07→2026-09-04)** |
| ✅ FE-012 | UX | AdminHub "Open Settings" dead link in backoffice portal | Broken chrome | XS | none — **done: → `/admin/settings`** |
| ✅ FE-013 | UX | Theme combobox shows disabled "Light" (FORCE_DARK_THEME) | Visible dead control; README drift | XS (hide) / M (ship light) | product decision — **done (hide); full light mode deferred** |
| ✅ FE-014 | Network | Duplicate codex market-overview fetch on Market Intel | Wasted calls, slower paint | S | none — **root cause was React Query retrying deterministic 503s; retry now skips any HTTP-status error (transport errors still back off)** |
| ⬜ FE-015 | Architecture | Dual HTTP stacks (axios api.ts 4,822ln vs fetch enhancedClient) with duplicated refresh logic; ambiguous `api/client.ts` shim | Every auth bug fixed twice | L | none (staged consolidation) |
| ✅ FE-016 | Dead code | ~3,650 lines dead pages + components (BotDashboard, CRM, IBPortal, BacktestDetails cluster, hooks/useBacktestProgress) | Maintenance drag | S | none — **done: 7 files + src/dev deleted, zero-importer verified, build/lint green** |
| ✅ FE-017 | Security | `roleMatches` fail-open for unknown/custom roles on backoffice lists | Wrong-role UI exposure (backend still 403s) | S | none — **done: fail-closed, custom roles need explicit allow-listing; 3 regression tests** |
| 🟡 FE-018 | Security | No CSP/Referrer-Policy/frame-ancestors (meta+server) | Clickjacking/referrer leakage | S | BE/infra headers — **referrer meta done; CSP + frame-ancestors remain server-side (infra)** |
| ⬜ FE-019 | Security | CSRF posture undocumented for cookie-authenticated mutations (SameSite=None assumption) | Needs verification | S | BE verify Origin checks |
| ✅ FE-020 | Reliability | Single global ErrorBoundary; no per-route `errorElement` | One crash = blank app | S | none — **done: `RouteErrorBoundary` on pathless wrapper route (in-place reload/dashboard recovery)** |
| ✅ FE-021 | Deps | Unused prod deps (framer-motion, @headlessui, @react-buddy, date-fns, recharts-via-dead-page); react-hook-form 1-file usage | Bundle/supply chain | S | FE-016 first — **done: 5 deps removed; vite/tailwindcss/@tailwindcss/forms moved to devDependencies** |
| 🟡 FE-022 | Code quality | 65 local formatters/172 toFixed/date-fns-unused — money formatting not centralized | Inconsistent money display | M | none — **started: `src/utils/format.ts` (+5 tests) adopted on Dashboard; remaining surfaces migrate opportunistically** |
| 🟡 FE-023 | Code quality | 21 manual loading/error useState files vs React Query (half-finished migration) | Duplicated state bugs | M | none — **5 standalone components migrated (SummaryCard, PerformanceMetrics, TradeHistory, RedisSettings, AdminComingSoonSettings) + new useBacktestSummary hook; SyncHealthPanel stays manual by design (adaptive 10s→60s backoff); BacktestList/BacktestDetailsV2/Settings deferred to the FE-015 window** |
| 🟡 FE-024 | QA process | Responsive QA checklists `[x]` with zero evidence files; CI test gate mismatch | False confidence | S | re-run capture suite — **CI gate half fixed by FE-004a; screenshot evidence still stale** |
| ⬜ FE-025 | UX/UI | Mobile KPI squeeze + table scroll affordance + sidebar description noise | Mobile operator polish | S | none |

## P3 — backlog

| ID | Area | Issue | Complexity |
|---|---|---|---|
| ✅ FE-026 | Security | DYDXKeyManager mnemonic in visible textarea → masked password input + Show/Hide toggle | XS |
| ✅ FE-027 | Security | WS debug:true logs payloads in prod → default now `import.meta.env.DEV` | XS |
| ✅ FE-028 | Security | CSV formula-injection neutralization — **done: `utils/csv.ts` sanitizeCsvCell/toCsvCell (+4 tests) wired into BacktestComparator + TableControls; numeric cells preserved** | XS |
| FE-029 | Security | Avatar MIME client-only; news URL scheme allowlist; sanitizeHost suffix allowlist | S |
| 🟡 FE-030 | A11y | Unnamed icon buttons (camera, devtools); unnamed settings searchbox; skip-link; nav-as-links | S | — **done: search box + avatar controls named & keyboard-accessible, skip-to-content link added; nav-buttons→links still open** |
| ✅ FE-031 | UX | Zero-P&L now `$0` neutral slate (verified live); sidebar identity + email tooltips; wrong-portal redirect shows explanatory toast | XS |
| ⬜ FE-032 | Perf | index-*.js 217KB eager-import audit; Landing lazy-fication; WS 1s auth watcher event-driven | M |
| FE-033 | Code | StrictMode inversion; tailwind.config vestigial; eslint flat+legacy duplication; prettier not installed; tsconfig `noUncheckedIndexedAccess` | S |
| FE-034 | i18n | EN/EL claims vs 3-component reality — either scope down README or invest in catalog | M |
| FE-035 | Docs | `.env.example` missing VITE_LIVE_URL/VITE_FLOWER_URL; stale "many anys" comment in eslint config | XS |
| FE-036 | UX | First-run dashboard checklist; skeletons for latency-visible lists; terminology glossary pass | S |
| FE-037 | Process | Web-vitals/error telemetry beacon (see 18) | M |

## Dependency graph (critical path)

```
FE-005 (env fix) ──► everything local
FE-016 (dead code) ──► FE-021 (dep removal, recharts)
FE-004 (test foundation) ──► protects FE-002/003 (auth changes) ──► FE-015 (API consolidation)
UI tokens (12-DS) ──► FE-006 (Field) ──► form migration waves
BE token endpoints ──► FE-009 (password reset)
```

Suggested slicing: 6 PR-able units max in flight; each P1 item lands with its regression test (Tier 3/4 per 18).
