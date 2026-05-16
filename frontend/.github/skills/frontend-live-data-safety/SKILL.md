---
name: frontend-live-data-safety
description: 'Harden frontend live-data flows for websocket/polling/fallback/recovery patterns. Use when diagnosing reconnect churn, stale data behavior, duplicate updates, action conflicts, or live status reliability.'
argument-hint: 'Describe the live-data surface, symptoms, and expected recovery behavior.'
user-invocable: true
disable-model-invocation: false
---

# Frontend Live Data Safety

Use this skill to make realtime UI reliable, conflict-safe, and operator-trustworthy.

## When to use

- Reconnect loops or periodic disconnect/reconnect churn
- Polling and websocket data disagreeing or racing
- Stale UI states causing incorrect control affordances
- Retry/restart/cancel conflicts from rapidly changing backend state

## Safety workflow

1. **Classify stream architecture**
   - Bootstrap source (HTTP/query cache)
   - Realtime source (websocket)
   - Recovery source (polling/fallback)
   - Source precedence and merge rules

2. **Define stale/recovery semantics**
   - Distinguish: `healthy`, `delayed`, `stale`, `recovering`
   - Do not force-close sockets solely due to stale timer unless explicitly required
   - Surface freshness age (`updated x ago`) with clear tone escalation

3. **Control-flow hardening**
   - Gate action buttons by normalized run state
   - On `409` conflicts: refresh metadata/state, show stable conflict message, avoid flipping actions
   - On `404` restart/retry edge: optional rerun fallback only when request context exists

4. **Data merge safety**
   - Normalize status/progress fields (`progress`, `progress_pct`, `progress_percent`)
   - Prefer finite numeric parsing with clamping
   - Keep source labels explicit for diagnostics (stream vs polling vs fallback)

5. **Observability**
   - Add throttled diagnostics for stale and reconnect events
   - Keep logs concise and emoji-prefixed (`🔌`, `❌`, `📊`)

6. **Verification**
   - Reproduce issue path end-to-end
   - Validate no reconnect churn pattern remains
   - Validate no restart↔retry ping-pong behavior remains
   - Run `npm run lint` and `npm run build`

## Done criteria

- Live badge/status reflects true health and freshness.
- User actions remain deterministic under changing backend state.
- Realtime updates recover without page resets or ambiguous state.
