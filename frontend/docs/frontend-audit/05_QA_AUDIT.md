# 05 — QA Audit (functional, browser-verified)

Every ✅/❌ below was observed in the running application (client portal 5173, backoffice 5174, backend 8888, infra up) unless marked *(code-verified)*. The Python bot API was down during the session, so bot-dependent flows were exercised in their **degraded** states — which is itself part of the audit.

## Journey coverage

| Flow | Happy | Negative | Degraded/error | Verdict |
|---|---|---|---|---|
| Public landing → nav → pricing/services | ✅ | — | — | Pass |
| Login (client) | ✅ → `/dashboard` | ✅ wrong creds → inline `alert` "Unable to sign in…" (generic, no user enumeration) + button disabled until valid | not tested (backend up) | Pass |
| Login (admin, backoffice portal) | ✅ → `/admin` AdminHub | — | — | Pass |
| Registration | ✅ via API (policy open, Turnstile self-disables on localhost) | account-exists → `"User already exists"` | browser form not walked (see blockers) | Pass (partial) |
| Session restore / refresh | ✅ reload keeps session (cookie restore path) | — | — | Pass |
| Role boundary | client → `/admin` URL: silently lands `/dashboard` (guard works; UX choice debatable) | API-level: client token gets **403** on admin + settings endpoints (verified) | — | Pass (backend enforces) |
| Dashboard empty state | ✅ full empty-state coverage with CTAs | — | — | Pass |
| Backtest form validation | ✅ presets, mode combobox, spinbuttons | ✅ reversed date range → inline error + toast (verified after re-test; first click during re-render was swallowed) | ✅ bot API down: markets picker disabled with explicit reason + static-fallback warning | Pass |
| Backtest run → live progress → results | ⚠️ not executable (bot API down) | — | WS builders verified in code; FE-FN-01 stale token key undermines this page's WS auth | **Blocked** |
| Bots desk | ✅ stats, operator notes, empty instance list | — | ✅ Arbitrage panel surfaces **raw axios string** `"Request failed with status code 502"` (FE-UX-02) | Partial pass |
| Bot create form | ✅ renders; mnemonic masked (`type="password"` verified in DOM) | not submitted (bot API down) | — | Partial pass |
| Settings (profile) | ✅ accessible labels, char counter, read-only username | — | — | Pass |
| Client Area onboarding | ✅ guided next steps with role-aware links | — | — | Pass |
| Market Intel | ✅ renders | — | Codex upstream 503 → graceful; **duplicate request** fired (FE-FN-02) | Pass w/ finding |
| Logout | code-verified (token + cookies + store cleared, `api.ts:2159-2187`) | — | — | Pass (code) |
| Backoffice AdminHub | ✅ counters, fast access | ❌ **"Open Settings" link → `/settings` redirects to `/dashboard`** — dead link in backoffice portal (FE-UX-05) | bot gateway counters show 0/20 success while bot API down (accurate) | Finding |

## Functional findings register

| ID | Finding | Evidence | Priority |
|---|---|---|---|
| FE-FN-01 | Stale `token` localStorage key → unauthenticated live-progress WS on Backtests page | `Backtests.tsx:710` | **P1** |
| FE-UX-02 | Raw axios error strings rendered to operators ("Request failed with status code 502") | Bots desk Arbitrage panel (live) | P2 |
| FE-UX-04 | Backtest window defaults to 2024-01-01→2024-03-31 | form + summary card (live); `BacktestRunner.tsx:110-111` | P2 |
| FE-UX-05 | AdminHub "Open Settings" dead in backoffice portal (redirects home) | live on 5174 | P2 |
| FE-FN-02 | Duplicate `/codex/market/overview` request on Market Intel | performance entries (live, ×2, both 503) | P2 |
| FE-FN-05 | First-click submit on BacktestRunner can be swallowed during re-render (validation did not fire on first attempt; fired on immediate re-click) | live observation | P3 (needs reproduction; likely transient) |
| FE-UX-08 | Wrong-portal access redirects silently (client `/admin` → `/dashboard`, no explanation) | live | P3 |

## Fintech-specific behaviour (Phase-10 lens)

| Risk | Status | Evidence |
|---|---|---|
| Duplicate submission of money-affecting forms | ✅ Protected | BacktestRunner `disabled={loading \|\| isPending}` + "Running Backtest…" (`BacktestRunner.tsx:1028-1036`); BotManager `disabled={isCreating}` + "Creating…" (`BotManager.tsx:1143-1150`) |
| Destructive action confirmation | ✅ (code) | `ActionDialog` confirmation pattern; risky mutations use it (README contract; `PlatformUI.tsx`) |
| Mnemonic/secret handling | ⚠️ Inconsistent | BotManager masks ✅ (live DOM check); **DYDXKeyManager uses a visible `<textarea>`** (`DYDXKeyManager.tsx:354-364`) — P3 |
| Number precision | ✅ Display-layer only | floats/`toFixed` for display; backend owns decimal math (`backtest_money_numeric` migrations) |
| Ambiguous status semantics | ⚠️ Minor | `+$0` P&L rendered green (dashboard, live); stale/fresh cues exist on active runs |
| Stale balances | n/a | No fiat balance UI; portfolio P&L derived from completed runs |
| Hidden fees | ✅ Explicit | fee/slippage inputs surfaced in backtest form with "Before you launch" summary |
| Misleading success | ✅ None found | "started but no run ID" handled with explicit warning (`BacktestRunner.tsx:496`) |
| KYC/documents/payments | n/a | No fiat payment flows exist; ICO whitelist is email-based |

## Error handling & resilience (Phase-19 lens)

- **Backend 502/503 (bot API down):** inline operator-readable reason on backtest markets picker ✅; raw string leak on Bots Arbitrage panel ❌; AdminHub gateway counters reflect failures ✅.
- **Codex 503:** panel degrades without layout breakage ✅.
- **401 lifecycle:** single-flight refresh + queue + 10s cooldown; session-expired event → controlled logout; refresh-warning toast; cannot loop (verified logic `api.ts:1818-1952`).
- **Render crash:** single global ErrorBoundary, **no per-route `errorElement`** — one crash blanks the app (P2, `App.tsx:262`).
- **Offline/not-found:** catchall `*` → `/unauthorized`; not tested offline (P3 gap in this audit).

## Browser compatibility

Browserslist: Firefox ≥110, Chrome ≥111, Safari ≥16.4, Edge ≥111. This audit ran Chromium only. The repo's own responsive script (Chrome CLI + raw CDP) targets Chrome/Edge. **No cross-browser evidence exists anywhere in the repo** — see `17_BROWSER_COMPATIBILITY.md`.

## Test-matrix verdict for this environment

What **can** be safely regression-tested locally today: login/MFA, registration policy, role boundaries, settings, CRM/IB read surfaces, backtest form validation (blocked at submit). What cannot: real backtest execution, live WS progress, bot lifecycle (all require a healthy bot API + worker).
