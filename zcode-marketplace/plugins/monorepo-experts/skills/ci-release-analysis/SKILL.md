---
name: ci-release-analysis
description: Analyze and safely change CI/CD for this monorepo — the bot-quality gate, container images, local-dev validation, coverage/ratchet policies, and image release conventions. Use for workflow changes, CI failures, gate policy questions, or release-path analysis.
---

# CI/CD and release analysis

## When to use
- Changing anything under `.github/workflows/`; diagnosing a CI failure;
  gate/ratchet policy questions; image build/release questions.

## When NOT to use
- Application code (service skills); docs-tree governance
  (`docs-governance-maintenance`).

## Rules
- Read `references/ci-release.md` first, plus
  `.github/instructions/workflow-yaml.instructions.md`.
- Jobs stay hermetic (`APP_RUN_CONFIG_FILE` + `.ci-run.json`); no runner
  access to `.configkey.bin`.
- Blocking vs reporting must be explicit (`continue-on-error` + promotion
  note). Ratchets only tighten.
- Trigger paths must cover every scope the jobs validate.
- CI never deploys.

## Output
For failures: the failing job, first real error in the log, root cause,
fix. For changes: job-by-job diff summary, gating implications, and the
exact workflow YAML validation performed (parse + job graph).

## Verification
Validate YAML parses, jobs/needs graph is acyclic, and (for behavior
changes) the equivalent local commands pass. State clearly that full CI
verification happens on push.
