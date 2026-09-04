# 07 — E2E Test Matrix

Target stack: **Playwright** (not installed yet — this matrix is the implementation contract). Priority reflects money-path risk. "Auth" column: ✅ = achievable with current local stack; 🔧 = needs seed fixture; 🚫 = needs healthy bot API.

| # | Flow | Priority | Happy | Negative | Mobile | API failure | Permissions | Feasibility |
|---|---|---|---|---|---|---|---|---|
| 1 | Login (client) | P0 | Yes | Yes | Yes | Yes (500/timeout) | N/A | ✅ verified manually |
| 2 | Login (admin → backoffice) | P0 | Yes | Yes | Yes | Yes | Yes (client blocked) | ✅ |
| 3 | MFA challenge + backup code | P0 | Yes | wrong code | Yes | Yes | N/A | 🔧 |
| 4 | Forced password rotation | P0 | Yes | weak pw | Yes | Yes | N/A | 🔧 |
| 5 | Logout + back-button lockout | P0 | Yes | — | Yes | — | N/A | ✅ |
| 6 | Session expiry mid-app | P0 | re-login prompt | — | — | refresh 500 | N/A | 🔧 |
| 7 | Registration (open policy) | P1 | Yes | dup email, bad pw | Yes | Yes | invitation mode | ✅ |
| 8 | Backtest form validation | P0 | presets apply | reversed dates *(verified)*, <2 markets | Yes | markets 503 → fallback notice | client only | ✅ |
| 9 | Backtest submit → progress → results | P0 | Yes | double-submit blocked | Yes | WS drop → poll fallback | client only | 🚫 |
| 10 | Backtest compare + CSV | P1 | Yes | 1-run selection | table scroll | Yes | client only | 🔧 |
| 11 | Strategy create/edit/delete | P1 | Yes | invalid risk params (NaN guard — add first) | Yes | Yes | client only | ✅ |
| 12 | Strategy → runtime start/stop (managed) | P1 | Yes | stop needs confirm | Yes | Yes | client only | 🚫 |
| 13 | Bot create (mnemonic masked) | P0 | DOM asserts `type=password` | double-submit | Yes | Yes | client only | 🚫 submit / ✅ form |
| 14 | Bot start/stop/restart/delete confirmations | P0 | ActionDialog | cancel = no-op | Yes | Yes | owner only | 🚫 |
| 15 | Role boundary sweep | P0 | — | client hits `/admin`,`/crm`,`/ib-portal` → redirected; **API 403 asserted** | — | — | Yes | ✅ |
| 16 | AdminHub → CRM client detail → status change | P1 | Yes | invalid transition | Yes | Yes | backoffice roles | 🔧 |
| 17 | Admin settings mutation (coming-soon toggle) | P1 | Yes | — | — | Yes | admin only (403 otherwise) | 🔧 |
| 18 | IB portal: dashboard + commissions | P1 | Yes | — | Yes | Yes | ib/sub_ib | 🔧 |
| 19 | ICO whitelist submit + email token actions | P1 | Yes | bad email, reused/expired token | Yes | Yes | public | ✅ |
| 20 | Public site tour (landing→services→pricing) | P2 | Yes | 404 slug | Yes | — | public | ✅ |
| 21 | Settings: profile save + avatar | P1 | Yes | oversize file, wrong MIME | Yes | Yes | authed | ✅ |
| 22 | Settings: 2FA enable full loop | P0 | Yes | wrong TOTP | Yes | Yes | authed | 🔧 |
| 23 | dYdX key create/rotate/delete | P0 | masked display | delete confirm | Yes | Yes | owner | 🔧 |
| 24 | Theme toggle (dark/system) | P3 | persists | light disabled | — | — | authed | ✅ |
| 25 | Command palette navigation | P2 | open, search, go | — | — | — | authed | ✅ |

## Automation notes

- **Auth reuse:** Playwright `storageState` from a post-login fixture; three role fixtures (client/admin/ib).
- **API failure injection:** `page.route('**/api/v1/**', ...)` for 500/timeout/offline — no backend chaos needed.
- **Bot-API-dependent rows (9,12,14):** gate behind a `@botapi` tag + CI job that starts the full stack; run form-level variants everywhere.
- **Money-path assertions:** after any submit action, assert exactly one network call fired (regression for duplicate submission) and button entered disabled state.
- **A11y:** append `axe-playwright` scan to rows 1,8,11,13,21 — fails on critical violations only (see 13_ACCESSIBILITY_AUDIT).
- **Visual:** rows 1,8,20 (+ seeded dashboard) get screenshot assertions at 375/1440 with clock/countdown masks.

## What exists today vs this matrix

19 Vitest unit/contract files cover fragments of rows 1,7,8,15,19 (pure helpers only — no DOM). Zero rows are automated end-to-end. The highest-value first wave: rows 1, 2, 5, 8, 15, 13-form, 21 (all ✅-feasible without the bot API).
