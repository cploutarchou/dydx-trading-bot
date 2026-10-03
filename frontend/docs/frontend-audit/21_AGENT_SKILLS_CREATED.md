# 21 — Agent Skills / Audit Roles Used

## Decision: no new repo agent files created

The task allowed creating dedicated agent/skill definitions. This audit deliberately **did not** add any, per the instruction "only create agents/skills that provide real value; do not create unnecessary agent bureaucracy":

- The repo already defines implementation-time standards in `frontend/.github/agents/senior-react-defi-product.agent.md` (+ its mandatory `senior-ux-designer` and `frontend-live-data-safety` skills) and root `.github/agents/senior-defi-monorepo-platform.agent.md`. Adding parallel audit personas would duplicate that governance.
- Audit-time roles were executed as **ephemeral specialized subagents** (single-purpose, results merged into these documents):

| Role (ephemeral) | Coverage delivered | Output merged into |
|---|---|---|
| Frontend Architecture Reviewer | 15-point architecture map, route/portal inventory, dead-code cluster, dual-API finding | 02, 04 |
| Static Code Quality Auditor | 62k-LOC metric sweep, hotspots, duplication, storage/React issues, deps | 04 |
| Test/QA Infrastructure Auditor | 19-file test inventory, CI gate analysis, QA scripts, stale-evidence finding | 18, 05, 14 |
| Client-Side Security Reviewer | 15-area security pass with confirmed-clean list | 16 |
| Browser/QA Engineer (main session) | Live authenticated walkthrough, forms, role probes, responsive, perf samples | 05, 06, 07, 13, 14, 15 |

## Recommended future additions (only when implementation begins)

1. **`.github/agents/frontend-qa-regression.agent.md`** — *after* Stage 1 of the roadmap lands (Playwright exists). Purpose: run the E2E waves, triage failures, keep `07_E2E_TEST_MATRIX.md` row-status current. Not useful before tests exist.
2. **`.github/skills/frontend-contract-guards/SKILL.md`** — when adding endpoints: the 8-step "types → client method → hook → queryKey → contract guard → E2E row" checklist. Real value because contract guards are the cheapest regression layer here.
3. **A11y gate snippet** inside the existing senior-react-defi-product agent (axe-scan + `getByLabelText` rule) rather than a new agent — extends the file the team already loads.

Each addition should be created at the moment its consumer workflow exists, not before.
