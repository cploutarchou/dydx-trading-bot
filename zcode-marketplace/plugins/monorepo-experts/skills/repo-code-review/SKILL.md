---
name: repo-code-review
description: Repository-aware code review for the dydx-trading-bot monorepo — routing each diff to its service's contracts, safety rules, and test obligations. Use when reviewing a diff, PR, or proposed change anywhere in this repo.
---

# Repository-aware code review

## When to use
- Reviewing any diff/PR/patch in this repository.

## When NOT to use
- Implementing the change itself (use the service skills); standalone
  security audits (`trading-security-review`).

## Procedure
1. Read `references/monorepo-map.md`; then the profile for every service the
   diff touches.
2. Route each hunk: does it preserve that service's invariants?
   - bot: fail-closed order/position paths, emergency cleanup, atomic pairs,
     no thread-hopping repository sessions, no blocking I/O in async paths.
   - backend: auth contracts intact, generic errors, parameterized SQL,
     ownership/quota gates.
   - frontend: api-client-only HTTP, contract guards updated, zero warnings.
   - infra/CI: hermetic jobs, no secrets, trigger paths match validated scope.
3. Demand tests: every behavior change needs a test that fails without it.
4. Check for unrelated refactoring, weakened assertions, skipped tests,
   generated-file edits, and secret-shaped strings.

## Output
Verdict (approve / request changes with blocking items), findings grouped by
severity (P0 loss/credential/uncontrolled-trading; P1 incorrect
orders/positions/risk/security; P2 reliability; P3 minor), each with
file:line evidence and the minimal fix. List what you verified vs. assumed.

## Verification
Do not approve until the touched services' canonical commands are quoted as
passing (or explicitly marked unrun with residual risk stated).
