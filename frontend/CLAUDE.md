# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Multi-Portal Architecture

This is a single React 19 + TypeScript + Vite workspace that builds three independent authenticated portals, selected by `VITE_APP_PORTAL_TYPE`:

- **Client Portal** (`client`): Dashboard, strategies, backtests, bot operations, profile, security, and credential management
- **Backoffice/CRM** (`backoffice`): Admin Hub, CRM clients, registration pipeline, hierarchy, commissions, Celery Ops, and operator settings
- **IB Portal** (`ib`): IB dashboard, client tree, applications/invitations, commission metrics, and referral tokens

Portal detection is in `src/app/portal.ts` via `getCurrentPortalType()`. Routes are registered in `src/App.tsx` with portal-gated rendering and `ProtectedRoute` + `allowedRoles` guards.

## Common Commands

```bash
# Development (port 5173 for client, 5174 for backoffice, 5175 for ib)
npm run dev              # Default client portal
npm run dev:client
npm run dev:backoffice
npm run dev:ib

# Production builds (outputs to dist/client-portal, dist/backoffice, dist/ib-portal)
npm run build
npm run build:client
npm run build:backoffice
npm run build:ib

# Validation
npm run lint
npm run typecheck
npm run test:contracts
```

## Backend Integration Rule

**The frontend must never talk directly to the dYdX bot API.** All integration flows through the Go backend on port 8888.

- Allowed: backend HTTP routes (`/api/*`), backend websocket routes (`/ws/*`)
- Not allowed: direct bot HTTP/websocket, direct database access

The dev server proxies `/api` and `/ws` to `VITE_API_BASE_URL` (defaults to `http://localhost:8888`).

## API Layer Architecture

Two API access patterns exist in production:

1. **`src/api.ts`**: Base Axios client with JWT auto-injection, 401 refresh logic, and core endpoints
2. **`src/api/enhancedClient.ts`**: Wrapper used by React Query hooks with `fetchWithAuth` + cookie-aware 401 retry

React Query hooks live in `src/api/hooks.ts` with cache tiers (`realtime`, `trading`, `static`) in `src/api/queryClient.ts`. Some screens still use direct `useState/useEffect` fetching (e.g., `BacktestList`, `BotManager`).

**Auth state for routing** comes from `src/store/auth.ts`, not `src/store/enhancedAuth.ts`.

## Response Shape Patterns

Backend envelope is typically `{ success, message, data, timestamp }`. Components often need nested extraction: `response.data?.backtests` (not `response.data.data.backtests`). Shapes are inconsistent—check callers before refactoring.

## Role-Based Access

Roles are defined in `src/auth/roles.ts`. Client routes allow `client`/`user`. IB routes allow `ib`/`sub_ib`. Backoffice routes allow `admin`, `super_admin`, `backoffice_admin`, `backoffice`, `operations_admin`, `compliance_admin`, `finance_admin`, `support_agent`, `read_only_auditor`, `security_analyst`, `accounting`, `marketing`, and `agent`.

Unauthorized authenticated users land on `/unauthorized`. Backend endpoints must enforce the same boundaries; frontend guards are UX layer only.

## Key Directories

- `src/app/` - Portal detection and route manifest
- `src/api/` - API clients, hooks, query config, websocket helpers
- `src/auth/` - Role definitions and normalization
- `src/pages/` - Route-level screens (including `client/`, `crm/`, `ib/` subdirs)
- `src/components/` - Reusable UI blocks
- `src/store/` - Zustand state (auth is in `auth.ts`)
- `apps/` - Portal app shells
- `packages/` - Shared exports (`shared-ui`, `shared-api`, `shared-auth`, `shared-types`)

## Launch Campaign Content

Public auth/coming-soon copy is centralized in `src/content/publicSite.ts`:
- `comingSoonMarketingContent`
- `icoLaunchpadContent`

Edit these for campaign changes; do not edit strings directly in `src/pages/Login.tsx` or `src/pages/ComingSoon.tsx`.

## Logging Conventions

Emoji-prefixed logs for console filtering:
- `🔐` - Auth flow
- `📊` - Backtest operations
- `🔌` - WebSocket/connectivity
- `❌` - Errors
- `🔧` - App/component lifecycle

## Theme System

The app supports Light, Dark, and System modes via `src/store/uiPreferences.ts` and `src/components/ThemeProvider.tsx`. Theme tokens are CSS variables in `src/index.css`. Charts should use `createTradingChart` from `src/components/charts/lightweightTheme.ts` to follow the selected theme.
