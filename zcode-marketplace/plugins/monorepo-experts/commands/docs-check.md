---
description: "Check documentation and API-contract hygiene for a scope (default: whole repo) under docs-governance rules"
argument-hint: "[scope]"
skills: docs-governance-maintenance
---

Check documentation and contract hygiene for: $ARGUMENTS (default: whole repo).

Steps (per the docs-governance-maintenance skill):
1. Run `make docs-governance` and quote the exact result.
2. Verify the canonical docs tree and that every local link resolves; flag
   absolute machine paths and unarchived temp-named files.
3. For behavior-changing diffs in scope: confirm the owning service's README
   (and `bot/openapi.json` for API changes) are updated in the same change.
4. For API changes: verify the contract triple is consistent (bot openapi,
   backend delegated routes + aliases, frontend client + contractGuards).

Report: governance verdict, findings with file:line, and the minimal fixes
(the docs-contracts-specialist subagent can review them read-only).
