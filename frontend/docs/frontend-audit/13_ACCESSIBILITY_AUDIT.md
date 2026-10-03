# 13 — Accessibility Audit (WCAG 2.2 AA target)

Method: live ARIA-tree inspection of every audited surface (Playwright snapshots), DOM property checks (label association), codebase grep inventory. No screen-reader walkthrough performed (environment limit) — flagged where assumption-based.

## Ranked findings

| Rank | Finding | Evidence | WCAG | Priority |
|---|---|---|---|---|
| 1 | **Financial form fields have no associated labels** — BacktestRunner (Start/End date, Z-Score, Stats Window, USD/Trade, Balance, Fee, Slippage, Rate, Max History) and BotManager (Instance ID, Address, Mnemonic, sizing): visual labels are plain divs; accessible name derives from placeholder only (disappears on input; not programmatically associated). Verified live: `hasLabel:false` on every input of the bot form. Settings profile form DOES label correctly — implementation is inconsistent, not impossible | live DOM check; repo: 96 `placeholder=` vs 29 `htmlFor` | 1.3.1, 3.3.2, 4.1.2 | **P2** |
| 2 | **Multiple `h1` per page** — dashboard renders 3 (sidebar brand "ExecutionLab", banner "Home", main greeting); pattern repeats across desks | live snapshot | 1.3.1 / best practice | P2 |
| 3 | **P&L conveyed by color alone** (+$0 green vs red; up/down deltas in tables) | live dashboard | 1.4.1 | P2 |
| 4 | Unnamed icon buttons: settings camera/avatar button, TanStack devtools (dev-only), some table action buttons render `button:` with empty accessible name | live snapshot | 4.1.2 | P3 |
| 5 | Unnamed search box in Settings (`searchbox "Search…"`) | live snapshot | 4.1.2 | P3 |
| 6 | "Member Since" as disabled textbox (semantics: static text in an editable role) | live settings | 1.3.1 | P3 |
| 7 | Sidebar nav as `<button>` not `<a href>` — no link semantics (route announcement/rotor entry lost; no middle-click — also a UX issue) | live snapshot | 1.3.1/4.1.2 | P3 |
| 8 | No skip-to-content link in workspace shell | code | 2.4.1 | P3 |
| 9 | Login error uses proper `alert` role ✅ but backtest validation error/toast announcement not verified with SR (toast container aria-live assumptions) | code | 4.1.3 | verify |
| 10 | Reduced motion: respected by CryptoBackground (static fallback + tests) ✅; not audited for page transitions/animations elsewhere | `CryptoBackground.test.tsx` | 2.3.3 | verify |

## What is already good (verified)

- Semantic landmarks on every screen: `banner`/`navigation`/`main`/`complementary` present and sensible.
- Login form: real `textbox "Username or email"` naming, `Show password` toggle named, error in `alert` role, disabled-submit-until-valid.
- TOTP inputs: `autocomplete="one-time-code"` + `inputMode=numeric` + digit filtering (Login.tsx:155-168, TwoFactorAuth.tsx:209-222).
- Password fields: correct `current-password`/`new-password` autocomplete everywhere (login/register/force-change/settings) — password-manager friendly; **no paste blocking**.
- Headings hierarchy otherwise logical (h1→h2→h3 within content); descriptive link texts; lists used semantically; tables have header structure where TerminalDataGrid used.
- jsx-a11y lint plugin active; 146 aria-* attributes across app; only 1 clickable-div violation repo-wide.
- Theme pre-paint script avoids flash (helps vestibular sensitivity).

## Remediation plan (ordered)

1. **Field wrapper migration** (`Field` primitive, UI U2.2): fixes finding #1 across all forms; do BacktestRunner + BotManager first (financial + mnemonic fields), then settings panels' stragglers. Est M.
2. **Heading discipline pass**: one `h1` per route (main content); sidebar brand → `p`/`div`; banner page-title stays `h1` only when main lacks one. Est S.
3. **Color-independent P&L**: prefix ▲/▼ or +/- on every delta (formats live in one place after U4.3). Est S.
4. **Name every icon button** (aria-label sweep; add lint rule `jsx-a11y/aria-props`+ manual grep `button:` in snapshots). Est S.
5. **Skip link** in MainLayout + focus-visible ring token (design tokens Step 2). Est S.
6. **Nav buttons → links** with `useNavigate` handlers where extra behavior needed. Est S.
7. Verify toast `aria-live="polite"` + error `role="status"`/`alert` once; add axe-core CI scan (Suite G) so regressions can't land.

## Explicit verification gaps

- No screen-reader (NVDA/VoiceOver) pass — items 9-10 and overall reading order need one SR session after fixes.
- Contrast not machine-measured this round; landing visual review flagged slate-400-on-950 secondary text at small sizes as suspect — run axe contrast audit before token finalization.
