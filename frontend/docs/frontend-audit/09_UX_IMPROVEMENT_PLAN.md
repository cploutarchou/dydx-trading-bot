# 09 — UX Improvement Plan

Sequenced, dependency-aware. Each item links to the audit finding in `08_UX_AUDIT.md`. Estimates: XS <½d · S ~1d · M multi-day.

## Wave 1 — Truth-telling fixes (no new features)

| # | Change | Finding | Est | Depends on |
|---|---|---|---|---|
| 1.1 | Error-normalization util (`humanizeApiError(status, url)` → sentence + traceID) applied to Bots Arbitrage panel, markets picker, Codex, CRM surfaces | UX-02 | S | none |
| 1.2 | Backtest default window = trailing 90 days at mount | UX-04 | XS | none |
| 1.3 | AdminHub "Open Settings" → `/admin/settings` | UX-05 | XS | none |
| 1.4 | Hide disabled "Light" theme option (until light ships) | UX-03 | XS | decision: light-mode roadmap |
| 1.5 | Neutral rendering for exactly-zero P&L | UX-07 | XS | none |
| 1.6 | Redirect toast on wrong-portal navigation | UX-06 | XS | none |
| 1.7 | Sidebar identity tooltip + full_name display | UX-08 | XS | none |
| 1.8 | Dedupe Market Intel market-overview query key | UX-09 | S | none |

**Exit criteria:** no axios-string in any operator surface; zero stale-date defaults; no dead nav links anywhere in backoffice.

## Wave 2 — Account self-sufficiency

| # | Change | Finding | Est | Depends on |
|---|---|---|---|---|
| 2.1 | Password-reset request screen + route `/forgot-password` | UX-01 | S | backend token endpoints |
| 2.2 | Reset-confirm screen `/reset-password/:token` (expired/reused token states) | UX-01 | S | 2.1 |
| 2.3 | Replace `mailto:` recovery link with flow entry; keep mailto as fallback | UX-01 | XS | 2.1 |
| 2.4 | Login page messaging for `locked_until` (backend has lockout — surface remaining time) | new | S | backend field in `/me` |

## Wave 3 — Operator flow polish

| # | Change | Finding | Est | Depends on |
|---|---|---|---|---|
| 3.1 | First-run dashboard checklist (4 steps reused from Client Area, dismissible, completes on first backtest) | UX-12 | S | none |
| 3.2 | Skeleton loaders for lists with visible fetch latency (backtest runs, CRM clients, IB network) | UX-11 | S | none |
| 3.3 | Terminology pass: standardize on "runtime (bot)" in nav/headers; glossary note in Client Area | UX-13 | S | copy review |
| 3.4 | Mobile: 1-col KPI wrap <400px; scroll-shadow on wide tables | UX-14 | S | none |
| 3.5 | Session-expiry grace: `auth:refresh-warning` toast already exists — add "Save your work" copy + retry-now action | resilience | S | none |

## Wave 4 — Bigger bets (post-Stage-2, decide with product)

- **Light mode completion** (~5,600 CSS lines exist; ThemeToggle already structured) — unlocks the System theme promise; M; verify contrast per 13_ACCESSIBILITY_AUDIT.
- **Guided backtest wizard** — the single-page form is information-dense (13+ fields); a 3-step wizard (window → universe → assumptions) matches the "Before you launch" pattern; M; only if new-user drop-off shows form abandonment.
- **Notification center** — alerts currently scattered (dashboard "Needs Attention", toasts, Telegram); a unified inbox surface; L; needs backend events contract.

## Explicitly NOT recommended

- Rewriting navigation or chrome (current shell is coherent and fast to learn).
- Adding a tour framework (checklist card covers the need with less code).
- More confirmation dialogs — confirmation coverage is already right; add only where money moves (already there).

## Success metrics

- Support tickets tagged "login/reset" → ~0 after Wave 2.
- Rage-click / dead-click rate on Bots desk error areas → 0 after Wave 1.1.
- New-user → first-backtest-run conversion (post Wave 3.1) — measurable once telemetry exists (see 25/Observability section in 18).
