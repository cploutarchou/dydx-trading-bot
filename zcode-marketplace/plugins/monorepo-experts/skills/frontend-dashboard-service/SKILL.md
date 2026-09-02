---
name: frontend-dashboard-service
description: Implement and review the React/TypeScript dashboard under frontend/ — pages, components, API hooks, auth flows, and contract guards. Use for any change inside frontend/, including UX work on backtests, strategies, live views, and settings.
---

# frontend/ service implementation (React dashboard)

## When to use
- Any change under `frontend/`.

## When NOT to use
- Backend/bot code; API contract redesign (`monorepo-architecture`).

## Rules
- All HTTP through `src/api.ts` / `src/api/hooks.ts` (interceptors own auth
  tokens). Never ad-hoc fetch.
- Zero-warning lint policy (`--max-warnings 0`); strict typecheck.
- Respect portal routing invariants and fintech UI standards
  (`frontend/docs/architecture/FINTECH_UI_STANDARDS.md`).
- Handle backend `password_change_required` 403s and MFA flows in UX.
- Never log or persist auth tokens outside the api client.

## Procedure
1. Read `references/frontend-service.md` first.
2. Check `frontend/.github/` skills for the relevant surface
   (react-query patterns, live-data safety, error observability).
3. Smallest complete change; update `src/api/contractGuards.test.ts` when
   response shapes change (together with backend).

## Verification (run all; quote real results)
```
cd frontend
npm run lint && npm run typecheck && npm run test:contracts && npm run build
```
