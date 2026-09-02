---
description: "Build the test plan for a scope (default: current diff) — which suites to run per service, which new tests to write, and known flaky/coupling traps"
argument-hint: "[scope]"
skills: test-diagnosis
---

Produce a test plan for: $ARGUMENTS (default: the current working diff).

Follow the test-diagnosis skill:
1. Map each changed file to its service and the existing suites that pin its
   behavior (list exact test files/tests).
2. List new tests required (including negative/failure paths) and which
   should fail before the fix.
3. Note service-specific traps from the profiles (env leakage, infra
   coupling, session thread-safety, dialect drift).
4. Give the exact verification commands per service, in run order, ending
   with each service's full gate.

Keep it actionable: a maintainer should be able to execute the plan verbatim.
