# Frontend Service

The frontend is a Vite/React workspace that now builds three independent authenticated portals from the same design system and API/auth foundations.

## Responsibilities

- render the public marketing site and pricing pages
- handle login, registration, 2FA, and account flows
- provide the authenticated Client Portal
- provide the CRM / Backoffice operator workspace
- provide the IB Portal workspace
- display live backtests, strategies, bots, and market views
- consume backend HTTP and websocket routes only

## Runtime

- framework: React 19 + TypeScript 6 + Vite 8
- default dev port: `5173`
- API target: backend on `8888`
- registration verification: set `VITE_TURNSTILE_SITE_KEY` to a Cloudflare Turnstile
  Managed widget site key. Widget mode is configured in Cloudflare; the frontend
  render options only control client presentation such as size and theme.

## Integration Rule

The frontend must never talk directly to the Python bot API in product code.

Allowed:

- backend HTTP routes
- backend websocket routes

Not allowed:

- direct bot HTTP or websocket routes
- direct database access

## Commands

```bash
npm install
npm run dev
npm run dev:client
npm run dev:backoffice
npm run dev:ib
npm run build
npm run build:client
npm run build:backoffice
npm run build:ib
npm run lint
npm run preview
npm test
npm run test:e2e
```

Testing notes: `npm test` runs the full Vitest suite (unit + contract; component
tests use jsdom via the `*.dom.test.tsx` naming convention). `npm run
test:e2e` runs the backend-free Playwright smoke suite from `e2e/` and starts
the dev server itself (first run needs `npx playwright install chromium`).

## Portal Architecture

The portal shell is selected with `VITE_APP_PORTAL_TYPE=client|backoffice|ib`.

- Client Portal (`apps/client-portal`): dashboard, client area, strategies, backtests, bot operations, profile, security, Telegram, and wallet/API key management. It does not register CRM, IB admin, Admin Hub, global settings, access-control, Celery Ops, or operator integration routes.
- CRM / Backoffice (`apps/backoffice`): Admin Hub, CRM clients, registration pipeline, hierarchy, commissions, security events, IB oversight, Celery Ops, and operator settings for access control, registration policy, Mailgun, Telegram, Market News, API, Redis, and trading configuration.
- IB Portal (`apps/ib-portal`): IB dashboard, client tree, applications/invitations, commission metrics, reports, referral tokens where role-authorized, profile, and security.

Shared boundaries are exposed under:

- `packages/shared-ui`
- `packages/shared-api`
- `packages/shared-auth`
- `packages/shared-types`

The current implementation keeps the original source modules in `src/*` and exports them through those package folders to avoid duplicating business logic while the repo moves toward a fuller workspace-package layout.

## Client Portal Information Architecture

The client portal is organized around the automation workflow:

- Dashboard: live account and runtime intelligence, active bots, live PnL, alerts, recent activity, and quick actions.
- Strategies: strategy library, builder, edit flows, templates, risk profile, and validation readiness.
- Backtests: a dedicated subsection with `/backtests` for validation dashboard stats, `/backtests/new` for run setup, `/backtests/runs` for the run archive, `/backtests/experiments` for experiment tracking, and `/backtests/compare` for comparisons.
- Bots: live/paper runtime management, health, start/stop/restart/delete actions, positions, logs, and deployment review.
- Market Intel: Codex token intelligence and Market News research. Legacy `/codex` and `/news` links redirect into this section.
- Client Area / Account: role progression, onboarding state, and partner application timeline.
- Settings: profile, security, dYdX keys/wallet/API credentials, and user Telegram delivery. Admin/operator settings stay in the backoffice portal even when an admin account opens client `/settings`.

Client portal product flow should remain: `Research -> Strategy -> Backtest -> Deploy Bot -> Monitor Dashboard`.

## Domains and Environment

Use these variables for local or deployed builds:

```bash
VITE_APP_PORTAL_TYPE=client
VITE_API_BASE_URL=http://localhost:8888
VITE_AUTH_BASE_URL=http://localhost:8888
VITE_CLIENT_HOST=app.executionlab.io
VITE_CRM_HOST=crm.executionlab.io
VITE_IB_PORTAL_HOST=ib.executionlab.io
```

Suggested deployment mapping:

- `app.executionlab.io` -> `npm run build:client`
- `crm.executionlab.io` -> `npm run build:backoffice`
- `ib.executionlab.io` -> `npm run build:ib`

