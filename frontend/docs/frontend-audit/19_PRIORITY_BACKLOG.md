# 19 — Priority Backlog

Legend — Priority: P0 critical · P1 high · P2 medium · P3 low. Complexity: XS <½d · S ~1d · M days · L ~week · XL architectural. Deps: FE=frontend-only · BE=needs backend · API=backend contract.
Status marks: ✅ done (2026-09-04 implementation pass 1) · 🟡 partially done · ⬜ open.

## Completion log

| Date | Completed |
|---|---|
| 2026-09-04 | FE-005, FE-001, FE-004a (`npm test` + full suite in CI; full Playwright/jsdom foundation still open under FE-004), FE-011, FE-012, FE-013 (hidden Light option; full light mode still deferred), FE-010, FE-014, FE-031, FE-007, FE-027, FE-026 |
| 2026-09-05 (pass 3) | FE-006 (Field primitive + both financial forms), FE-022 (started: shared format util + Dashboard), FE-018 (partial: referrer meta), FE-028 (CSV injection guard), FE-029 (partial: https allowlist + host suffix guard) |
| 2026-09-05 (pass 9b) | FE-038 label category burned down (91→0, rule on) |
| 2026-09-05 (pass 10) | FE-009 **complete** (backend tokens + endpoints, frontend screens/routes/e2e, live-verified end-to-end; NULL full_name/avatar scan fix 35b8a5e2) |
| 2026-09-05 (pass 11) | FE-038 import-naming + jsx-a11y interaction categories → 0 (1f0e9662); react-hooks compiler rules → 0 (b0fb2b41); exhaustive-deps → 0 (a4f5724a); set-state-in-effect 54 → 33 (6e854e9d, paused mid-category) |
| 2026-09-06 (pass 14) | FE-015 core: single HTTP stack — enhancedClient on axios via requestJson, fetch machinery deleted, live-verified (1137a6a6); CI green both workflows |
| 2026-09-06 (pass 15) | FE-023 Settings → React Query (900e4d41); BacktestList → React Query with active-only polling + backoff via refetchInterval, per-run status calls dropped as redundant (d848f2aa); enhancedClient deleted → botApi.ts, hooks/websocket auth direct on api.ts (cc7231cc); api.ts chunk split measured and rejected (+16KB gzip first load — see FE-015 row) |
| 2026-09-06 (pass 13) | FE-022 **complete** — ~40 remaining money sites migrated to shared formatters (09e4e560) |
| 2026-09-06 (pass 12) | FE-009 e2e CI failures root-caused to two real form bugs — first-submit validation race (ForgotPassword) + submit-button deadlock (ResetPassword) — fixed + verified backend-free (90e79303); FE-038 **complete**: set-state-in-effect 31 → 0, rule enforced (68244e7e); all 238 lint findings closed |
| 2026-09-05 (pass 9) | FE-018 (nginx CSP + hardening headers), FE-029 (backend avatar validation + tests), FE-033 (noUncheckedIndexedAccess enabled, 50 fixed) |
| 2026-09-05 (pass 8) | FE-033a (eslint full coverage + prettier), FE-036 (complete), FE-030 (complete), FE-022b (6 formatters), FE-019, FE-002 + FE-003 (cookie-first auth, verified live), FE-015 (scoped: shim deleted), FE-024 (complete within tooling limits); NEW FE-038 lint debt (238); backend CI test fix for c70cc809's fixture seeding (0879b268) |
| 2026-09-05 (pass 7) | FE-032 (complete: −33% eager JS, event-driven WS auth sync) |
| 2026-09-05 (pass 6) | FE-025 (complete), FE-036 (partial: first-run card; skeletons verified already present; terminology open) |
| 2026-09-05 (pass 5) | FE-023 (partial: 5 components to React Query), FE-008 (P&L direction arrows) |
| 2026-09-05 (pass 4) | FE-030 (partial: naming + keyboard + skip link), FE-033 (partial: StrictMode, tailwind config, eslint comment), FE-035 |
| 2026-09-05 | FE-016 (7 dead files + `src/dev` deleted), FE-021 (framer-motion/@headlessui/@react-buddy/date-fns/recharts removed; vite+tailwindcss+forms → devDeps), FE-017 (roleMatches fail-closed + tests), FE-020 (RouteErrorBoundary via pathless errorElement), FE-004 **complete** (jsdom + Testing Library + Playwright, 2 component tests, 7 backend-free E2E smoke specs, CI runs unit+e2e; suite now 21 files / 116 tests + 7 e2e) |

