# 17 — Browser Compatibility

## Declared support

`browserslist` (`package.json`): Firefox ≥110, Chrome ≥111, Safari ≥16.4, Edge ≥111 — a modern-evergreen matrix; no IE/legacy targets. Build targets ES2020 (`tsconfig` target) via Vite esbuild; CSS uses custom properties, `:has`-free selectors per index.css review; no vendor-prefix dependencies beyond autoprefixer (installed).

## Evidence status

| Browser | Evidence in repo | This audit |
|---|---|---|
| Chromium | `scripts/capture-responsive-screenshots.mjs` (Chrome CLI), `verify-crypto-background-browser.mjs` (raw CDP: reduced-motion, print media, popstate, longtask/CLS/LCP/FPS) — public routes only | ✅ full live pass |
| Firefox | **none** | ❌ not run |
| Safari/WebKit | **none** | ❌ not run |
| Edge | screenshot script detects Edge as fallback | ❌ not run |

**Finding (P3, process):** no cross-browser evidence exists anywhere in the repo; prior responsive sign-offs (now stale) were Chrome-only.

## Risk areas when Firefox/WebKit get tested

1. **Date inputs** (`input[type=date]`) — styling and value behavior diverge on WebKit; forms rely on them heavily (backtest window). Verify fill/UX, not just CSS.
2. **WebSocket reconnection timing** — Safari throttles background timers aggressively; the 30s heartbeat + backoff should be tested under tab-backgrounding on Safari.
3. **localStorage in private modes** — token persistence wraps in try/catch already (verified `api.ts:1973-1975`), good; verify the whole login path in Firefox private window.
4. **CSS `color-mix`/modern functions** — grep index.css before trusting; if used, confirm 16.4 baseline covers.
5. **CryptoBackground canvas** — WebKit rAF throttling in background tabs; script has static fallback + tests, but verify on real Safari.
6. **Clipboard API** (backup-code copy in 2FA) — needs user gesture + permissions on Safari; code uses explicit click handler (OK), verify behavior.
7. **Focus behavior** in dialogs (ActionDialog focus-trap) — WebKit focus quirks are the classic breakage.

## Recommendation

Add a **Playwright project matrix** (chromium + firefox + webkit) for the smoke subset of the E2E matrix (rows 1, 8, 20: login, backtest form validation, public tour) rather than the full suite — cost-efficient coverage of the risky surface. Local `npx playwright test --project=webkit` needs the WebKit runtime download; CI carries the three-browser cost only on the smoke job.
