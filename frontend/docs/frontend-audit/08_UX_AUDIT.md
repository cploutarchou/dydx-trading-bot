# 08 — UX Audit

Sources: live walkthrough of every major client/backoffice surface (2026-09-04), visual reviews at 1440/375, code inspection of flows not executable locally. Format per issue: Problem · Why it matters · Affected users · Severity · Solution · Benefit · Difficulty.

---

### UX-01 · No self-serve password reset — **P2** (P1 by user impact, constrained by backend dependency)
"Account recovery" on `/login` is a `mailto:support@executionlab.io` prefilled link.
**Why:** the single most common account problem becomes a support ticket with ≥hours latency; unacceptable for a product holding trading credentials.
**Users:** all, at worst moment (locked out).
**Solution:** email-token reset flow (request → emailed link → new password → invalidate sessions). Frontend: 2 screens + route; backend: token issuance endpoints.
**Benefit:** removes the #1 support burden; industry baseline. **Difficulty:** M (frontend S + backend M).

### UX-02 · Raw technical errors shown to operators — **P2**
Bots desk Arbitrage panel rendered `"Request failed with status code 502"` verbatim (live observation).
**Why:** operators can't act on axios strings; erodes trust in a control room.
**Solution:** centralized error→human mapper (status+endpoint → operator sentence + next step), reuse `InlineNotice`; keep trace ID visible for support.
**Benefit:** every degraded surface becomes actionable. **Difficulty:** S.

### UX-03 · Theme control offers a dead option — **P2**
Theme combobox renders `Light [disabled]` in the header of every page (live) while `FORCE_DARK_THEME` forces dark (`uiPreferences.ts:18`).
**Why:** a visible-but-disabled control reads as broken; contradicts README's "Light, Dark, and System" claim.
**Solution:** either hide the option until light mode ships, or complete light-mode enablement (~5,600 lines of light CSS already exist).
**Benefit:** removes a small daily "why?" on every page. **Difficulty:** XS (hide) / M (ship light).

### UX-04 · Backtest defaults frozen in 2024 — **P2**
Form + summary card default `2024-01-01 → 2024-03-31` (`BacktestRunner.tsx:110-111`), 2.5 years stale.
**Why:** users who don't change dates backtest a stale regime and may trust the results; silent research-quality hazard.
**Solution:** default to trailing window (e.g. last 90 days) computed at mount; keep explicit presets.
**Benefit:** every default run reflects recent market structure. **Difficulty:** XS.

### UX-05 · Dead admin link — **P2**
AdminHub "Open Settings" → `/settings` in backoffice portal silently lands on `/dashboard` (live).
**Why:** navigation that lies destroys the operator's mental model.
**Solution:** point at `/admin/settings` (registered backoffice route) or remove the tile.
**Benefit:** trust in chrome. **Difficulty:** XS.

### UX-06 · Silent portal redirects — **P3**
Client hitting `/admin` lands on `/dashboard` with zero explanation (live).
**Solution:** toast "Client accounts use the Client Portal — redirecting to your dashboard." **Difficulty:** XS.

### UX-07 · Zero P&L presented as gain — **P3**
Dashboard renders `+$0` in profit green (live). **Solution:** neutral gray for exactly-zero. **Difficulty:** XS.

### UX-08 · Truncated identity — **P3**
Sidebar shows `Signed in as auditcli…` truncation without tooltip/full name (visual review).
**Solution:** title attr + full_name preference display. **Difficulty:** XS.

### UX-09 · Duplicate market-overview fetch on Market Intel — **P2** (perf-UX)
Two identical `/codex/market/overview` calls on mount (live) — slower first paint of data, doubled 503 noise.
**Solution:** shared query key via `queryKeys` factory for that hook's two consumers. **Difficulty:** S.

### UX-10 · Command palette & workflow guidance — **strength**
Command palette (⌘K) with route search, numbered workflow rails (Research→Strategy→Backtest→Deploy→Monitor), per-page purpose headers, and step-checklists (Client Area, Backtests/new) are genuinely good operator UX — keep and extend.

### UX-11 · Empty states — **strength, one gap**
Empty states consistently pair status + guidance + CTA (dashboard, bots, backtests, CRM). Gap: a few lists flash empty state before load completes (no skeleton) — add skeletons where fetch latency is visible.

### UX-12 · Onboarding — **P3**
First login lands on an empty-but-guided dashboard; Client Area carries the narrative. Gap: no dismissible "first run" tour tying the four steps to links; new users must discover Client Area themselves.
**Solution:** reuse Client Area content as a 4-step checklist card on dashboard until first completed backtest. **Difficulty:** S.

### UX-13 · Terminology consistency — **P3**
Mostly disciplined ("runtime", "validation run", "desk"). Stray mixing: "Bots" vs "runtimes" vs "instances" vs "managed strategy runtimes" across sidebar/desks. One glossary pass on nav + page headers. **Difficulty:** S.

### UX-14 · Mobile operator UX — **P3**
Nav drawer works at 375 (visual review); KPI strip squeezes to 2-up with cramped labels; tables (Backtest runs) rely on horizontal scroll (acceptable terminal pattern) — add scroll-shadow affordance. **Difficulty:** S.
