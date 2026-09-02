---
name: trading-security-review
description: Threat-focused security review for this trading platform — auth/session/MFA/secret handling, tenant isolation, injection classes, and trading-specific threats (uncontrolled orders, credential exposure, fail-open risk states). Use for security audits, suspicious diffs, or any auth/secret/order-adjacent change.
---

# Security and threat review (trading platform)

## When to use
- Security review of any scope: whole repo, one service, or a specific diff.
- Any change touching auth, sessions, MFA, secrets, keys, orders, positions,
  or risk limits.

## When NOT to use
- General code quality (use `repo-code-review`).

## Procedure
1. Read `references/monorepo-map.md` + the target service's profile.
2. Threat checklist (derive specifics from the profile's concerns):
   - Credentials: mnemonics/API keys/tokens — storage (salted hashes,
     AES-GCM profiles), transit, logging, commit risk. Never print values.
   - Authn/Authz: JWT/session/MFA step-up paths, ownership fail-closed
     (user_id=0), quota enforcement, generation-based refresh revocation.
   - Trading integrity: can this change place/lose control of an order?
     Fail-open states, partial fills, untracked exposure, cancel verification,
     abort scoping on shared subaccounts.
   - Injection/leak classes: SQL parameterization, error responses leaking
     internals, unbounded inputs/goroutines/body reads.
   - Env/config: placeholder creds in non-dev labels, plaintext k8s secrets.
3. Verify each suspicion by reading the code path end-to-end; label
   confirmed vs. hypothesis.

## Output
Findings by severity (P0 credential exposure/uncontrolled trading; P1
materially incorrect security behavior; P2 defense-in-depth gaps), each with
file:line, attack sketch, and minimal fix. Explicitly state what was NOT
reviewed. Do not run exploits; static analysis + tests only.

## Verification
Security-relevant fixes must land with tests that fail before the fix.
