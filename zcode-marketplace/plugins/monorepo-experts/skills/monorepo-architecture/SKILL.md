---
name: monorepo-architecture
description: "Analyze and change the dydx-trading-bot monorepo cross-service architecture: topology, integration boundaries, dependency direction, config flow, and service routing. Use for any task spanning more than one of bot/, backend/, frontend/, or platform/infra — or when deciding where a change belongs."
---

# Monorepo architecture and dependency analysis

## When to use
- A request touches multiple services or asks "where does X live / who owns Y".
- Reviewing integration-boundary changes (frontend->backend->bot), config-flow
  changes, or new cross-service contracts.

## When NOT to use
- Single-service implementation: use `bot-trading-service`,
  `backend-gateway-service`, or `frontend-dashboard-service` instead.
- Pure CI or migration work: use `ci-release-analysis` / `db-migrations`.

## Procedure
1. Read `references/monorepo-map.md` (relative to this skill's base
   directory; repo copy at
   `zcode-marketplace/plugins/monorepo-experts/references/monorepo-map.md`).
2. Read the specific service profile(s) listed in its routing table for
   every service the task touches.
3. Verify the claimed topology against code before asserting it (e.g., grep
   for direct frontend->bot calls or backend imports of bot code — both are
   boundary violations).
4. Classify the change: contract change (needs lockstep updates),
  single-service, or platform.

## Output
A short architecture note: services touched, direction of change, contract
impact, coordination required (bot/openapi.json + backend delegated routes +
frontend api client), and the exact validation commands per service from the
map's matrix. Distinguish observed facts from inferences.

## Verification
Run the canonical commands for every touched service (map's validation
matrix). For contract changes, confirm all three layers updated in the same
change set. Never claim a command passed without running it.
