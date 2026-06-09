# Admin Coming Soon and Light Theme Plan

## Current-State Analysis

### Architecture and Entry Points

- The monorepo is split into `frontend/` (React 19, TypeScript, Vite, Tailwind CSS v4), `backend/` (Go, Gin, MariaDB), and `bot/` (Python FastAPI trading runtime).
- The strict integration boundary is `frontend -> backend -> bot`; browser code must not call the bot directly.
- Frontend bootstraps from `frontend/src/main.tsx` into `frontend/src/App.tsx`, which wraps routing with `ThemeProvider`, React Query, global error handling, toast UI, and auth bootstrap.
- Backend route assembly is centralized in `backend/internal/app/router.go`, with feature route registration under `/api/v1/*`.

### Frontend Routing, Navigation, and Auth

- Portal selection is handled by `frontend/src/app/portal.ts` using `VITE_APP_PORTAL_TYPE` or hostname detection.
- Portal route ownership lives in `frontend/src/app/routeManifest.tsx`.
- Navigation is generated from `frontend/src/navigation/workspaceNav.ts`, filtered by role with `filterNavItemsForRole`.
- Protected route behavior is in `frontend/src/App.tsx` via `ProtectedRoute`, which waits for session bootstrap, redirects unauthenticated users to `/login`, enforces password rotation, privileged MFA setup, and role gates.
- Auth state used by route guards is `frontend/src/store/auth.ts`. Roles are normalized in `frontend/src/auth/roles.ts`.

### Admin Section Structure

- Backoffice/admin routes are available only in the `backoffice` portal route manifest.
- Admin hub is `frontend/src/pages/AdminHub.tsx`.
- Operator settings are exposed at `/admin/settings` and rendered by the shared `frontend/src/pages/Settings.tsx`.
- Admin-level settings APIs are protected server-side by `RequireAuth()`, `RequireMFA(...)`, and `RequirePermission(..., "crm.admin.manage")`.

### Settings and Feature-Flag Storage

- Backend settings are persisted in `bot_settings` with `(section, key)` uniqueness.
- Existing platform settings include registration and portal subdomain settings.
- `platform.coming_soon_enabled` already exists in default backend settings initialization and is seeded by `backend/migrations/mysql/000060_add_coming_soon_setting.up.sql`.
- Public frontend bootstrap reads `GET /api/v1/public/app-config`, which currently returns `coming_soon_enabled`.
- Existing generic `PUT /api/v1/settings` can update `platform.coming_soon_enabled`, but it is broad and lacks a dedicated confirmation-oriented contract for this production-impacting toggle.

### Current Coming Soon Behavior

- `frontend/src/pages/ComingSoon.tsx` already exists.
- `frontend/src/App.tsx` already has a `ComingSoonGate` that reads public app config.
- Current gating is incomplete because any authenticated user can bypass the public Coming Soon page.
- Backend currently exposes the setting publicly but does not enforce a maintenance/launch gate for authenticated non-admin API access.

### Theme Implementation

- `frontend/src/components/ThemeProvider.tsx` writes `data-theme` and `data-theme-preference` attributes to `<html>`.
- Theme preference is persisted in `frontend/src/store/uiPreferences.ts`.
- `frontend/src/index.css` defines dark-first CSS variables and a light-mode override block.
- Most components still use dark Tailwind utility classes directly (`bg-slate-*`, `text-white`, `border-slate-*`, `text-cyan-*`, etc.).
- Light mode is currently achieved through a large compatibility override layer that remaps common dark classes. This preserves dark behavior but creates inconsistent light surfaces where component classes are too specific or absent from the compatibility layer.

### Major Light-Theme Inconsistencies

- App shell uses hardcoded `text-white`, dark slate/stone backgrounds, and dark borders in `MainLayout`, `Header`, and `Sidebar`.
- Sidebar active, hover, quick action, account, and logout states use dark-only class combinations.
- Header controls and breadcrumbs use dark-only text and control colors.
- Settings page uses many slate/cyan/red classes directly in labels, section nav, action bars, switches, and validation states.
- `TerminalDataGrid` hardcodes dark table container, metrics, header, row, search, and pagination colors.
- Shared UI primitives in `PlatformUI.tsx` encode tone classes with dark text and backgrounds.
- Toasts, dialogs, command palette, and error surfaces depend on dark utility classes and require light compatibility.
- Several CRM/IB pages have many local hardcoded color classes; the existing global light override helps but still leaves risks around nested active states and low-contrast muted text.
- Public/auth/landing surfaces use heavy dark gradients and decorative lighting that become visually noisy when forcibly converted to light.

### Usability, Accessibility, and Responsive Issues

- Active navigation state is clear in dark mode but less structurally distinct in light mode because contrast depends heavily on cyan tint.
- Focus uses a cyan ring globally, but some switches and dark controls have low contrast in light mode.
- Settings generic schema fields use a two-column grid that can become cramped on narrow screens.
- Tables need stronger light-mode header separation, row hover, row boundaries, and pagination affordances.
- Some muted text is too low-contrast in light mode due to direct `text-slate-500/600` usage.
- Production-impacting setting updates lack a dedicated confirmation flow.

### Implementation Risks

- Route and API gating must avoid redirect loops and must not block `/login`, `/register`, `/auth/*`, `/public/app-config`, `/health`, `/ready`, `/metrics`, static assets, or admin settings routes.
- Existing dark theme behavior should not regress while improving light mode.
- Broad CSS overrides can unintentionally recolor intentionally dark modal or overlay surfaces.
- Backend middleware must not break bot delegated routes for authorized admins or operational readiness endpoints.
- Generic settings update behavior is already consumed by the existing settings page, so dedicated Coming Soon APIs should extend rather than replace that contract.

