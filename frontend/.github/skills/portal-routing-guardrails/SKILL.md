---
name: portal-routing-guardrails
description: 'Protect multi-portal route architecture and auth/role gating for client/backoffice/ib surfaces. Use when adding routes, role checks, portal switches, or protected navigation flows.'
argument-hint: 'Describe route change, portal target, role constraints, and expected navigation behavior.'
user-invocable: true
disable-model-invocation: false
---

# Portal Routing Guardrails

Use this skill to keep route behavior safe, consistent, and production-ready across all portals.

## Use when

- Adding or refactoring routes in `src/App.tsx`, `src/app/routeManifest.tsx`, or portal utilities
- Changing auth gate behavior (`ProtectedRoute`, session bootstrap)
- Updating role access (`allowedRoles`, privileged workflows)
- Modifying portal selection (`VITE_APP_PORTAL_TYPE`, `getCurrentPortalType()`)

## Core guardrails

1. Preserve portal isolation (`client`, `backoffice`, `ib`) and avoid accidental route leakage.
2. Enforce auth/session checks before rendering protected routes.
3. Keep role checks explicit and fail-closed by default.
4. Preserve password-rotation and MFA setup gate behavior where applicable.
5. Keep redirects deterministic (no redirect loops, no fallback ambiguity).

## Implementation checklist

- [ ] Route is attached to the intended portal only
- [ ] Protected route gate still waits for session initialization
- [ ] `allowedRoles` is explicit for privileged pages
- [ ] Unauthenticated users land on the correct auth flow
- [ ] Unauthorized users receive stable fallback route/error UX

## Verification checklist

- Verify route access for each role persona
- Verify behavior before and after refresh/session restore
- Verify direct URL navigation behaves the same as in-app navigation
- Verify no portal can reach another portal-only route by path guessing

## Notes

Prefer centralized route manifest updates over scattered inline route checks, and keep role logic close to route definition for easier audits.
