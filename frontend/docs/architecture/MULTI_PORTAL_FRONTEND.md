# Multi-Portal Frontend

## Apps

- Client Portal: `VITE_APP_PORTAL_TYPE=client`, deployed at `app.example.com`
- CRM / Backoffice: `VITE_APP_PORTAL_TYPE=backoffice`, deployed at `crm.example.com`
- IB Portal: `VITE_APP_PORTAL_TYPE=ib`, deployed at `ib.example.com`

## Shared Packages

- `packages/shared-ui`: UI primitives, page containers, and feedback surfaces
- `packages/shared-api`: API clients, hooks, query client, and API types
- `packages/shared-auth`: portal detection, role helpers, and auth store
- `packages/shared-types`: shared portal, role, and API types

These packages currently re-export existing `src/*` modules so the split does not duplicate business logic.

## Role Assumptions

- Client Portal: `client`, `user`
- IB Portal: `ib`, `sub_ib`; admin/backoffice roles may enter for operational oversight
- CRM / Backoffice: `admin`, `super_admin`, `backoffice`, `operations_admin`, `finance_admin`, `support_agent`

The frontend prevents accidental cross-portal access with route guards and `/unauthorized`. The backend remains responsible for enforcing authorization on every endpoint.

## Deployment Mapping

```bash
npm run build:client      # app.example.com
npm run build:backoffice  # crm.example.com
npm run build:ib          # ib.example.com
```

Runtime variables:

```bash
VITE_API_BASE_URL=https://api.example.com
VITE_AUTH_BASE_URL=https://api.example.com
VITE_CLIENT_HOST=app.example.com
VITE_CRM_HOST=crm.example.com
VITE_IB_PORTAL_HOST=ib.example.com
```

`VITE_API_URL` remains a compatibility fallback for older profiles.
