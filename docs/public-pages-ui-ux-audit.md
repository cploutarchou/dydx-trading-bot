# Public Pages UI/UX Audit

Scope: Coming Soon, ICO briefing, and Login pages in the React/Vite frontend.

## Original Problems Found

- Coming Soon used a dashboard-like layout with preview modes, progress bars, market-style ticker data, repeated sign-in actions, and dense operator language.
- ICO briefing mixed countdown, calendar actions, whitelist, resources, sale facts, utility, and timeline into competing cards without a clear investor reading order.
- Login included marketing panels, entry profile selectors, repeated ICO messaging, status cards, and unauthenticated "Back to dashboard" navigation.
- The public market ticker displayed hardcoded prices and changes from frontend content, not live API data.
- Login displayed backend-provided auth errors and logged login error detail, which could create account-enumeration or sensitive-response exposure risk.
- Shared public-page patterns existed mostly as page-specific Tailwind/CSS compositions rather than reusable primitives.

## UX Decisions Made

- Established one consistent public shell width for these pages: `max-w-6xl`.
- Kept the dark DeFi identity but reduced gradients, glow, borders, nested panels, badges, and motion.
- Reframed Coming Soon as a launch landing page with one primary CTA, one secondary CTA, three capabilities, and compact launch status.
- Rebuilt ICO around investor information hierarchy: overview, key facts, timeline, utility, documentation, whitelist request, and risk/compliance notice.
- Simplified Login to authentication only: identity, controlled-access copy, credentials fields, sign-in, account recovery, and return-to-launch navigation.
- Removed fake market-price/ticker presentation entirely from the redesigned pages and centralized launch copy.

## Components Created Or Changed

- Added `src/components/PublicPagePrimitives.tsx`:
  - `PublicLaunchShell`
  - `PublicStatusPill`
  - `PublicSectionHeading`
  - `PublicCapabilityList`
  - `PublicFactGrid`
  - `PublicTimeline`
  - `PublicCountdown`
  - `PublicDisclosure`
  - `PublicResourceLink`
- Added `src/utils/publicPages.ts` for ICO countdown/date/email helpers.
- Added `src/utils/loginForm.ts` for login validation and disabled-submit behavior.
- Added `src/app/publicAccess.ts` for testable Coming Soon bypass routes and public navigation paths.
- Updated `src/index.css` with restrained public-page tokens/classes.

## Accessibility Improvements

- Added visible, semantic form labels and `aria-invalid`/`aria-describedby` for login and whitelist fields.
- Added `role="alert"` for validation/auth errors and `role="status"` for whitelist success.
- Added password show/hide button with accessible names.
- Kept CTA touch targets at least 44px high.
- Used semantic headings and a real ordered timeline.
- Countdown uses `role="timer"` with polite live updates.
- Removed tiny ticker text and decorative motion-heavy content.

## Responsive Improvements

- Primary CTAs stack full-width on mobile and remain visible.
- Page panels use simple single-column mobile flow and two-column desktop flow.
- Fact grids and capability lists collapse without horizontal overflow.
- Form controls keep stable sizing and do not rely on small badges or mode selectors.
- Screenshot capture manifest now includes `/`, `/ico`, and `/login`.

## Content And Business-Data Concerns

- ICO sale values remain frontend-configured in `src/content/publicSite.ts`; they are not API-driven.
- Fundraising target, caps, total supply, public allocation, network, sale status, and sale date need business/legal confirmation before production publication.
- Documentation links point to repository documentation/architecture pages and should be replaced with final whitepaper, tokenomics, and participation/KYC policy URLs.
- Whitelist request currently uses a `mailto:` handoff because no whitelist API endpoint was found.
- Account recovery uses `mailto:support@executionlab.io` because no public password recovery route was found.

## Remaining Limitations

- Local responsive screenshots have now been captured for the three public routes; final production-preview route rendering still depends on backend CORS/config availability.
- Without a whitelist API, loading/success states can only confirm the mail client handoff, not server-side receipt.
- Coming Soon status text depends on `/api/v1/public/app-config` for the optional launch message, while the page structure itself remains frontend-rendered.

## Second UI/UX iteration

### Problems That Remained After The First Redesign

