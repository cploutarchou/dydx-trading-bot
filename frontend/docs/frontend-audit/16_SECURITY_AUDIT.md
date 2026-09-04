# 16 — Security Audit (client-side)

Depth: full static pass over `src/`, `apps/`, `packages/`, `public/`, build config + live behavioral checks (login, role boundaries, backend enforcement probes). Backend enforcement was verified independently — frontend guards are correctly treated as UX only.

## Confirmed issues

| ID | Finding | Evidence | Severity | Fix direction |
|---|---|---|---|---|
| ✅ SEC-01 | ~~Access JWT mirrored to localStorage~~ **RESOLVED 2026-09-05: setToken no longer persists; boot scrubs the legacy key; session recovery is cookie-driven (verified live: fresh reload authenticates with zero JWT in storage)** (`_dydx_access_token`) — XSS-stealable fallback bearer for a trading app. Cookie session is primary (`getCurrentUser` prefers cookie, `api.ts:2340-2346`) so the fallback is removable | `src/api.ts:1972,2022,2118` | **P1** | Drop localStorage persistence; rely on HttpOnly cookie (+cookie handshake for WS — see SEC-02) |
| ✅ SEC-02 | ~~WS auth via `?access_token=` URL param~~ **RESOLVED 2026-09-05: connectSocket is cookie-first — the backend accepts the `dydx_session` cookie on WS upgrades (verified in `middleware/auth_token.go`) with origin-checked handshake; the query token remains only as a fallback for cookie-less flows** on every authenticated socket (`/api/v1/backtests/{id}/live`, `/ws/backtests|bots|strategies`) — bearer lands in proxy/access logs & any TLS-terminating hop. Cookie-based handshake already works for the `/ws` manager | `src/api/origin.ts:222,234`; builders `api.ts:4259-4283` | **P1** | Send token via first message or `Sec-WebSocket-Protocol`, or cookie-auth the upgrade (backend already sets session cookie) |
| SEC-03 | `roleMatches` leniency: any unknown/custom role passes every route list containing a backoffice role; admin/super_admin match everything | `src/auth/roles.ts:101-117` | P2 (UI-layer only — **backend 403 verified**) | Fail-closed for unknown roles on backoffice lists |
| 🟡 SEC-04 | No CSRF token on cookie-authenticated mutations — **verified backend posture (2026-09-05): auth cookie defaults to SameSite=Lax (blocks cross-site POSTs); SameSite=None is opt-in via AUTH_COOKIE_SAMESITE with forced Secure; CORS is origin-allowlisted with credentials. Residual recommendation: enforce Origin/Sec-Fetch-Site on mutating methods when SameSite=None is deployed** (`withCredentials` everywhere, JSON bodies). JSON content-type forces preflight for XHR, but verify backend Origin/`Sec-Fetch-Site` checks given cross-subdomain `SameSite=None` cookies | `api.ts:1778`, `enhancedClient.ts:123` | P2 (verify server) | Backend: Origin allowlist on mutations; document posture |
| SEC-05 | No CSP, Referrer-Policy, or frame-protection (meta absent; server headers not in this repo) | `index.html` | P2 | Add meta referrer + server CSP/frame-ancestors |
| SEC-06 | Mnemonic entry as visible `<textarea>` in DYDXKeyManager (BotManager correctly masks — inconsistent secret UX) | `DYDXKeyManager.tsx:354-364` | P3 | password input + reveal toggle |
| SEC-07 | WebSocketManager `debug:true` default logs full WS payloads (positions, trading data) to console in prod | `websocket.ts:84,241` | P3 | default false / gate on DEV |
| SEC-08 | CSV export lacks formula-injection neutralization (`=`,`+`,`-`,`@` prefixes from API strings) | `BacktestComparator.tsx:332-340`, `TableControls.tsx:215-222` | P3 | prefix `'` on risky cells |
| SEC-09 | Avatar upload MIME/size validated client-side only (browser-spoofable; render risk low as data-URL img) | `ProfileSettings.tsx:57-84` | P3 | server re-validation (confirm backend) |
| SEC-10 | News `href={article.url}` without https-scheme allowlist (React 19 blocks `javascript:` — defense-in-depth only) | `CoinDeskNewsPanel.tsx:77,123` | P3 | `https:` check |
| SEC-11 | `sanitizeHost` doesn't allowlist platform domains (admin-controlled input → arbitrary host links) | `utils/portalSubdomainSettings.ts:48-56` | P3 | suffix allowlist `executionlab.io` |
| SEC-12 | Stale `localStorage.getItem('token')` (never written) — correctness bug with security flavor: WS built from it is unauthenticated (see FE-FN-01) | `Backtests.tsx:710` | P1 (as correctness) | delete line |
| SEC-13 | Build config `define`-inlines every `VITE_*` from encrypted profile into the bundle — safe today (URLs/site key) but silently exposes any future secret-prefixed value | `vite.config.ts:169-173` | P3 (process) | CI grep for secret patterns in dist |

