---
description: "Review the architecture of a scope (default: the current diff) — boundaries, dependency direction, contract impact, and placement correctness"
argument-hint: "[scope]"
skills: monorepo-architecture, repo-code-review
---

Review the architecture of: $ARGUMENTS (default: the current working diff).

Steps:
1. Read monorepo-map.md and the profiles for every service in scope.
2. Verify boundary rules in the actual code: frontend -> backend -> bot
   only; no layer-skipping calls or imports.
3. Assess: placement (does the change live in the owning service?),
   dependency direction, contract impact (openapi / delegated routes /
   frontend client), config-flow correctness, and coordination required.
4. Prefer dispatching the monorepo-principal-architect or
   dependency-boundary-reviewer subagent for isolated analysis.

Report: verdict, findings with file:line evidence grouped P0-P3,
contract/coordination implications, and the canonical validation commands
the change must pass. Distinguish observed facts from inferences.