`VITE_API_URL` is still supported as a compatibility fallback, but new deployments should use `VITE_API_BASE_URL`.

## Role Guards

Client routes allow `client` and `user`. IB routes allow `ib` and `sub_ib`; admin/backoffice roles can also enter for operational oversight. Backoffice routes allow `admin`, `super_admin`, `backoffice_admin`, `backoffice`, `operations_admin`, `compliance_admin`, `finance_admin`, `support_agent`, `read_only_auditor`, `security_analyst`, `accounting`, `marketing`, and `agent`.

Unauthorized authenticated users land on `/unauthorized`. Backend endpoints must continue to enforce the same role boundaries; frontend guards are a UX and accidental-access layer, not the source of authorization truth.

Admin/backoffice users get a topbar switch into the CRM / Backoffice portal. Backoffice users get a matching topbar switch back to the Client Portal. Add new admin pages to `src/app/routeManifest.tsx` under the backoffice route list and `src/navigation/workspaceNav.ts` under `backofficeNavItems`; add new client pages to the client route list and `clientNavItems`. Do not add admin-only pages to the client route list unless the route is a deliberate compatibility redirect and is still backend guarded.

## Backend/API Notes

The current portal builds consume these backend namespaces:

- public app bootstrap flags: `/api/v1/public/app-config`
- client/session and shared account state: `/api/v1/me`, `/api/v1/auth/session`
- partner/client portal data: `/api/v1/portal/*`
- CRM/backoffice operations: `/api/v1/backoffice/*`
- IB portal workspace: `/api/v1/ib/*`
- legacy CRM compatibility while older clients migrate: `/api/v1/admin/crm/*`
- platform and trading settings: `/api/v1/settings/*`

Backend role checks must enforce the same portal assumptions listed above, especially for `/api/v1/backoffice/*`, `/api/v1/ib/*`, `/api/v1/portal/*`, and `/api/v1/settings/*`.

## Coming Soon Mode

Public launch mode is controlled by the backend setting `platform.coming_soon_enabled`.

- Safe public bootstrap endpoint: `GET /api/v1/public/app-config`
- Admin mutation path: Backoffice/Admin Hub -> Settings -> Access Control -> Platform Access -> Coming Soon mode
- Direct API mutation, for admin automation only: `PUT /api/v1/settings` with `{ "platform.coming_soon_enabled": true }`

When enabled in the client portal:

- unauthenticated public traffic sees the branded Coming Soon page
- `/login`, `/2fa-setup`, `/force-password`, and `/ico` remain routable
- `/admin...` attempts are allowed to reach auth/route guards so admin deep links do not get replaced by the Coming Soon page
- authenticated sessions continue through existing protected route guards
- backoffice and IB portal builds are not blocked

If the public app config endpoint fails to load, the frontend fails open to the existing app so operators are not locked out by a bootstrap outage.

## Launch Campaign Copy

Marketing launch text for the public auth/coming-soon surfaces is centralized in:

- `src/content/publicSite.ts` -> `comingSoonMarketingContent`
- `src/content/publicSite.ts` -> `icoLaunchpadContent`

Update these fields for campaign changes:

- `icoAnnouncement` (launch badge/callout copy)
- `launchTicker` (ticker symbols, price text, change text, and stage labels)
- `icoLaunchpadContent.resources` (whitepaper/tokenomics/KYC links)
- `icoLaunchpadContent.timeline` (sale phases and status labels)
- `icoLaunchpadContent.countdownTargetUtc` + `countdownLabel` (public-sale timer)
- `icoLaunchpadContent.whitelistContactEmail` + `whitelistCtaLabel` + `whitelistHelperCopy` (whitelist CTA behavior)
- `icoLaunchpadContent.calendar*` fields (Google Calendar + ICS reminder event metadata)

Do not edit campaign strings directly in `src/pages/Login.tsx` or `src/pages/ComingSoon.tsx`; those pages consume shared content from `publicSite.ts`.

## Key Directories

- `apps/backoffice`, `apps/client-portal`, and `apps/ib-portal` for portal app shells
- `packages/shared-ui`, `packages/shared-api`, `packages/shared-auth`, and `packages/shared-types` for shared exports
- `src/app` for portal detection and typed route manifest ownership
- `src/pages` for route-level screens, including `src/pages/crm`, `src/pages/ib`, and `src/pages/client`
- `src/components` for reusable UI blocks
- `src/features` for feature modules such as backtests and Codex
- `src/api` for API, websocket helpers, hooks, and normalizers
- `src/auth` for role definitions and role normalization
- `src/store` for Zustand state
- `src/navigation` for workspace navigation and command palette