## P1 — correctness & security high

| ID | Area | Issue | Impact | Complexity | Deps | Regression risk |
|---|---|---|---|---|---|---|
| ✅ FE-001 | Correctness | Stale `localStorage['token']` read → Backtests page live-progress WS unauthenticated; silently falls back to 8s polling | Live progress integrity | XS | none | none — now uses `api.connectSocket` (verified: import removed, socket built with stored token) |
| ✅ FE-002 | Security | Access JWT persisted in localStorage | Session theft surface | M | — **done: persistence removed, boot scrubs legacy key, recovery is cookie-driven (verified live)** |
| ✅ FE-003 | Security | WS `?access_token=` in URL on all auth'd sockets → log/proxy leakage | Credential leakage | M | — **done: cookie-first WS auth (backend `auth_token.go` accepts session cookie on upgrades); query token only when no session hint** |
| ✅ FE-004 | Test/QA | CI runs 1/19 test files; no `npm test`; zero component/E2E coverage on money paths | Regression blindness | M | none | none (additive) — **partially done (a): `npm test` script added, full 20-file/111-test suite now the CI gate; Playwright+jsdom+Testing Library still open** |

## P2 — this quarter

| ID | Area | Issue | Impact | Complexity | Deps |
|---|---|---|---|---|---|
| ✅ FE-005 | Environment | run.json `DB_POOL_SIZE(105)>DB_MAX_CONNECTIONS(100)` hard-fails backend startup (validate-before-clamp); bot API logs same | Every new dev blocked | S | BE (clamp or fix profile) — **done in BE: `db.go` now clamps with warning; backend boots on stock run.json (verified live)** |
| ✅ FE-006 | A11y | Financial forms lack label association (names from placeholders) — BacktestRunner, BotManager | SR users locked out of core flows | M | none — **done: `Field` primitive (label/hint/error + aria wiring) + 5 component tests; 12 BacktestRunner + 7 BotManager fields migrated; verified live: 15/15 controls label-associated on /backtests/new** |
| ✅ FE-007 | A11y/UI | Multiple h1 per page (3 on dashboard) | Navigation semantics | S | none — **done: sidebar brand → p, all main-content h1 → h2, banner is canonical h1 (verified: exactly 1 h1 on dashboard & backtests/new)** |
| ✅ FE-008 | A11y | P&L color-only signaling | Colorblind operators | S | U4.3 formatter — **done: ▲/▼ direction glyphs on signed P&L via shared formatter (Dashboard hero, avg, lifetime inherit)** |
| ✅ FE-009 | UX | No self-serve password reset (mailto only) | Lockout = support ticket | M | BE (token endpoints) — **done: backend `password_reset_tokens` (SHA-256 hash, 30-min TTL, single-use atomic consume, 60s cooldown, no-enumeration responses, session-generation bump) + `/forgot-password` & `/reset-password` screens, routes, api methods, login link swap; 6 handler tests + 3 e2e specs; verified live end-to-end (unknown email identical 200, cooldown throttles, newest link invalidates older, replay rejected, new password logs in). Live pass also surfaced + fixed a production bug: NULL `full_name`/`avatar` broke user scans (35b8a5e2)** |
| ✅ FE-010 | UX | Raw axios strings in operator surfaces (Bots 502 case) | Trust, actionability | S | none — **done: `src/utils/apiErrors.ts` (+8 tests) applied to Arbitrage panel; adopt gradually elsewhere** |
| ✅ FE-011 | UX | Backtest defaults frozen at 2024-01→03 | Stale research defaults | XS | none — **done: trailing 90-day window (verified live: 2026-06-07→2026-09-04)** |
| ✅ FE-012 | UX | AdminHub "Open Settings" dead link in backoffice portal | Broken chrome | XS | none — **done: → `/admin/settings`** |
| ✅ FE-013 | UX | Theme combobox shows disabled "Light" (FORCE_DARK_THEME) | Visible dead control; README drift | XS (hide) / M (ship light) | product decision — **done (hide); full light mode deferred** |
| ✅ FE-014 | Network | Duplicate codex market-overview fetch on Market Intel | Wasted calls, slower paint | S | none — **root cause was React Query retrying deterministic 503s; retry now skips any HTTP-status error (transport errors still back off)** |
| 🟡 FE-015 | Architecture | Dual HTTP stacks (axios api.ts 4,822ln vs fetch enhancedClient) with duplicated refresh logic; ambiguous `api/client.ts` shim | Every auth bug fixed twice | L | none — **nearly done: single HTTP stack (1137a6a6) + facade deleted → `src/api/botApi.ts` endpoint surface, auth/session calls direct on api.ts (cc7231cc); Settings + BacktestList migrated to React Query (900e4d41, d848f2aa). Remaining: BacktestDetailsV2 → React Query. Chunk split attempted + measured 2026-09-06 and REJECTED: manualChunks for api.ts hoists shared helpers eager (45.2→61.1KB gzip first load) — the real fix is per-portal endpoint modules so class methods tree-shake, deliberately deferred** |
| ✅ FE-016 | Dead code | ~3,650 lines dead pages + components (BotDashboard, CRM, IBPortal, BacktestDetails cluster, hooks/useBacktestProgress) | Maintenance drag | S | none — **done: 7 files + src/dev deleted, zero-importer verified, build/lint green** |
| ✅ FE-017 | Security | `roleMatches` fail-open for unknown/custom roles on backoffice lists | Wrong-role UI exposure (backend still 403s) | S | none — **done: fail-closed, custom roles need explicit allow-listing; 3 regression tests** |
| ✅ FE-018 | Security | No CSP/Referrer-Policy/frame-ancestors (meta+server) | Clickjacking/referrer leakage | S | — **done: referrer meta (pass 3) + full header set in docker/nginx.conf (CSP, X-Frame-Options DENY, nosniff, Permissions-Policy), validated in-container; repeated per-location to defeat nginx add_header inheritance** |
| ✅ FE-019 | Security | CSRF posture undocumented for cookie-authenticated mutations | Needs verification | S | — **done: verified SameSite=Lax default + origin-allowlisted CORS; residual recommendation (Origin check under SameSite=None) filed in 16_SECURITY_AUDIT.md** |
| ✅ FE-020 | Reliability | Single global ErrorBoundary; no per-route `errorElement` | One crash = blank app | S | none — **done: `RouteErrorBoundary` on pathless wrapper route (in-place reload/dashboard recovery)** |
| ✅ FE-021 | Deps | Unused prod deps (framer-motion, @headlessui, @react-buddy, date-fns, recharts-via-dead-page); react-hook-form 1-file usage | Bundle/supply chain | S | FE-016 first — **done: 5 deps removed; vite/tailwindcss/@tailwindcss/forms moved to devDependencies** |
| ✅ FE-022 | Code quality | 65 local formatters/172 toFixed/date-fns-unused — money formatting not centralized | Inconsistent money display | M | none — **done: `src/utils/format.ts` shared formatters adopted across all money surfaces (Dashboard, ClickHouseAnalytics, TradeHistory, PerformanceMetrics, IB commissions/tier rates, RedisSettings, StrategyManager, BotManager); non-money decimals (sharpe/z-score/MB) intentionally local (09e4e560)** |
| 🟡 FE-023 | Code quality | 21 manual loading/error useState files vs React Query (half-finished migration) | Duplicated state bugs | M | none — **7 surfaces migrated (SummaryCard, PerformanceMetrics, TradeHistory, RedisSettings, AdminComingSoonSettings, Settings, BacktestList) + useBacktestSummary hook; SyncHealthPanel stays manual by design (adaptive 10s→60s backoff); BacktestDetailsV2 is the last file (its calls now go through api/botApi only)** |
| ✅ FE-024 | QA process | Responsive QA checklists `[x]` with zero evidence files; CI test gate mismatch | False confidence | S | re-run capture suite — **CI gate half fixed by FE-004a; screenshot evidence refreshed: 24 public-route captures on QA machine + checklist regenerated to match the tool (PNGs uncommitted per root .gitignore policy)** |
| ✅ FE-025 | UX/UI | Mobile KPI squeeze + table scroll affordance + sidebar description noise | Mobile operator polish | S | none — **done: KPI grids 1-col <400px (Dashboard + BotManager, verified live), `.scroll-shadow-x` right-edge fade on wide tables (computed style verified), sidebar descriptions gated to xl+ with hover title** |

