---
name: test-diagnosis
description: Select the right tests and diagnose failures across the dydx-trading-bot monorepo (bot pytest, backend go test -race, frontend vitest contracts), including hermetic-suite pitfalls and flaky-class identification. Use when choosing tests for a change or debugging a red test/CI job.
---

# Test selection and failure diagnosis

## When to use
- Deciding what to run for a change; diagnosing a failing test or CI job.

## When NOT to use
- Writing the feature itself (service skills); CI workflow changes
  (`ci-release-analysis`).

## Test-selection heuristics (per service profile)
- bot: files touching `src/trading/**` -> `tests/test_*trading*`,
  `test_*exit*`, `test_*abort*`, `test_bot_agent*`; backtest engine ->
  `test_backtest_*`; plus the full gate before handoff (coverage floor 82).
- backend: route/middleware changes -> the matching `*_test.go` in
  `internal/routes` (sqlite-backed contracts); always `go test -race ./...`
  before handoff.
- frontend: any `src/api/**` change -> `npm run test:contracts`; UI changes
  -> lint + typecheck minimum.

## Failure-diagnosis procedure
1. Reproduce narrowly (`pytest tests/<file>::<test> -q`, `go test ./<pkg>/ -run <Name>`).
2. Classify: real regression, environment coupling, or flaky/racy.
   Known coupling traps: structured-config env leakage (all alias gates must
   be cleared in tests), local infra leaking into suites (conftest
   hermeticity is load-bearing), sqlite-vs-postgres dialect drift,
   `BacktestRepository` session across threads, timing-dependent exit tests.
3. For CI-only failures: compare runner env (hermetic `.ci-run.json`, no
   `.configkey.bin`) against local; read the job log for the first real
   traceback before the noise.
4. Fix the root cause; never weaken, skip, or delete the test. Ratchet
   baselines change only with documented justification.

## Output
Root cause, evidence (command + traceback lines), fix, and the exact
re-run commands with their real results.

## Verification
Re-run the narrow test AND the service's full gate; quote both results.
