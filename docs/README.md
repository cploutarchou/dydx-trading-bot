# Platform Documentation

Wiki-style documentation for the dYdX trading-bot monorepo. Start here, then
follow the links below for the area you are working in.

## Canonical documents

- [Platform Overview](PLATFORM.md) — services, integration boundary, runtime model.
- [Development Workflow](DEVELOPMENT.md) — setup, commands, tests, conventions.
- [Operations Guide](OPERATIONS.md) — running the stack, monitoring, incident notes.
- [CI/CD Strategy](CI_CD_STRATEGY.md) — pipelines, gates, and promotion model.
- [Documentation Governance](DOCUMENTATION_GOVERNANCE.md) — the rules this docs tree follows.
- [Roadmap / Improvements](roadmap/IMPROVEMENTS.md) — tracked improvement work.

## Service documentation

- [Bot service (Python)](../bot/README.md) — trading runtime, API, workers.
- [Backend (Go)](../backend/README.md) — API gateway, PostgreSQL, delegation.
- [Frontend (React)](../frontend/README.md) — dashboard, portals, UX.

## Reference material in this tree

- [Final application improvement plan](FINAL_APPLICATION_IMPROVEMENT_PLAN.md)
- [Final storage & database improvement plan](FINAL_STORAGE_AND_DATABASE_IMPROVEMENT_PLAN.md)
- [Final storage & database validation report](FINAL_STORAGE_AND_DATABASE_VALIDATION_REPORT.md)
- [Implementation progress summary](IMPLEMENTATION_PROGRESS_SUMMARY.md)

## Historical note

An earlier "arbitrage analysis" doc series (current-project-arbitrage-analysis,
project-specific-arbitrage-improvement-plan, codex-final-report,
arbitrage-phase2-rollout-playbook, arbitrage-day1-rollout-command-sheet) was
removed from the repository. The current description of the pairs/arbitrage
stack lives in [`.github/skills/dydx-pairs-arbitrage/SKILL.md`](../.github/skills/dydx-pairs-arbitrage/SKILL.md)
and the code it references.