## P3 — backlog

| ID | Area | Issue | Complexity |
|---|---|---|---|
| ✅ FE-026 | Security | DYDXKeyManager mnemonic in visible textarea → masked password input + Show/Hide toggle | XS |
| ✅ FE-027 | Security | WS debug:true logs payloads in prod → default now `import.meta.env.DEV` | XS |
| ✅ FE-028 | Security | CSV formula-injection neutralization — **done: `utils/csv.ts` sanitizeCsvCell/toCsvCell (+4 tests) wired into BacktestComparator + TableControls; numeric cells preserved** | XS |
| FE-029 | Security | Avatar MIME client-only; news URL scheme allowlist; sanitizeHost suffix allowlist | S |
| ✅ FE-030 | A11y | Unnamed icon buttons; unnamed settings searchbox; skip-link; nav-as-links | S | — **done: all four (sidebar nav now real <Link> elements, verified live)** |
| ✅ FE-031 | UX | Zero-P&L now `$0` neutral slate (verified live); sidebar identity + email tooltips; wrong-portal redirect shows explanatory toast | XS |
| ✅ FE-032 | Perf | index-*.js 217KB eager-import audit; Landing lazy-fication; WS 1s auth watcher event-driven | M | — **done: sourcemap-attributed composition; Landing/Pricing/PublicServicePage/Register route-split → index 227KB→151KB (gzip 60→40KB, −33%); WS auth watcher now event-driven via `auth:changed` events (no more perpetual 1s interval). api.ts (45.6KB eager) remains — bundled with FE-015** |
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


