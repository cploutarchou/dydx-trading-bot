# 06 — QA Test Plan

Risk-weighted plan for the surfaces that matter in a trading product. Priority: correctness > security > clarity > reliability > accessibility > performance.

## 1. Scope & environments

| Env | Purpose | Data | Reset |
|---|---|---|---|
| local (this setup) | dev + smoke | seeded `admin` + throwaway client; mock run `/backtest/mock-run-aabb1122` | `make infra-down` + volume prune; users via register API |
| CI | lint/typecheck/**all unit+component**/build per PR | hermetic `.ci-run.json` | ephemeral |
| QA/e2e (new) | Playwright E2E vs stack (backend+infra, bot API optional w/ mocked runs) | scripted seed | re-provision |

## 2. Manual + automated suites

### SUITE A — Auth & session (P0 coverage; automate first)
1. Login happy (client, admin, ib) → correct landing per role. *(verified this audit)*
2. Login wrong password → generic inline alert, no user enumeration. *(verified)*
3. Login unknown user → identical message. *(verified)*
4. MFA-enabled account → challenge step → wrong code → retry; correct code → in.
5. Session refresh: expire access token, verify silent refresh; kill refresh cookie → `auth:session-expired` → login redirect; verify no retry storm (cooldown).
6. Password rotation: forced flag → `/force-password` gate both directions; weak new password rejected.
7. Logout clears localStorage `_dydx_access_token` + `_dydx_session_established`, cookies expired, back button does not re-enter. *(code-verified; automate)*
8. Registration: policy open/invitation/closed; duplicate email/username; Turnstile enabled vs localhost-disabled.
9. Password reset (once built — FE-UX-01).

### SUITE B — Backtest lifecycle (P0; partially blocked by bot API)
1. Form validation: reversed dates *(verified)*, >2 markets in input mode, zero/negative sizing, empty number fields (NaN guard — currently missing).
2. Submit → disabled button + "Running Backtest…" *(verified)*; double-click cannot double-submit *(code-verified)*.
3. Progress: WS updates; WS drop → HTTP recovery poll ≤8s; completion → results page; **regression test for FE-FN-01** (WS must carry token).
4. Results: metrics render, trade table pagination, CSV export opens clean file.
5. Compare: select 2+ runs, diff table, CSV.

### SUITE C — Bots & runtime (P0 once bot API stable)
1. Create form: masked mnemonic (visual + DOM `type` assertion), testnet checkbox, naming hints.
2. Start/stop/restart/delete each require confirmation dialog (ActionDialog) — assert cancel is a no-op.
3. Runtime stats stream reconnect: kill WS → panel shows reconnecting state (not silent).
4. Bot API down: Bots desk renders, errors humanized (regression for FE-UX-02).

### SUITE D — Roles & portals (P0)
1. client → `/admin`, `/crm/*`, `/ib-portal/*`: UI redirect; **API 403** asserted independently. *(verified manually; automate both sides)*
2. admin in client portal: topbar switch works; client routes render.
3. ib/sub_ib → IB portal surfaces; token management hidden for non-backoffice.
4. Custom-role account (create via DB) → must NOT gain backoffice UI (regression for FE-SEC-03).

### SUITE E — Public & ICO (P1)
1. Landing/pricing/service pages render, nav round-trips, no console errors.
2. ICO countdown ticks; whitelist submit (valid/invalid email); confirm/unsubscribe token links (valid, expired, reused); `/ico/:documentSlug` TOC anchors.
3. Coming-soon gate on/off: unauth sees branded page; `/login`, `/2fa-setup`, `/force-password`, `/ico` remain routable; backend down → fail-open. *(unit tests exist in `publicAccess.test.ts` — keep)*

### SUITE F — Settings & secrets (P1)
1. Profile: avatar upload (type/size rejection), name char-limit, email change.
2. 2FA enable full loop: QR → code → backup codes shown once → login with OTP → recovery code.
3. dYdX keys: masked display, create/rotate/delete with confirmations.
4. Telegram: invalid bot token error surface.

### SUITE G — Accessibility gate (P1; see 13_ACCESSIBILITY_AUDIT)
Keyboard-only pass + axe-core scan per route in CI; label-association assertions for every form field (regression for FE-A11Y-01).

### SUITE H — Visual regression (P2; see 23-note in 18)
Playwright screenshot tests on: landing, login, dashboard (empty + seeded), backtests/new, bots (empty), settings, CRM dashboard, ICO; viewports 375/768/1440; mask clocks/countdowns.

## 3. Negative/environmental matrix per suite

For each automated happy path, add: API 500, API timeout, offline (context.setOffline), slow 3G throttle, back-button mid-flow, refresh mid-flow, double-submit, session expiry mid-flow.

## 4. Defect triage rules

- Money-path regression = P0 regardless of rarity.
- Role-boundary regression = P0 (frontend + backend asserted).
- Console error on load of any route = release blocker (repo standard: qa scripts already fail on console errors — keep).

## 5. Current blockers to executing this plan

1. No Playwright/jsdom/Testing Library installed (Suite automation impossible today).
2. No `npm test` script; CI runs 1/19 files.
3. Bot API instability blocks Suite B/C happy paths locally.
4. No seeded e2e fixtures (need a seed script: users of each role + one completed backtest via mock run).
