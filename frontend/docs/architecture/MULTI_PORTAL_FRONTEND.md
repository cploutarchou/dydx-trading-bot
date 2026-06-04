# Multi-Portal Frontend

## Apps

- Client Portal: `VITE_APP_PORTAL_TYPE=client`, deployed at `app.executionlab.io`
- CRM / Backoffice: `VITE_APP_PORTAL_TYPE=backoffice`, deployed at `crm.executionlab.io`
- IB Portal: `VITE_APP_PORTAL_TYPE=ib`, deployed at `ib.executionlab.io`

Portal route registration is centralized in `src/app/routeManifest.tsx`. Each entry owns its route path, allowed workspace roles, and lazy-loaded element so `src/App.tsx` can apply one consistent protected-route wrapper.

Admin and client surfaces remain separate portal concerns. Client routes must stay in the client route list; admin/backoffice pages must stay in the backoffice route list and corresponding `backofficeNavItems` navigation. Admin users may enter the client portal for normal user workflows, but admin configuration is not rendered in client `/settings`.

## Shared Packages

- `packages/shared-ui`: UI primitives, page containers, and feedback surfaces
- `packages/shared-api`: API clients, hooks, query client, and API types
- `packages/shared-auth`: portal detection, role helpers, and auth store
- `packages/shared-types`: shared portal, role, and API types

These packages currently re-export existing `src/*` modules so the split does not duplicate business logic.

Shared API exports now include `src/api/normalizers.ts` for envelope/list extraction. Shared UI exports include the platform primitives, `TerminalDataGrid`, and live-state/freshness badges.

## Role Assumptions

- Client Portal: `client`, `user`
- IB Portal: `ib`, `sub_ib`; admin/backoffice roles may enter for operational oversight
- CRM / Backoffice: `admin`, `super_admin`, `backoffice`, `operations_admin`, `finance_admin`, `support_agent`

The frontend prevents accidental cross-portal access with route guards and `/unauthorized`. The backend remains responsible for enforcing authorization on every endpoint.

Admin/backoffice users see a workspace topbar switch from client or IB surfaces into the CRM / Backoffice portal. In the backoffice portal the same control returns to the Client Portal. The switch uses `VITE_CRM_HOST`, `VITE_CLIENT_HOST`, and the portal subdomain settings helpers, so production deployments must keep those host values accurate.

In Vite development, the switch stays on the same origin and adds `?portal=backoffice` or `?portal=client`. This preserves the localStorage-backed dev session, avoiding a forced login when moving between `localhost` and `crm.localhost`.

## Deployment Mapping

```bash
npm run build:client      # app.executionlab.io
npm run build:backoffice  # crm.executionlab.io
npm run build:ib          # ib.executionlab.io
```

Runtime variables:

```bash
VITE_API_BASE_URL=https://api.executionlab.io
VITE_AUTH_BASE_URL=https://api.executionlab.io
VITE_CLIENT_HOST=app.executionlab.io
VITE_CRM_HOST=crm.executionlab.io
VITE_IB_PORTAL_HOST=ib.executionlab.io
```

`VITE_API_URL` remains a compatibility fallback for older profiles.

## Adding Routes

- Add client pages to `clientRoutes` in `src/app/routeManifest.tsx` and `clientNavItems` in `src/navigation/workspaceNav.ts`.
- Add admin/backoffice pages to `backofficeRoutes` and `backofficeNavItems`.
- Add IB pages to `ibRoutes` and `ibNavItems`.
- Keep backend authorization aligned with the route owner. Admin settings and mutations should use the existing backend RBAC/MFA middleware where the backend has a database-backed permission boundary.

## Coming Soon and Admin Access

Coming Soon mode is a client-portal public launch gate only. It does not block the backoffice or IB builds. In the client portal, `/admin...` paths bypass the Coming Soon page so auth and route guards can redirect anonymous users to login or authenticated users to the correct unauthorized/client flow without a loop.
