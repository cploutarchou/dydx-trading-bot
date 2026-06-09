---
name: react-query-patterns
description: 'Standardize React Query usage for this frontend: query keys, stale/gc tiers, mutations, invalidation scope, polling/reconnect behavior, and optimistic-safe updates. Use when building or debugging hooks in src/api/hooks.ts or hook-backed components.'
argument-hint: 'Describe the data flow, current hook behavior, and desired cache/update semantics.'
user-invocable: true
disable-model-invocation: false
---

# React Query Patterns

Use this skill to keep server-state behavior predictable, efficient, and operator-safe.

## Use when

- Creating or refactoring hooks in `src/api/hooks.ts`
- Designing `queryKeys` and invalidation boundaries
- Debugging stale, flicker, duplicate refetch, or cache mismatch issues
- Converting legacy component fetch/poll logic to hook-based flows

## Guardrails

1. Reuse `queryKeys` and `queryConfigs` from `src/api/queryClient.ts`.
2. Keep invalidation as narrow as possible.
3. Use `enabled` for conditional fetches and route-dependent IDs.
4. Keep real-time behavior explicit (poll interval, websocket merge, recovery).
5. Never mix business normalization across multiple components; normalize once.

## Recommended hook checklist

- [ ] Query key includes every data-shaping parameter
- [ ] `queryFn` returns normalized response shape
- [ ] Proper cache tier selected (`realtime`, `trading`, `static`)
- [ ] Retry strategy matches endpoint behavior
- [ ] Mutation `onSuccess` invalidates only dependent keys
- [ ] Error state mapped to stable UI messaging

## Mutation pattern

- Prefer optimistic updates only when rollback path is trivial and safe.
- For risky trading controls, use server-confirmed update then targeted invalidation.
- Handle conflict responses (`409`) with state refresh instead of repeated retries.

## Verification

- Validate no unnecessary refetch loops on tab focus/reconnect.
- Validate loading transitions do not hide primary controls.
- Validate stale data indicators remain coherent on live surfaces.