## Proposed Architecture

### Coming Soon

- Reuse `bot_settings` as the authoritative persistence mechanism.
- Keep `GET /api/v1/public/app-config` as the unauthenticated read contract.
- Add narrow admin endpoints:
  - `GET /api/v1/settings/platform/coming-soon`
  - `PUT /api/v1/settings/platform/coming-soon`
- Protect the new endpoints with the existing settings route middleware: auth, privileged MFA, and `crm.admin.manage`.
- Validate update payloads as explicit booleans.
- Add backend middleware that checks `platform.coming_soon_enabled` for `/api/v1/*` application routes and blocks non-admin/non-backoffice authenticated requests with a structured `503` response while exempting auth, public config, health/readiness/metrics, websocket, debug, admin/backoffice/settings, and portal admin routes.
- Keep frontend route gating client-portal only. Anonymous users and authenticated non-admin client users see Coming Soon while enabled. Backoffice/admin users can still reach admin/backoffice routes.
- Add an admin settings panel with state display, refresh, confirmation dialog, loading, success, error, and duplicate-submission prevention.

### Light Theme

- Expand semantic tokens in `frontend/src/index.css` for page, surface, text, border, actions, states, disabled, overlay, shadow, table, input, and focus.
- Keep a single stylesheet and preserve dark mode as default.
- Improve the existing compatibility layer so dark Tailwind classes map to consistent light theme tokens.
- Add targeted component classnames or CSS for shell, header, sidebar, settings, tables, dialogs, toasts, and Coming Soon.
- Prefer semantic CSS variables for shared primitives while leaving feature-specific Tailwind structure intact.

## Files Expected to Change

- `docs/admin-coming-soon-and-light-theme-plan.md`
- `backend/internal/handlers/settings_handler.go`
- `backend/internal/routes/settings_routes.go`
- `backend/internal/middleware/coming_soon_middleware.go`
- `backend/internal/app/router.go`
- `backend/internal/routes/public_app_config_routes_test.go`
- `backend/internal/middleware/coming_soon_middleware_test.go`
- `frontend/src/api.ts`
- `frontend/src/App.tsx`
- `frontend/src/pages/ComingSoon.tsx`
- `frontend/src/pages/Settings.tsx`
- `frontend/src/components/AdminComingSoonSettings.tsx`
- `frontend/src/components/MainLayout.tsx`
- `frontend/src/components/Header.tsx`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/components/TerminalDataGrid.tsx`
- `frontend/src/components/ui/PlatformUI.tsx`
- `frontend/src/index.css`
- Frontend tests for theme routing and UI where practical.

## Database or API Changes

- No new table is required.
- Existing migration `000060_add_coming_soon_setting` already seeds `platform.coming_soon_enabled`.
- Add narrow API endpoints for reading/updating the Coming Soon setting.
- Existing `GET /api/v1/public/app-config` remains backward compatible.
- Add a structured blocked response for gated non-admin API calls while Coming Soon mode is enabled.

## UI/UX Changes

- Add a dedicated "Coming Soon" admin settings section visible only in backoffice settings.
- Show current launch mode clearly with status badges and explanatory copy.
- Require confirmation before enabling or disabling mode.
- Disable duplicate submissions and show loading, success, failure, and refresh states.
- Polish the Coming Soon page with brand identity, clear heading, short explanation, and sign-in path without fake dates or unsupported contact details.
- Improve light-mode shell, navigation, controls, forms, tables, modals, toasts, badges, and loading states.

## Migration and Backward Compatibility

- The existing seeded setting defaults to disabled, so normal behavior is preserved after deployment.
- Public config response shape remains compatible.
- Existing generic settings update still works; the new endpoint is a safer extension.
- Coming Soon middleware defaults to allow if settings storage is unavailable, avoiding accidental outage from migration/storage failure.
- Admin routes and auth flows are explicitly exempt to avoid lockouts.

## Testing Strategy

- Backend:
  - Public app-config default disabled and setting read tests.
  - Dedicated Coming Soon read/update handler tests.
  - Unauthorized admin setting update attempts.
  - Middleware blocking for authenticated normal users while enabled.
  - Middleware allow for admins and exempted routes.
- Frontend:
  - Route gate behavior for anonymous, normal authenticated, and admin users.
  - API client methods for Coming Soon setting.
  - Theme preference switching and light semantic token behavior where existing test setup permits.
  - Critical UI components using light-compatible classes.
- Validation commands:
  - Frontend formatter if present, lint, typecheck, tests, build.
  - Backend gofmt, targeted `go test`, broader `make test` as time permits.

## Concrete Implementation Checklist

- [ ] Add dedicated backend Coming Soon read/update handler methods.
- [ ] Add protected routes under `/api/v1/settings/platform/coming-soon`.
- [ ] Add backend Coming Soon API middleware with explicit exemptions.
- [ ] Add backend tests for public config, update authorization, and middleware blocking.
- [ ] Add frontend API client methods and types.
- [ ] Tighten `ComingSoonGate` to allow only admin/backoffice users through while enabled.
- [ ] Add `AdminComingSoonSettings` and surface it in backoffice settings.
- [ ] Polish `ComingSoonPage`.
- [ ] Expand semantic CSS tokens and light compatibility layer.
- [ ] Replace key hardcoded shell/settings/table colors with semantic or theme-aware classes.
- [ ] Add/update frontend tests where practical.
- [ ] Run formatting, linting, typechecking, tests, and production build.
- [ ] Manually inspect light and dark routes on desktop/tablet/mobile where feasible.
