# CRM Backoffice Implementation Plan (Incremental, Production-Safe)

## Milestones

### M1 — Foundation (completed in this iteration)
- [x] Audit current architecture, auth, CRM routes, and data model.
- [x] Add RBAC schema (`permissions`, `role_permissions`, `user_permission_overrides`).
- [x] Seed fintech-oriented permission mappings for legacy + new CRM roles.
- [x] Add backend permission service + middleware.
- [x] Apply permission checks to CRM/admin routes.

### M2 — Auditability hardening
- [ ] Enforce audit logging for all sensitive CRM/admin mutations.
- [ ] Capture actor role, target entity, result, IP, user-agent, diff snapshot for critical updates.
- [ ] Add searchable audit filters for backoffice operators.

### M3 — Admin auth hardening
- [ ] Require MFA for all CRM-capable roles.
- [ ] Add step-up re-auth for high-risk actions (role changes, disables, commission updates).
- [ ] Add suspicious login hooks + lock/review workflow.
- [ ] Add admin session policy (short TTL, rotation, forced re-auth windows).

### M4 — CRM module expansion
- [ ] Dashboard: security + operational summary.
- [ ] User Management: search/filter/detail + lifecycle.
- [ ] Activity Monitoring: login/security/admin timeline.
- [ ] Admin Management: operator status, role/permission assignment.
- [ ] Audit Log UI with filters/export.
- [ ] Internal notes/case workflow.

### M5 — Rollout and operational safety
- [ ] Feature flag new CRM capabilities.
- [ ] Staging soak tests + auth/permission regression suite.
- [ ] Production phased rollout by role.
- [ ] Rollback plan validation.

## Detailed task breakdown

1. **Backend authorization**
   - Add permission checks per endpoint.
   - Keep compatibility with existing claims/roles.
   - Introduce explicit deny overrides per user.

2. **Data model & migration**
   - Add new RBAC tables and indexes.
   - Seed minimum role-permission matrix.
   - Verify migration behavior against PostgreSQL.

3. **Frontend alignment**
   - Expand role normalization for new CRM roles.
   - Keep existing route gates while backend is source-of-truth.

4. **Security controls**
   - MFA enforcement for CRM roles.
   - Session hardening and rotation.
   - Brute-force and anomaly hooks on admin login.

5. **Testing**
   - Unit tests for permission evaluation and middleware.
   - Route tests for positive/negative permission paths.
   - Regression tests for login + refresh + existing admin operations.

## Dependencies
- Existing user role field in `users.role` remains source role identifier.
- Auth claims already include `role` and `is_admin`.
- Existing CRM endpoints under `/api/v1/admin/crm/*` provide rollout-safe anchor.

## Rollout order
1. Deploy migrations.
2. Deploy backend permission middleware + route wiring.
3. Validate with staging role matrix.
4. Enable expanded CRM roles in operations runbook.
5. Roll MFA and privileged re-auth requirements.
6. Expand CRM UI modules iteratively.
