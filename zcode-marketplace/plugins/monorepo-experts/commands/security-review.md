---
description: "Threat-focused security review of a scope (default: current diff) — credentials, auth, tenant isolation, and trading-integrity threats"
argument-hint: "[scope]"
skills: trading-security-review
---

Perform a security review of: $ARGUMENTS (default: the current working diff).

Follow the trading-security-review skill checklist, prioritizing:
credential exposure, authn/authz contract breaks, trading-integrity
fail-open paths, injection/leak classes, and environment/config posture.

Prefer dispatching the appsec-specialist subagent for the deep pass.
Static analysis only — never run exploits, never contact exchanges, never
print secret values.

Report: findings by severity (P0/P1/P2) with file:line, attack sketch, and
minimal fix; explicitly list what was NOT reviewed; require tests that fail
before the fix for any security-relevant remediation.
