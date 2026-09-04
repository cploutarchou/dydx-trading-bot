# 18 — Test Automation Strategy

## Current state (measured)

- **19 Vitest files, ~103 cases, all pure unit/contract** — zero DOM/component tests (no jsdom, no Testing Library installed), zero E2E (no Playwright/Cypress anywhere).
- **CI (`bot-quality.yml` → `frontend-quality`) runs `lint + typecheck + test:contracts + build`** — i.e. **1 of 19 test files**; no `npm test` script exists; the other 18 files run only if someone types `npx vitest run`.
- Root Makefile `test` = lint+build for frontend (no vitest). Frontend Makefile has no test target.
- Contract guards (`contractGuards.test.ts`) check key-presence on 4 backtest endpoints only — no type checks, no negative envelope cases, nothing for auth/bots/CRM/IB/settings.
- Fixtures/factories: none; tests hand-roll literals. No msw. No coverage tooling.
- QA scripts: 3 dependency-free Node scripts driving Chrome (CLI flags / raw CDP) — public routes only; authenticated capture documented as blocked.
- Responsive checklists claim completion but screenshot dirs are absent (stale evidence).

## Strategy: right-size the pyramid to risk (fintech: money paths + authz first)

### Tier 1 — Pure unit (already strong; extend selectively)
Keep + extend: formatters (consolidate 65 local helpers into `src/utils/format.ts` with tests — doubles as dedup), `loginForm` helpers, role normalization (add fail-closed cases for SEC-03), payload normalizers. **Rule: no new local formatter without a test in the shared util.**

### Tier 2 — Contract guards (expand the cheap, high-value layer)
Grow `contractGuards` to: login/register/refresh payload shapes, `/me` user object (role/flags), bot instance list/status, strategy CRUD, CRM client envelope, settings GET/PUT, WS message envelopes (progress/status). Add type assertions (not just key-presence) + negative envelope cases. Est S per endpoint group; runs in <1s.

### Tier 3 — Component tests (new capability: jsdom + @testing-library/react)
Install: `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@vitest/coverage-v8`. A `vitest.config.ts` (environment jsdom; keep node-env for pure units via docblock or workspace projects). Priority components:
1. `Field`/`Button` primitives (when built — U2) with a11y assertions (`getByLabelText`).
2. BacktestRunner form: validation matrix (reversed dates ✅ case exists today only via code), NaN guards, double-submit disable.
3. BotManager create form: masked mnemonic, confirmation dialogs.
4. Login/MFA step flow with mocked api store.
5. LiveState/TerminalDataGrid behavior props.
**Rule: every bug fixed gets a component test first (fix-second).**

### Tier 4 — E2E: Playwright (the big gap)
- Install `@playwright/test`; config with 3 auth fixtures (client/admin/ib via storageState), baseURL 5173, `page.route` mocks for API-failure cases, webserver binding to `npm run dev` + backend profile.
- Implement waves from `07_E2E_TEST_MATRIX.md`: Wave 1 rows 1,2,5,8,15,13-form,21 (no bot API needed); Wave 2 (bot-dependent) behind `@botapi` tag once bot API stabilizes.
- 3-browser smoke project (chromium/firefox/webkit) on rows 1,8,20.
- **Visual regression:** Playwright screenshots (`toHaveScreenshot`) on 8 canonical screens × 375/1440 with clock/countdown masks — replaces the stale manual checklist; wire `qa:screenshots:sync` to it.

### CI wiring (one job, ordered)
```
lint → typecheck → vitest run (ALL suites) → build → playwright (chromium) → playwright smoke (3 browsers, on main only)
```
Add `npm test` = `vitest run`; keep `test:contracts` as alias. Coverage via `@vitest/coverage-v8` with **thresholds on changed-files only** (ratchet, not vanity %).

### What NOT to do
- No 100% coverage goal; no snapshot-testing pages (visual suite covers); no mocking the whole API layer in E2E (use real backend for authz rows — that's the point); no Cypress (Playwright's storageState+multi-browser fits better); no Storybook.

### Observability hook (Phase-25 requirement)
Bundle a tiny `reportWebVitals`-style reporter (LCP/INP/CLS + `fetch` failure beacon to backend `/api/v1/observability/frontend`, release tag from build) behind an env flag. Tests then cover money paths; telemetry covers reality. Keep it opt-out, no PII.