## UI Standard

The current UI direction is production DeFi:

- websocket-first live surfaces
- backend-only integration
- trading-terminal style density where appropriate
- responsive layouts across mobile, tablet, and desktop
- smaller, intentional surfaces instead of oversized marketing boxes

## Live Backtest Stream Stability

- Backtest progress streams use websocket-first updates with HTTP bootstrap/recovery.
- Managed websocket stale detection now supports two modes:
  - force-close stale sockets to trigger reconnect (`closeOnStale: true`)
  - keep sockets open and resync state over HTTP without forced reconnect (`closeOnStale: false`)
- Backtest progress uses the non-forced-close mode to avoid deterministic reconnect churn/noisy logs when a stream is temporarily quiet.
- Stale/resync events are logged with `🔌` prefixes and throttled so production consoles remain readable.

## Shared Product Patterns

- public pages should explain workflow, trust posture, and pricing before auth
- public navigation is route-based rather than anchor-based: Home, Research, Runtime, Market Intel, Security, and Pricing are separate journeys
- pre-auth public pages should favor editorial bands, thin separators, and row-based comparison over long one-page scrolls or stacked rounded cards
- auth screens should expose access state, security expectations, and next-step clarity
- workspace chrome should keep grouped navigation, command access, environment context, and operator identity visible
- operator pages should use control-room headers, compact status pills, and reusable terminal-style cards/grids
- the workspace shell uses sharper 8px surfaces, neutral dark panels, and restrained cyan/emerald/amber state color so data hierarchy stays stronger than decoration
- dashboard quick-launch and activity-tape surfaces should refresh softly and preserve visible data while active jobs update
- risky mutations should use consistent confirmation dialogs rather than browser-native confirms
- inline notices and toast feedback should use human operator language with next-step guidance
- setup flows such as backtest launch and runtime creation should show summary context before submission
- live-state semantics should stay consistent:
  - healthy/positive: emerald
  - live/realtime: cyan
  - warning/recovering: amber
  - negative/failure: rose/red
- theme selection supports Dark and System modes through
  `src/store/uiPreferences.ts`, `src/components/ThemeProvider.tsx`, and the
  header `ThemeToggle`. Light mode is implemented in CSS but temporarily
  disabled (`FORCE_DARK_THEME` in `uiPreferences.ts`); the toggle hides it
  until it ships. The selected preference is stored in `localStorage`
  under `ui.theme`; no backend storage is used because the current backend
  settings endpoints are platform/admin/trading settings rather than per-user
  visual preferences.
- theme tokens live in `src/index.css` as CSS variables for backgrounds,
  foreground text, muted text, primary/secondary/accent, borders, cards,
  surfaces, inputs, semantic states, and chart colors. Tailwind's
  `execution.*` colors resolve to those variables.
- new theme-aware components should prefer shared primitives such as
  `PlatformPageHeader`, `PlatformPanel`, `PlatformStatCard`,
  `TerminalDataGrid`, `premium-*`, `operator-*`, and `workspace-*`. For custom
  CSS, use the semantic variables instead of adding new dark-only `slate` or
  `stone` color literals.
- charts should be created through `createTradingChart` from
  `src/components/charts/lightweightTheme.ts` so chart backgrounds, grid lines,
  labels, borders, and crosshairs follow the selected theme.
- operator density preferences should persist across pages via `localStorage` key
  `operator-ui-density` using `src/hooks/usePersistentPreference.ts`.
  Backtest operator pages read this shared preference to keep comfort/dense layouts consistent.

## Supporting Docs

- [Frontend Architecture Notes](/home/chris/workspace/dydx-trading-bot/frontend/docs/architecture/README.md)
- [Multi-Portal Frontend](/home/chris/workspace/dydx-trading-bot/frontend/docs/architecture/MULTI_PORTAL_FRONTEND.md)
- [Fintech UI Standards](/home/chris/workspace/dydx-trading-bot/frontend/docs/architecture/FINTECH_UI_STANDARDS.md)
- [Troubleshooting](/home/chris/workspace/dydx-trading-bot/frontend/docs/guides/TROUBLESHOOTING.md)
- [Root Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
