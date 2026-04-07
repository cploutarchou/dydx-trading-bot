---
name: "Delegated Bot API Review"
description: "Review delegated bot API routes, upstream proxy logic, auth forwarding, service-token behavior, WebSocket relays, retries, timeout handling, and caller compatibility in this dYdX backend. Use when auditing delegated bot API behavior, upstream integrations, or proxy-style route changes."
argument-hint: "Describe the delegated route, upstream integration, file, diff, or behavior to review"
agent: "agent"
---

Perform a focused delegated bot API review for this repository.

Use the repository guidance in [Go API, Database, and Crypto Trading Backend](../skills/go-api-db-crypto-trading/SKILL.md) and [Go Backend API Conventions](../instructions/go-backend-api.instructions.md).

Review the requested routes, handlers, HTTP clients, WebSocket proxy code, middleware interactions, and related configuration with emphasis on upstream delegation safety and caller compatibility.

## Review for these risks

- incorrect auth forwarding, missing token propagation, or accidental service-token misuse
- incompatibilities between backend compatibility routes and the upstream bot API contract
- timeout, retry, cancellation, or connection-lifecycle bugs in delegated HTTP flows
- poor separation between transport failures, upstream business-rule failures, and local validation failures
- request or response translation bugs that change caller-visible behavior
- WebSocket relay issues such as dropped messages, half-open connections, missing close handling, or broken bi-directional forwarding
- insecure header forwarding, cookie leakage, or unintended trust of client-provided values
- missing observability around upstream failures, degraded health, or partial responses
- environment mismatches, wrong upstream URLs, or testnet vs mainnet handling mistakes
- hidden breaking changes for frontend callers that rely on legacy route shapes or response semantics

## Output format

Provide:

1. **Overall delegation risk** — low, medium, or high
2. **Findings** — ordered by severity
3. **Why it matters** — caller impact, operational impact, or security/trading impact
4. **Recommended minimal fix** — smallest safe compatibility-preserving change first
5. **Compatibility notes** — mention auth mode, timeout behavior, WebSocket behavior, and any frontend-facing contract risks

## Review rules

- Prioritize caller compatibility, auth correctness, and transport reliability over style comments.
- Be specific about affected routes, handlers, client calls, headers, tokens, WebSocket paths, and config keys.
- Distinguish confirmed defects from possible integration concerns.
- If the existing implementation looks safe, say so briefly instead of forcing issues.
- Explicitly call out whether the change should use user-token forwarding or service-token mode.
- Mention health-check and degraded-upstream behavior when relevant.
- Prefer the smallest compatibility-preserving fix before suggesting broader refactors.
