---
name: error-observability-patterns
description: 'Standardize frontend error handling and observability patterns: actionable UX errors, stable retries, emoji-prefixed diagnostics, and safe failure recovery across API/live-data/operator surfaces.'
argument-hint: 'Describe the failing surface, current error behavior, and desired user + logging outcome.'
user-invocable: true
disable-model-invocation: false
---

# Error Observability Patterns

Use this skill to make failures diagnosable for developers and understandable for operators.

## Use when

- API errors are noisy, unclear, or inconsistent
- Live-data screens fail silently or flicker between states
- Retry/conflict behavior causes action churn
- Logs are missing context for root-cause analysis

## UX error principles

1. Show user-safe, action-oriented error copy (what happened + what to do next).
2. Keep critical controls stable during transient errors.
3. Distinguish retryable vs terminal failures.
4. Avoid collapsing whole pages when scoped fallback is sufficient.

## Observability conventions

- `🔐` auth/session events
- `📊` data/query/backtest events
- `🔌` websocket/connectivity events
- `❌` failures/exceptions
- `🔧` lifecycle and control-flow diagnostics

Each log should include concise context: feature surface, operation, status, and key IDs (non-sensitive).

## Error handling checklist

- [ ] Error is surfaced in-component with clear next action
- [ ] Background retries are bounded and intentional
- [ ] Conflict responses (e.g., `409`) trigger refresh, not ping-pong actions
- [ ] Network/auth failures do not expose sensitive details in UI
- [ ] Diagnostics are concise and searchable

## Verification

- Validate expected behavior for 401/403/404/409/5xx on target flow
- Validate toasts/cards are consistent with fintech copy tone
- Validate logs enable quick trace from user symptom to likely failure source
