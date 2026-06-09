---
name: testing-and-contracts
description: 'Generate or improve tests for frontend API contracts, normalizers, query hooks, and component data states. Use when writing unit/integration-style tests for regressions in response shapes and runtime behavior.'
argument-hint: 'Provide target file(s), behavior to verify, and the regression/risk to prevent.'
agent: 'API Integration Specialist'
---

Create a focused test plan and implementation for the requested area.

## Output requirements

1. Start with a short risk summary.
2. Propose test cases grouped by behavior:
   - Happy path
   - Contract-shape edge cases
   - Failure and conflict handling
   - Regression guard for known bug
3. Implement tests using current project patterns.
4. Add or update mocks/fixtures with minimal duplication.
5. Include a brief "What this protects" summary.

## Project-specific focus

- Prefer protecting `src/api/contractGuards.ts`, `src/api/normalizers.ts`, and `src/api/hooks.ts` behavior.
- Assert envelope and nested-data handling explicitly.
- For live-data related hooks, verify stale/recovery semantics and no action ping-pong.

## Constraints

- Keep tests deterministic and fast.
- Avoid brittle DOM snapshots unless explicitly requested.
- Do not broaden test surface beyond requested risk boundary.
