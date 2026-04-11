# CRM / Backoffice Architecture (Fintech-Safe Incremental Design)

## Current state summary

### Runtime architecture
- `frontend/` (React + TypeScript + Vite) calls only `backend/`.
- `backend/` (Go + Gin) provides auth, portal/admin APIs, and bot delegation.
- `bot/` (Python FastAPI + runtime workers) handles trading/runtime execution.
- Data path: `frontend -> backend -> bot`.

### Auth and session (as-is)
- JWT access + refresh flow exists in `backend/internal/routes/auth_routes.go`.
- `RequireAuth()` middleware validates bearer access tokens and injects user context.
- Frontend keeps access/refresh tokens in localStorage and also sets cookie fallback.
- Password rotation flag (`password_change_required`) exists and is enforced in frontend routing.

### Existing CRM capability
- CRM route exists in frontend (`/crm`) with role guard (`admin`, `backoffice`).
- Backend CRM endpoints already exist under `/api/v1/admin/crm/*` in `portal_routes.go`.
- Current CRM checks are mostly role-string based (`canManageCRM`) and not permission-granular.

## Security/auth gap analysis

1. **Authorization granularity gap**
   - Existing route authorization is primarily `is_admin` checks or coarse role checks.
   - No action-level permission model for least privilege.

2. **Audit consistency gap**
   - Audit infrastructure exists (`audit_logs`) but coverage is not enforced across all sensitive routes.

3. **Admin boundary gap**
   - No first-class role-permission mapping tables for per-role/per-user overrides.

4. **Session hardening gap**
   - Token persistence in localStorage increases impact of XSS.
   - No refresh token rotation tracking/revocation registry yet.

5. **Step-up security gap**
   - CRM-specific mandatory MFA and privileged-action re-auth flow are not fully enforced yet.

## Target CRM architecture

### Access model (deny-by-default)
- Introduce permission keys and explicit role mappings.
- Introduce optional per-user permission overrides (`allow`/`deny`) for break-glass and exception handling.
- Enforce permissions at API route boundary (backend source of truth).

### New RBAC persistence
- `permissions`
- `role_permissions`
- `user_permission_overrides`

### Minimum permission set
- `crm.read`, `crm.write`
- `users.read`, `users.update`, `users.disable`
- `kyc.read`, `kyc.review`
- `finance.read`, `finance.manage`
- `audit.read`
- `security.events.read`
- `roles.manage`
- `crm.admin.manage`

### Roles supported
Legacy + fintech CRM roles:
- `admin`, `backoffice`
- `super_admin`, `operations_admin`, `compliance_admin`, `support_agent`, `finance_admin`, `read_only_auditor`, `security_analyst`

## Deployment/routing strategy recommendation

### Preferred now: `domain.com/crm` (incremental, low-risk)
- Already implemented in frontend and integrated with current shell/auth.
- Enables rapid rollout without DNS/app split risk.

### Planned target: `crm.domain.com` (stronger isolation)
- Move to dedicated CRM frontend build and stricter cookie/session boundaries after permission and MFA hardening are validated in production-like staging.

## Migration and rollout strategy

1. Ship RBAC tables + seed mappings behind current routes (non-breaking).
2. Add permission middleware to CRM/admin endpoints while preserving existing role checks where needed.
3. Introduce CRM read/write separation and tighten high-risk actions.
4. Add immutable-style admin action logging coverage for all sensitive endpoints.
5. Add CRM mandatory MFA + privileged action re-auth checks.
6. Move token strategy toward httpOnly cookies + rotation tracking.
7. Expand CRM modules incrementally (users, activity, audit, notes, admin management).

## Risks and mitigation

- **Risk:** Over-permissive fallback behavior during migration.
  - **Mitigation:** Seed explicit role permissions and progressively disable legacy role-only checks.

- **Risk:** Breaking existing admin flows.
  - **Mitigation:** Keep endpoint contracts unchanged; enforce permissions with compatible defaults.

- **Risk:** Missing audit for new actions.
  - **Mitigation:** Add mandatory audit hooks per sensitive route before expanding capabilities.

## Status after this change set

- RBAC persistence foundation: **implemented**
- Route-level permission middleware foundation: **implemented**
- CRM/admin route adoption of granular permissions: **implemented (initial)**
- Mandatory MFA for CRM users: **pending next milestone**
- Security events/session device visibility: **pending next milestone**
