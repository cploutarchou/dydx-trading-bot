---
name: docs-governance-maintenance
description: Maintain this monorepo's documentation and API contracts under the docs-governance rules — canonical docs tree, link validation, README sync, and openapi contract updates. Use when changing behavior docs, fixing docs-governance failures, or updating API contracts.
---

# Documentation and contract maintenance

## When to use
- Docs changes anywhere governed by `make docs-governance`; behavior-change
  PRs that must update docs in-commit; API contract updates
  (`bot/openapi.json` + backend routes + frontend client).

## When NOT to use
- CI workflow internals (`ci-release-analysis`).

## Rules
- Read `docs/DOCUMENTATION_GOVERNANCE.md` (the enforced policy) and
  `references/monorepo-map.md` for the routing table.
- Canonical tree: `docs/{README,PLATFORM,DEVELOPMENT,OPERATIONS,CI_CD_STRATEGY,DOCUMENTATION_GOVERNANCE}.md`,
  `docs/roadmap/IMPROVEMENTS.md`, service READMEs. Links must resolve;
  no absolute local paths; temp/handoff-named files belong under
  `docs/archive/`.
- Behavior changes update the owning service's README (+ `bot/openapi.json`
  for API changes) in the same commit.
- Never document intent the code doesn't implement; remove links to removed
  features rather than leaving them dangling.

## Output
Changed docs + the governance run result. For contracts: the three-layer
lockstep list (bot spec, backend delegated routes, frontend client/tests).

## Verification
```
make docs-governance
```
Quote the result. For API changes, also run frontend contract tests.