- Coming Soon still had a left-heavy hero, excessive desktop whitespace, duplicate sign-in placement, repeated launch copy, an oversized launch-status card, and product capabilities too low in the page.
- ICO briefing still read like documentation: narrow hierarchy, a full-width countdown block, small facts, visually similar sections, buried whitelist form, and timeline labels disconnected from their items.
- Login still used a wide two-column composition with a stretched auth card, weak focal point, and underspecified button/touch states.

### Layout Changes Implemented

- Replaced the Coming Soon desktop hero with a two-column composition: launch copy/actions/status on the left and a restrained research/validate/execute/monitor workflow visual on the right.
- Replaced the oversized Coming Soon launch panel with a compact three-item status strip.
- Reworked ICO into a briefing layout: hero plus compact sale summary panel, readable sale facts, timeline and whitelist side by side, then utility/documentation and collapsed secondary details.
- Simplified Login to a single centered authentication column around 460-520px wide, slightly above center on desktop and comfortably fitting mobile height.
- Updated the screenshot capture viewports to `390x844`, `768x1024`, `1440x900`, and `1920x1080`.

### Typography Changes

- Increased hero and section hierarchy with responsive `clamp()` sizes.
- Raised critical body/fact/form text to readable 16px+ sizing where appropriate.
- Kept supporting labels at 13-14px minimum and removed cramped microcopy from primary content.

### Page-Width Changes

- Added public page layout tokens around a `76.5rem` maximum container.
- Added an auth-width token around `31rem`.
- Used fixed desktop side panels around 400-420px for the workflow, sale summary, and whitelist form while preserving fluid text columns.

### Components Refactored

- Refactored `PublicPagePrimitives` into shared public-page building blocks:
  - `PublicPageShell`
  - `PublicHeader`
  - `PageContainer`
  - `StatusBadge`
  - `PrimaryButton`
  - `SecondaryButton`
  - `FormField`
  - `PasswordField`
  - `SaleCountdown`
  - `SaleFacts`
  - `SaleTimeline`
  - `DocumentationPanel`
  - `WhitelistForm`
  - `ProductWorkflow`
  - `Accordion`
- Kept aliases for the prior public primitive names where useful to avoid unnecessary churn.

### Interaction Improvements

- Added stronger default, hover, active, disabled, loading, and focus-visible states for shared public buttons.
- Added smooth anchor scrolling for the whitelist CTA and disabled it under reduced-motion preferences.
- Added subtle workflow/timeline/card hover feedback while respecting `prefers-reduced-motion`.
- Prevented duplicate whitelist submissions while a request is loading or after a mailto request is prepared.
- Preserved login username/password autocomplete values for password managers.

### Responsive Corrections

- Removed mobile header action collision on the ICO page by limiting the header to one utility action.
- Removed duplicate sign-in CTAs from Coming Soon; sign-in appears once in the hero.
- Verified no horizontal overflow at all required viewports.
- Increased mobile touch targets for auth links, password visibility, buttons, and accordions.
- Kept mobile hero/action stacking readable without nested card-heavy layouts.

### Accessibility Corrections

- Kept semantic labels, `aria-invalid`, and error descriptions for login and whitelist forms.
- Kept auth failures generic and screen-reader announced.
- Kept password show/hide as a real button with an accessible label.
- Added minimum 44px interactive target sizing to accordion summaries and auth links.
- Confirmed reduced motion disables workflow node animation.

### Before/After Screenshot Paths

- Before: `frontend/docs/screenshots/public-pages-baseline/`
- After: `frontend/docs/screenshots/public-pages-second-iteration/`
- Captured routes: `/`, `/ico`, `/login`
- Captured sizes: `390x844`, `768x1024`, `1440x900`, `1920x1080`

### Remaining Limitations

- ICO values remain frontend-configured campaign content and still require business/legal confirmation before production publication.
- The whitelist flow still uses `mailto:` because no whitelist submission API was found.
- Production preview from `localhost:4173` / `127.0.0.1:4173` is blocked by backend CORS for `/api/v1/public/app-config` and `/api/v1/auth/registration-status`; dev rendering on `127.0.0.1:5174` was used for final UI browser validation.
