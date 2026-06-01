# ExecutionLab Branding UI/UX Plan

## Current frontend structure

- React 19 + TypeScript + Vite application under `src/`.
- Multi-portal routing is selected by `VITE_APP_PORTAL_TYPE` in `src/App.tsx`, with protected routes wrapped by `src/components/MainLayout.tsx`.
- Public routes use `src/components/PublicSiteShell.tsx` and route pages in `src/pages/Landing.tsx`, `src/pages/Pricing.tsx`, and `src/pages/PublicServicePage.tsx`.
- Auth routes use `src/components/AuthExperienceShell.tsx` with `src/pages/Login.tsx`, `src/pages/Register.tsx`, 2FA, and password rotation pages.
- Authenticated workspace chrome is `src/components/Sidebar.tsx`, `src/components/Header.tsx`, and `src/components/WorkspaceCommandPalette.tsx`.
- Shared operator primitives live mainly in `src/components/ui/PlatformUI.tsx`; page spacing uses `src/components/PageContainer.tsx`.
- Visual support components currently include `src/components/DeFiIllustrations.tsx` and `src/components/PublicMarketPulse.tsx`.
- Static browser assets are in `public/`, including `public/favicon.svg`.

## Current styling approach

- Tailwind CSS is the primary styling system, with utility classes used directly in JSX.
- `src/index.css` imports Tailwind and defines global CSS variables, animation primitives, public-site styles, auth styles, workspace styles, and operator dashboard card styles.
- `tailwind.config.js` currently has no extended theme tokens.
- No CSS modules, SCSS, MUI, Chakra, shadcn, Bootstrap, or large component library is used in production code.
- The current visual direction is already dark and fintech-oriented, but it leans toward DefiArbitrage / crypto trading language and a teal/green palette.

## Branding gaps

- Product name, favicon, public shell, sidebar wordmark, and public copy still say `DefiArbitrage` or `dYdX Backtest System`.
- Public marketing language is crypto/arbitrage-specific rather than ExecutionLab's broader technical execution-lab positioning.
- Visual system uses many teal/emerald accents; ExecutionLab needs sharper cyan/blue with violet/signal green used sparingly.
- Public hero visuals include external imagery and crypto-specific illustration labels; this should become original ExecutionLab technical lab imagery.
- Shared primitives exist but are not explicitly branded with ExecutionLab tokens.
- Tailwind theme has not been extended with brand colors despite Tailwind being present.

## Proposed ExecutionLab visual direction

- Brand: `ExecutionLab`, with an original text-based wordmark and compact `EL` symbol using bracket/terminal/lab geometry.
- Tone: dark technical, premium, sharp, precise, confident, and engineering-led.
- Palette:
  - Background `#050816`
  - Surface `#0F172A`
  - Elevated surface `#111827`
  - Primary cyan `#00D4FF`
  - Primary dark `#0284C7`
  - Secondary violet `#7C3AED`
  - Success/signal green `#22C55E`
  - Text primary `#F8FAFC`
  - Text secondary `#94A3B8`
  - Border `#1E293B`
- Typography: keep existing Manrope/Sora/JetBrains Mono stack, because it already supports a clean technical feel.
- Layout: preserve existing grid-based public, auth, and operator layouts while tightening brand language and accent behavior.
- Motion: keep current subtle transitions and reduced-motion support; avoid adding decorative animation.

## Exact files planned for modification

- `BRANDING_UI_UX_PLAN.md`
- `BRANDING_UI_UX_CHANGELOG.md`
- `tailwind.config.js`
- `index.html`
- `package.json`
- `public/favicon.svg`
- `public/vite.svg`
- `docs/architecture/FINTECH_UI_STANDARDS.md`
- `src/index.css`
- `src/components/BrandMark.tsx`
- `src/components/PublicSiteShell.tsx`
- `src/components/Sidebar.tsx`
- `src/components/Header.tsx`
- `src/components/AuthExperienceShell.tsx`
- `src/components/PublicMarketPulse.tsx`
- `src/components/DeFiIllustrations.tsx`
- `src/components/ui/PlatformUI.tsx`
- `src/content/publicSite.ts`
- `src/pages/Landing.tsx`
- `src/pages/Pricing.tsx`
- `src/pages/PublicServicePage.tsx`
- `src/pages/Login.tsx`
- `src/pages/Register.tsx`
- `src/pages/TwoFactorAuth.tsx`
- `src/pages/ForcePasswordChange.tsx`
- `src/pages/Dashboard.tsx`

## Risks

- The app is still functionally a DeFi/trading platform, so copy must not erase necessary trading, dYdX, backtest, bot, or risk context inside authenticated product workflows.
- Broad copy changes can create tone drift if deep feature pages still use older DeFi wording; this pass will focus on shell, public, auth, shared primitives, and dashboard entry points.
- `src/index.css` is large and contains legacy style sections; changes should prioritize token overrides and shared class behavior rather than a risky full rewrite.
- Build may expose existing strict TypeScript or lint issues unrelated to branding; those will be separated from any errors caused by this work.