## Verified clean (no action)

- **XSS surface:** zero `dangerouslySetInnerHTML`/`innerHTML`/`eval`/`new Function` across src+apps+packages; no HTML-rendering markdown libs; only URL-attrs dynamic (React 19 URL guard active).
- **Open redirects:** none — post-login targets hardcoded by role (`Login.tsx:77-113`); no `redirect=`/`next=` params anywhere; no `window.open`; no postMessage listeners.
- **Refresh flow:** refresh token never JS-readable (HttpOnly cookie; `POST /auth/refresh` withCredentials); interceptor single-flight + queue + `_retry` + 10s cooldown — cannot loop; session-expired event → controlled logout.
- **2FA/TOTP:** secret + backup codes memory-only in store (never persisted/logged); QR via img; one-time-code semantics on inputs.
- **Secrets in repo/logs:** none — no `sk_`/`whsec_`/JWT-prefix literals; console logs print labels/errors only, never token values (111 statements reviewed).
- **Source maps:** off in build; dist contains zero `.map` (verified).
- **Password handling:** autocomplete semantics correct everywhere; no paste blocking; visibility toggles don't log.
- **Turnstile:** public site key only; self-disables on localhost — server-side enforcement is the contract (registration tested OK locally without it).
- **`target=_blank`:** always `rel="noreferrer"`.
- **Backend authorization (independent probes):** client token → 403 on `/api/v1/admin/users` and `PUT /api/v1/settings` — frontend hiding is not the security boundary. ✅

## Frontend-vs-backend boundary statement

Every role-gated UI surface in this app relies on backend enforcement as the real boundary — and the backend does enforce (verified). The remaining frontend duties are: fail-closed UI (SEC-03), no credential material in JS-readable storage (SEC-01), and no credential leakage in URLs (SEC-02).


## Backend posture verification (FE-019, 2026-09-05)

| Control | Verified state | Evidence |
|---|---|---|
| Auth cookie SameSite | Defaults **Lax**; `None` only via `AUTH_COOKIE_SAMESITE=none`, which forces `Secure` | `backend/internal/routes/auth_routes.go:176-195` |
| CORS | Env-driven origin allowlist; credentials only for allowed origins | `backend/internal/middleware/middleware.go:13-39` |
| WS upgrade auth | Cookie (`dydx_session`) accepted **before** query token; query fallback restricted to WebSocket upgrades only; upgrader origin-checked | `backend/internal/middleware/auth_token.go:12-43`, `bot_api_delegate_routes.go:27-29` |
| CSRF residual | With default Lax cookies, cross-site POSTs carry no cookie → protected. With opt-in None, form-based JSON smuggling is not explicitly blocked → recommend Origin/`Sec-Fetch-Site` enforcement on mutations | backend gap, filed as recommendation |
