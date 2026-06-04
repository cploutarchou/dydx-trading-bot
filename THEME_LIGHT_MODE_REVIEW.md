# Light Mode Theme Review

Date: 2026-06-04

## Styling System Audit

- Frontend stack is React 19, TypeScript, Vite, Tailwind CSS v4, Zustand, React Router, TanStack Query, Lucide icons, Recharts, and Lightweight Charts.
- Styling is mostly Tailwind utility classes in `frontend/src/**/*.tsx`, backed by a large shared CSS layer in `frontend/src/index.css`.
- The app already has shared fintech primitives in CSS and components, including `premium-*`, `platform-*`, `operator-*`, `workspace-*`, `PublicSiteShell`, `PlatformUI`, `TerminalDataGrid`, and chart helpers.
- Tailwind config extends a small `execution` color palette, but most production UI still uses direct `slate`, `stone`, `gray`, `cyan`, `emerald`, `amber`, `rose`, and arbitrary hex utilities.
- Existing preference state was in `frontend/src/store/uiPreferences.ts`, but `ThemeMode` only allowed `dark` and `App.tsx` forced `data-theme="dark"` on every render.

## Dark-Only Usage Found

- Approximately 3,500 Tailwind dark-neutral color utilities are used across frontend source files.
- Approximately 760 direct CSS color literals or `rgb/rgba` calls exist across CSS, chart helpers, and components.
- High-risk hardcoded surfaces include:
  - App shell: `MainLayout`, `Header`, `Sidebar`, `WorkspaceCommandPalette`
  - Public pages: `Landing`, `Pricing`, `PublicServicePage`, `ComingSoon`, `PublicSiteShell`
  - Auth pages: `Login`, `Register`, `TwoFactorAuth`, `ForcePasswordChange`, `AuthExperienceShell`
  - Operator pages: `Dashboard`, `Backtests`, `BacktestDetailsV2`, `BotDashboard`, `Settings`, `AdminHub`
  - Admin/settings components: access control, auth, Mailgun, Telegram, Redis, AI market/news settings
  - Data-heavy components: `TerminalDataGrid`, `TableControls`, `BacktestList`, comparator/results panels, charts
  - Overlays and feedback: dialogs, modals, command palette, toasts, empty/error/loading states

## Light Mode Breakage Risks

- Direct `text-white` and `text-slate-*` headings would be low contrast on light surfaces.
- Direct `bg-slate-950/900/800` and `bg-stone-950/900` panels would remain dark islands inside light pages.
- Tables and sticky headers relied on dark backgrounds and would look heavy or mismatched in light mode.
- Form fields used dark input backgrounds and low-contrast placeholders.
- Chart canvases used dark backgrounds, dark grid/border colors, and static label colors.
- Turnstile was forced to `dark`, which would mismatch light auth/register pages.

## Implementation Decision

- Implemented a real theme foundation in `frontend/src/index.css` with semantic tokens for background, foreground, muted text, primary, secondary, accent, border, card, surface, input, success, warning, danger, info, and chart colors.
- Preserved the existing DeFi/fintech identity by keeping cyan/teal/emerald/violet semantics, but tuned light-mode values toward institutional navy, slate, white, and restrained accent color.
- Added a light-mode compatibility layer that remaps existing dark Tailwind utility usage into semantic light surfaces. This avoids brittle one-off component rewrites and covers legacy pages while new work can move toward semantic/shared primitives.
- Kept dark mode visually intact by scoping light-only compatibility rules to `:root[data-theme='light']`.

## Theme Selection and Persistence

- Theme preference is stored in `localStorage` under `ui.theme`.
- Supported values are `light`, `dark`, and `system`.
- `system` resolves from `prefers-color-scheme`.
- Backend settings were inspected. Existing backend settings are platform/admin/trading settings and not per-user visual preferences, so no backend persistence was added.
- An inline boot script in `frontend/index.html` sets `data-theme` before React starts to reduce first-paint flicker.

## Files Changed

- `frontend/src/store/uiPreferences.ts`
- `frontend/src/components/ThemeProvider.tsx`
- `frontend/src/components/ThemeToggle.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/Header.tsx`
- `frontend/src/index.css`
- `frontend/tailwind.config.js`
- `frontend/index.html`
- `frontend/src/components/charts/lightweightTheme.ts`
- `frontend/src/components/BacktestLightweightChart.tsx`
- `frontend/src/components/CumulativePnlChart.tsx`
- `frontend/src/components/TurnstileWidget.tsx`
- `frontend/README.md`

## Guidance for New UI

- Prefer shared primitives (`PlatformUI`, `TerminalDataGrid`, `premium-*`, `operator-*`, `workspace-*`) over raw color-heavy markup.
- Use semantic CSS variables from `index.css` for new custom CSS.
- If Tailwind utilities are used directly, prefer neutral structure plus shared classes; avoid new hardcoded dark-only `bg-slate-950`, `text-white`, and `border-slate-800` patterns unless the surface is intentionally dark in both themes.
- For charts, use `createTradingChart` so chart colors come from theme tokens.
