# Route/Admin/Client Separation Review

## Discovered route structure

- Routing is manually declared with React Router v7 in `frontend/src/App.tsx`.
- Portal-specific authenticated routes are centralized in `frontend/src/app/routeManifest.tsx`.
- Portal selection is runtime/build-time based in `frontend/src/app/portal.ts`:
  - `VITE_APP_PORTAL_TYPE=client|backoffice|ib`
  - hostname fallback: `crm.*` -> backoffice, `ib.*` or `ib-portal.*` -> IB, default -> client.
- Public routes are declared directly in `App.tsx`: `/`, `/services/:slug`, `/pricing`, `/login`, `/register`, `/2fa-setup`, `/force-password`, `/unauthorized`.
- Client routes are `/dashboard`, `/client-area`, `/market-intel`, `/market-intel/news`, `/backtests*`, `/backtest/:runId`, `/strategies*`, `/bots`, `/settings`, plus compatibility redirects for `/codex`, `/news`, `/profile`, `/security`, `/wallet`, and `/strategies/managet`.
- Backoffice/admin routes are `/dashboard`, `/admin`, `/admin/celery`, `/crm/*`, `/ib-portal/*`, and `/settings` in the backoffice portal.
- IB routes are `/profile`, `/security`, and `/*` in the IB portal.

## Discovered layout structure

- Public pages render their own public/auth shells (`Landing`, `PublicSiteShell`, `AuthExperienceShell`, `ComingSoon`).
- Authenticated pages are wrapped by `ProtectedRoute`, which renders `MainLayout`.
- `MainLayout` composes `Sidebar`, `Header`, and `WorkspaceCommandPalette`.
- The authenticated layout is portal-aware through `getCurrentPortalType()` and `workspaceNav.ts`.
- Backoffice/admin already has a distinct sidebar navigation through `backofficeNavItems`; client has a separate `clientNavItems` set.

## Discovered auth and role handling

- Auth state used by active routing is `frontend/src/store/auth.ts`.
- User role fields are `role` and `is_admin`.
- Frontend role normalization and matching are in `frontend/src/auth/roles.ts`.
- Backend JWT/session middleware sets `user_id`, `username`, `email`, `is_admin`, and `role` in Gin context.
- Backend RBAC middleware is `backend/internal/middleware/rbac_middleware.go`.
- Admin/backoffice backend namespaces use `RequireAuth`, `RequireMFA`, and `RequirePermission` where supported.

## Discovered admin-related routes/pages/components

- Frontend pages: `AdminHub`, `AdminCelery`, CRM pages under `frontend/src/pages/crm`, IB oversight pages under `frontend/src/pages/ib`.
- Admin/operator settings components include `AdminAccessControlSettings`, `MailgunSettings`, `CoinDeskNewsSettings`, `AIMarketSettings`, `CodexSettings`, and `ArbitrageRuntimeSettings`.
- Coming Soon is rendered by `frontend/src/pages/ComingSoon.tsx` and controlled by `/api/v1/public/app-config`.
- Light/Dark mode is handled by `ThemeProvider`, `ThemeToggle`, and `useUIPreferencesStore`.

## Current problems found

- The client portal registered `/admin/celery`, creating an admin route inside the client route manifest.
- Client navigation included an admin-only Celery Ops item for admin roles.
- `/settings` in the client portal could show admin/operator controls to admin users because settings visibility only checked role, not portal surface.
- The client topbar had no explicit way for an admin/backoffice user to open the backoffice/admin portal.
- Coming Soon intercepted unauthenticated `/admin...` attempts in the client portal before route guards could redirect through auth flow.
- Backend Celery delegation used an admin-only inline check, but it only honored `is_admin` and not the strict admin role strings exposed by the frontend.

## Security gaps

- Frontend hiding was not the only protection for most admin APIs: settings, backoffice, CRM, admin users, IB tier rates, and arbitrage settings are backend guarded.
- Celery backend access was admin-only, but the boolean-only check could deny legitimate `backoffice_admin` role sessions and was less aligned with the route role gate.
- The frontend client route manifest exposed an admin path. Even with backend protection, that mixed admin affordances into the client portal.

## UX/navigation gaps

- Normal users did not see admin navigation, but admin navigation could appear in the client portal.
- Admin users lacked a clear topbar path from client/IB surfaces into the admin/backoffice section.
- Backoffice already had its own sidebar, but the client portal was partially mixing admin ops into client IA.

## Recommended refactor

- Keep the existing multi-portal route model.
- Keep client/user functionality in the client portal route manifest.
- Keep admin/backoffice functionality in the backoffice route manifest.
- Do not duplicate CRM, IB admin, Admin Hub, or operator settings inside the client portal.
- Add a role-aware topbar portal switch:
  - client/IB -> Backoffice Admin
  - backoffice -> Client area
- Make client `/settings` user-only even for admin users; keep admin/operator settings on the backoffice `/settings` surface.
- Let `/admin...` requests bypass Coming Soon so the auth/route guard handles them.
- Align Celery backend admin checks with strict admin roles.

## Implementation plan

- Remove client manifest registration for `/admin/celery`.
- Remove client sidebar Celery Ops item.
- Add portal link helpers for cross-portal topbar navigation.
- Add admin/backoffice-only topbar portal switch.
- Gate admin/operator settings by backoffice portal surface as well as role.
- Adjust Coming Soon bypass logic for `/admin...`.
- Harden delegated Celery admin guard to accept `admin`, `super_admin`, and `backoffice_admin`.
- Update tests and docs.

## Files changed

- `frontend/src/app/routeManifest.tsx`
- `frontend/src/app/routeManifest.test.tsx`
- `frontend/src/app/portalLinks.ts`
- `frontend/src/navigation/workspaceNav.ts`
- `frontend/src/navigation/workspaceNav.celery.test.ts`
- `frontend/src/components/Header.tsx`
- `frontend/src/pages/Settings.tsx`
- `frontend/src/App.tsx`
- `backend/internal/routes/bot_api_delegate_routes.go`
- `frontend/README.md`
- `frontend/docs/architecture/MULTI_PORTAL_FRONTEND.md`

## Final route behavior

- Normal client users see only client routes and client settings.
- Admin/backoffice users can still use client routes, but admin configuration does not appear in client `/settings`.
- Admin/backoffice users get a topbar entry to the backoffice portal.
- Backoffice users get a topbar entry back to the client area.
- Admin controls remain in the backoffice portal under Admin Hub, CRM, IB oversight, `/admin/celery`, and `/settings`.
- Anonymous `/admin...` requests in the client portal are not replaced by Coming Soon; route/auth handling redirects through login/unauthorized flow.

## Production blockers / residual risk

- Cross-portal switching depends on correct `VITE_CRM_HOST`, `VITE_CLIENT_HOST`, and deployment routing.
- Frontend route guards are not security controls; backend RBAC/MFA remains mandatory.
- Celery delegated routes are still guarded by a strict admin role check rather than full RBAC permission lookup because that route registrar does not currently receive a database dependency.