## FE-038 — lint debt burn-down (new, discovered 2026-09-05)

Enabling the full recommended lint rule sets revealed 238 pre-existing violations
(the legacy config was dead, so these rules never ran). Carved out explicitly in
`eslint.config.cjs` until burned down per category:

| Rule | Count | Fix pattern |
|---|---:|---|
| ~~jsx-a11y/label-has-associated-control~~ | ~~91~~ → **0 (2026-09-05: all 91 associated via htmlFor/id pairs, group captions converted to <p>, rule enabled at error level with depth 4; verified live — zero orphaned refs)** |
| ~~react-hooks/exhaustive-deps~~ | ~~36~~ → **0 (2026-09-05: stable raw bindings replace `?? []` fallback deps; loaders to useCallback; justified disables for pass-through hook + signature-deps sync; rule enabled)** |
| ~~import/no-named-as-default (+member)~~ | ~~24~~ → **0 (2026-09-05: named imports at 21 sites, redundant default exports dropped, axios named imports; rule enabled)** |
| ~~jsx-a11y interaction rules~~ | ~~14~~ → **0 (2026-09-05: keyboard-operable rows/headers, presentation-role backdrops, justified disables on APG Escape dialogs; rules enabled)** |
| ~~react-hooks (compiler: static-components, purity, immutability, preserve-manual-memoization)~~ | ~~15~~ → **0 (2026-09-05: useNow() clock hook, hoisted loaders, module-scope MetricCard, stable memo bindings; rules enabled)** |
| ~~react-hooks/set-state-in-effect~~ | ~~54~~ → **0 (2026-09-06: all six categories closed — render-time adjust for data→draft syncs and reset-on-change, lazy initializers, consumption-time derivation, microtask-deferred mount loaders; 238 original findings at zero, every rule enforced at error level)** |
