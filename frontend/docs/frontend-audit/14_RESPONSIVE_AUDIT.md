# 14 — Responsive Audit

Method: live browser measurement at 320/375/1440 (+ visual review at 375 and 1440) on the highest-risk surfaces; code review of the class system. Repo's own QA docs (`docs/RESPONSIVE_QA_STATUS.md` etc.) were cross-checked — **their checklists claim all captures done, but `docs/screenshots/` does not exist; treat prior sign-off as stale.**

## Measured results (this audit)

| Page | 320px | 375px | 1440px | Notes |
|---|---|---|---|---|
| Dashboard | ✅ no h-scroll (scrollWidth 320) | ✅ (375) | ✅ | KPI 2-up squeeze + label crowding at 375 (visual) |
| Backtests/new (form-heavy) | ✅ no h-scroll | ✅ | ✅ | long form scrolls vertically; controls stay usable |
| Landing | — | ✅ (visual) | ✅ (visual) | hero/nav fine; contrast note |
| Login | — | ✅ | ✅ | single-column, focus order fine |

Overflow probes found only decorative background SVGs extending past viewport (clipped, `overflow:hidden` container) — harmless.

## Findings

| ID | Finding | Priority |
|---|---|---|
| R-1 | KPI strips force 2-up below ~400px → squeezed labels/values (visual review at 375) | P3 |
| R-2 | Wide tables (backtest runs, CRM clients) rely on bare horizontal scroll with no affordance | P3 |
| R-3 | Sidebar occupies ~88% of 375px viewport when drawer opens (visual) — acceptable drawer, but ensure overlay tap-out + Esc close are wired (verify in fix pass) | P3 |
| R-4 | Long operator descriptions under nav items inflate chrome height at small widths | P3 |
| R-5 | No evidence of 768-specific review in this session beyond structure (tablet pass owed when screenshot suite lands) | gap |
| R-6 | Prior responsive sign-off docs are stale/false-positive (all `[x]`, zero PNGs) — process finding, not layout | P2 (process) |

## Verdict

Layout-level responsiveness is genuinely solid (320px without overflow on the worst page is above average). Remaining issues are polish (R-1/R-2/R-4) and process (R-6), not breakage.

## Remediation

1. Re-baseline evidence: run `npm run qa:screenshots:capture` (needs Chrome on PATH; authenticated routes need `--user-data-dir` per playbook) or the new Playwright screenshot suite at 320/375/768/1440; commit PNGs under `docs/screenshots/responsive/` and make `qa:screenshots:sync` CI-honest (checklist from files, as designed).
2. U1.5/U1.6/U1.7 from the UI plan cover R-1/R-2/R-4.
3. Add a tablet (768) visual pass to Suite H; mask dynamic clocks.
