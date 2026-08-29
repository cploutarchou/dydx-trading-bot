---
description: "Generate complete bot flow documentation: system/runtime flow, business logic flow, and application flow with diagrams and validation notes"
name: "Document Bot Flows"
argument-hint: "Scope: full system, API lifecycle, strategy runtime, or specific feature"
agent: "Senior Python DeFi Runtime"
---

Document the bot flows end-to-end with production-grade clarity.

Scope: ${input:Scope (full system/API lifecycle/strategy runtime/specific feature)}

## Objective

Produce maintainable documentation that explains:

1. **System/runtime flow** (request to execution to persistence)
2. **Business logic flow** (decision rules, safety checks, and state transitions)
3. **Application flow** (API routes, manager lifecycle, worker process behavior, and data boundaries)

## Required workflow

1. Inspect relevant code paths and identify canonical entrypoints.
2. Trace flow across API -> manager -> worker -> trading runtime -> exchange/persistence.
3. Separate business decisions from transport/infrastructure details.
4. Highlight fail-safe logic, error handling, and recovery behavior.
5. Note assumptions, unknowns, and documentation gaps.

## Required output sections

1. **Architecture snapshot**
    - Core components and responsibilities
    - Runtime boundaries and process isolation

2. **Flow map (high level)**
    - End-to-end flow in concise bullets
    - Main happy path and critical alternate paths

3. **Business logic flow**
    - Decision points and guardrails
    - Execution safety controls and reconciliation behavior
    - Preconditions and postconditions for key operations

4. **Application/API flow**
    - Route/handler to service/module mapping
    - Instance lifecycle (create/start/status/stop/delete)
    - Auth and readiness behavior where relevant

5. **Sequence diagrams (Mermaid)**
    - One system-level sequence
    - One lifecycle sequence
    - One failure/recovery sequence

6. **Data and state flow**
    - Persistent stores, in-memory state, and `bot_states/*` artifacts
    - State transitions and consistency safeguards

7. **Failure modes and rollback notes**
    - Top operational risks
    - What to do if runtime/exchange/local state diverges

8. **Validation checklist**
    - Concrete steps to verify behavior in dev/testnet

## Documentation quality bar

- Be specific (file paths, key functions/classes, and state boundaries).
- Mark inferred behavior as inferred; do not present guesses as facts.
- Prefer concise, structured explanations over long prose.
- Keep operator-focused language for on-call/debugging usability.
