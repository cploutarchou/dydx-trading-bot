# ExecutionLab Fintech UX Review

## Current Structure Summary

- Frontend is a React 19 + TypeScript + Vite app in `frontend/`, with shared portal routing selected by `VITE_APP_PORTAL_TYPE` or hostname in `frontend/src/app/portal.ts`.
- Route ownership is centralized in `frontend/src/app/routeManifest.tsx`; authenticated routes are wrapped by `ProtectedRoute` in `frontend/src/App.tsx`.
- The UI already has a fintech-oriented shell (`MainLayout`, `Header`, `Sidebar`) and shared primitives in `frontend/src/components/ui/PlatformUI.tsx`.
- Public pages use `PublicSiteShell`, `Landing`, `Pricing`, and service pages. Current public positioning reads more like a general technical delivery agency than a DeFi execution platform.
- Backend is a Go API gateway in `backend/`, with route -> handler -> service -> repository layering and PostgreSQL migrations under `backend/migrations/postgres`.
- Platform settings already exist in the `bot_settings` table and are administered through protected `/api/v1/settings` routes guarded by auth, MFA, and `crm.admin.manage`.
- Registration policy already uses persistent platform settings and a safe public status endpoint, which is the right pattern to reuse for Coming Soon.

## UI/UX Weaknesses

- Public site copy does not clearly establish ExecutionLab as a DeFi/crypto execution, research, backtesting, and runtime platform.
- Public and authenticated surfaces are visually mature, but the product story is split between broad "technical execution" language and trading-specific operator pages.
- Some admin controls are spread across generic settings; high-risk launch controls need a clearer operator-facing control surface.
- Loading/failure behavior for app-wide bootstrap settings is not yet present because there is no public app config bootstrap contract.
- The public site has strong CTA sections, but its trust/security claims should be more specific to custody boundaries, credentials, backtests, live runtimes, and admin access.

## Fintech Trust Issues

- Coming Soon mode must not be controlled by frontend-only local state; it needs a persistent backend setting with admin-only mutation.
- Public bootstrap data must expose only safe flags and branding metadata, not internal settings, secrets, infrastructure URLs, or admin configuration.
- Admin/backoffice access must remain available when public launch mode is paused.
- Route guards must avoid redirect loops between `/`, `/login`, and protected workspace paths.
- App config fetch failure should fail open to the existing app rather than accidentally locking operators out.

## DeFi Positioning Gaps

- Landing page should say what the platform does for DeFi operators: market research, strategy validation, backtesting, dYdX runtime readiness, bot monitoring, and risk-aware execution workflows.
- Trust language should emphasize credential hygiene, role-based access, audited settings, runtime health, and validation before deployment.
- Coming Soon should feel like a controlled fintech launch state, not a generic maintenance splash.
- CTA copy should move serious users toward access review and sign-in without noisy crypto motifs or meme visuals.

## Technical Risks

- `App.tsx` is the correct place for app-wide public gating, but it also owns auth bootstrap; Coming Soon logic must not interfere with session restore.
- The multi-portal model means client public routes can be gated, while backoffice/IB portals should remain routed normally.
- The admin setting must invalidate both settings queries and public app config queries after mutation.
- Existing settings initialization has repeated default-setting lists; adding a new setting must update migration, initialize defaults, schema, and no-settings fallback paths to avoid drift.
- Backend tests use both PostgreSQL-style runtime assumptions and SQLite-backed integration tests; new setting reads should tolerate missing schema gracefully where needed.

## Recommended Implementation Plan

1. Add persistent backend setting `platform.coming_soon_enabled` with a transaction-safe migration.
2. Add `GET /api/v1/public/app-config` that returns only safe public flags: app name, brand name, portal launch state, and timestamp.
3. Extend settings defaults/schema so existing admin settings flows can read and persist the new flag.
4. Add a frontend API method and React Query bootstrap for app config.
5. Add a `ComingSoonPage` and an app-level gate that blocks public client routes when enabled, while allowing auth/admin utility routes and all backoffice/IB portal routing.
6. Add an admin control to the existing Access Control surface so admins can enable/disable Coming Soon mode without editing raw settings.
7. Improve public landing and Coming Soon copy to align with serious DeFi execution, trust, and platform readiness.
8. Update frontend/backend documentation with operation notes and run targeted lint/build/tests.

## Implementation Notes

- Email capture is intentionally not included unless a dedicated public lead-capture endpoint exists; using Mailgun status alone would not provide a clean public storage and consent model.
- Coming Soon is scoped to public client-portal routes. Existing operators can still sign in, and backoffice/IB builds continue through their normal route manifests.
- The frontend fails open if public app config cannot be loaded, so backend outages do not create an accidental production lockout.

## Implemented Changes

- Added PostgreSQL migration `000060_add_coming_soon_setting` for `platform.coming_soon_enabled`.
- Added safe public backend config endpoint `GET /api/v1/public/app-config`.
- Added frontend app-config bootstrap, Coming Soon route guard, and branded Coming Soon page.
- Added admin Coming Soon control under Settings -> Access Control -> Platform Access.
- Repositioned public landing copy around DeFi research, strategy validation, dYdX runtime readiness, and fintech trust.
- Updated frontend/backend README notes with operation and API details.
