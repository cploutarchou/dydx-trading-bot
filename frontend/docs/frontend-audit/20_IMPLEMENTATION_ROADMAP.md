# 20 — Implementation Roadmap

Sequencing follows the repo's own value order (correctness > security > clarity > reliability > a11y > perf > aesthetics). Each stage is independently shippable; gates define done.

## Stage 0 — Unblock (½ day)
- **FE-005** backend run.json pool clamp (BE PR) + regenerate dev profile.
- Re-verify `LOCAL_SETUP_GUIDE.md` cold-start end-to-end.
**Gate:** fresh checkout → `make infra-up && cd backend && make run` works with zero hand-edits.

## Stage 1 — Correctness & security P1s (2–4 days)
1. FE-001 stale token key (XS) + regression note in backtest progress test.
2. FE-004 test foundation in parallel: `npm test` script + all 19 files in CI + jsdom/Testing Library installed + Playwright scaffolding with auth fixtures (Wave-1 rows green: login, guards, backtest form validation).
3. FE-002/003 token posture: confirm backend cookie-session on WS handshake → drop localStorage JWT + URL token (behind a staged rollout flag if backend needs transition).
**Gate:** E2E Wave-1 green in CI on every PR; no `access_token` in any outbound URL; no JWT in localStorage after login.

## Stage 2 — UX truth-telling + quick wins (1–2 days)
- FE-010 error humanizer, FE-011 date defaults, FE-012 dead link, FE-013 hide Light option, FE-014 dedupe query, FE-025 mobile KPI/table affordances, FE-031 micro-UX batch.
**Gate:** zero axios-strings in UI (grep + visual); defaults reflect trailing window.

## Stage 3 — Forms & a11y (3–5 days, after DS tokens Step 1–2)
- FE-006 Field primitive + migrate BacktestRunner/BotManager/Settings stragglers; FE-007 h1 discipline; FE-008 P&L icons; FE-030 naming/skip-link batch; axe-core CI scan (Suite G).
**Gate:** every form field `getByLabelText`-addressable in component tests; axe critical=0 on canonical routes.

## Stage 4 — Security hardening & resilience (2–3 days; BE coordination)
- FE-017 fail-closed roleMatches; FE-018 CSP/referrer/frame (meta+server); FE-019 CSRF posture verification + doc; FE-020 per-route errorElement; FE-026..029 P3 security batch.
**Gate:** unknown-role fixture gets no backoffice UI; route-crash demo renders in-place error page; security review sign-off on headers.

## Stage 5 — Hygiene & perf (2–3 days)
- FE-016 delete dead cluster → FE-021 dep removal; FE-022 shared formatters (+tests); FE-023 finish React Query migration (11 files); FE-032 bundle trims; FE-033 config cleanups (StrictMode flip early here).
**Gate:** bundle initial JS down ≥15%; `grep recharts|framer-motion` zero; lint/format single-config.

## Stage 6 — Test automation scale-up (3–5 days, can start after Stage 1)
- E2E Wave-2 (MFA, 2FA loop, settings, ICO, CRM/IB read paths) + `@botapi` job when bot API stable; 3-browser smoke; visual regression suite replacing stale checklists (FE-024); contract-guard expansion.
**Gate:** matrix rows 1–8, 11, 13-form, 15, 19–23 automated; screenshots committed and synced by CI.

## Stage 7 — Architecture consolidation (1–2 weeks, feature-frozen window)
- FE-015 single API client (keep axios core; port enhancedClient methods; delete fetch stack + shims) with contract guards as the safety net; component/Button/Panel/Table primitive completion (UI U2); optional light-mode ship (FE-013 full) behind contrast audit.
**Gate:** one HTTP client; `api/client.ts` deleted; U2 component count migrated ≥80%; no behavior regressions in Stage-6 suites.

## Explicitly deferred / needs product decision
- Password reset (FE-009) — sized, blocked on backend tokens; schedule with backend team.
- i18n scope decision (FE-034).
- Observability beacon (FE-037) — after Stage 6, opt-out, no PII.
- Notification center, guided wizard (UX Wave-4).

## Risk notes
- FE-002/003 touch auth for every socket+request — do behind Stage-1 tests only; coordinate backend WS handshake first.
- FE-015 is the only XL-adjacent item; contract guards + E2E are prerequisites, not niceties.
- Bot-API-dependent test rows stay tagged until the bot API migration-exit bug is fixed upstream.
