# Findings — FRONT (`frontend/`, React + TypeScript + Vite operator dashboard)

Audit date: 2026-09-19. Branch: `audit/2026-09-19-all`. Read-only investigation; no source file was modified.

Scope notes (things that were checked and are fine, so they are not findings):

- Access JWT is memory-only; `localStorage` holds only a boolean session hint (`src/api.ts:2004-2029`). Legacy token keys are scrubbed at start-up (`src/api.ts:1794-1800`).
- No `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function`, or `window.open` anywhere under `src/`.
- No direct bot-API access: no `:8889` / bot host reference in `src/`, `vite.config.ts`, `.env.example`, `index.html` or the built `dist/`. `src/api/botApi.ts` rides the shared backend axios client and only calls `/api/v1/*`, `/health`, `/ready`.
- WebSocket URLs carry no token once a session is established (`src/api.ts:4344-4347`).
- `.env.example` holds only public `VITE_*` values; `frontend/.env` and `dist/` are git-ignored; `vite.config.ts:171-176` bakes only `VITE_`-prefixed keys into the bundle. A grep of the existing `dist/` for secret markers returned nothing.
- CSV export is formula-injection safe (`src/utils/csv.ts`), external links go through `src/utils/urlSafety.ts`.
- `frontend-quality` in `.github/workflows/bot-quality.yml:748-803` does run the full unit suite (`npm test`), plus lint, typecheck, build and Playwright smoke.
- `BotManager` start/stop/restart/delete all go through a confirmation dialog (`src/components/BotManager.tsx:636-676`, `1354-1357`).

---

## P1

### FRONT-P1-001 — Every mutation is auto-retried once, including non-idempotent trading POSTs
- Priority: P1 | Type: reliability | Area: api/queryClient
- Evidence: frontend/src/api/queryClient.ts:107-111
  ```ts
      mutations: {
        // Retry mutations once
        retry: 1,
        retryDelay: 1000,
      },
  ```
- Impact: `useCreateBotInstance`, `useStartBotInstance`, `useQuickDeployBot`, `useCreateBacktest`, `useStartStrategyRuntimeMutation`, `useStopStrategyRuntime`, CRM/IB commission and role mutations all inherit this default (no hook in `src/api/hooks.ts` overrides `retry` for a mutation; `grep -rn "retry:" src` shows only query-level overrides). When the first POST reaches the backend but the response is lost (timeout, 502 from the proxy, connection reset) the request is silently sent a second time one second later: duplicate backtest runs, duplicate runtime creation, a second `start` against a runtime that is already starting. The frontend sends no idempotency key (`grep -rni idempotency frontend/src` → no matches), so the backend cannot deduplicate. Because most `src/api.ts` methods re-throw `new Error(getErrorMessage(error))`, even deterministic 4xx rejections are retried.
- Root cause: a blanket React Query default written for reads was applied to writes; unlike the query default (`queryClient.ts:90-98`) it does not even inspect the HTTP status.
- Fix: set `mutations: { retry: false }` globally. Opt individual, provably idempotent mutations (PUT settings) into retry explicitly. For start/create flows add a client-generated `Idempotency-Key` header once the backend supports it (cross-service item).
- Verification: new vitest `src/api/queryClient.test.ts` asserting `queryClient.getDefaultOptions().mutations?.retry === false`; a jsdom test that a rejected `useCreateBacktest` mutation calls the mocked `botApi.createBacktest` exactly once. `cd frontend && npm run test`.
- Effort: S | Blast radius: med | Depends on: —

### FRONT-P1-002 — Stopping a live strategy runtime needs no confirmation and is bound to a bare `s` keypress
- Priority: P1 | Type: bug | Area: components/StrategyManager
- Evidence: frontend/src/components/StrategyManager.tsx:1301-1305 (shortcut) and 929-954 (handler)
  ```tsx
      if (key === 's') {
        event.preventDefault();
        void handleRuntimeToggle(strategy);
        return;
      }
  ```
  ```tsx
      if (!shouldStop) {
        openStartDialog(strategy);
        return;
      }
      ...
        const response = await stopRuntimeMutation.mutateAsync({ strategyId: strategy.id });
  ```
- Impact: starting goes through a readiness dialog, but when the runtime is active `handleRuntimeToggle` calls the stop mutation immediately. The handler is attached to the focusable card (`StrategyManager.tsx:1733-1738`, `tabIndex={0}` + `onKeyDown`) and only filters modifier keys (`1293-1297`), so a stray `s` while a card — or any button inside it, since the event bubbles — has focus halts a mainnet strategy. `BotManager` itself warns that after a stop "Open positions may still need operator review" (`BotManager.tsx:652`), i.e. positions are left unmanaged. The key handler also ignores `runtimePending`, so a key-repeat fires several stop requests (each of which is additionally retried, see FRONT-P1-001). `BotManager` already confirms the same action, so behaviour is inconsistent across the two desks.
- Root cause: the stop branch was never routed through a confirmation step; the keyboard shortcut reuses the click handler without a target/pending guard.
- Fix: route the stop branch through the existing confirm dialog component used by `BotManager` (title with strategy name + network, danger tone for mainnet). In `handleStrategyCardKeyDown` return early when `event.target !== event.currentTarget` or when `runtimePending[strategy.id]` is set; the shortcut should only open the dialog.
- Verification: new `StrategyManager.dom.test.tsx`: focus a running strategy card, `userEvent.keyboard('s')`, assert the stop API mock is not called until the dialog's confirm button is clicked. `cd frontend && npm run test`.
- Effort: M | Blast radius: low | Depends on: —

### FRONT-P1-003 — Wallet mnemonic can be written to the browser console on a failed create; seed field is offered to password managers
- Priority: P1 | Type: security | Area: components/BotManager, api
- Evidence: frontend/src/components/BotManager.tsx:691-697 and 716-717; frontend/src/api.ts:4916-4924
  ```tsx
          credentials: {
            address: createForm.address,
            mnemonic: createForm.mnemonic,
            ...
            secret_phrase: createForm.mnemonic,
  ```
  ```tsx
      } catch (err) {
        console.error('Failed to create bot:', err);
  ```
- Impact: `botApi.createBotInstance` → `ApiClient.requestJson` (`api.ts:4916-4924`) does not wrap errors, and the response interceptor ends with `return Promise.reject(error)` (`api.ts:1989`), so `err` is the raw `AxiosError`. Its `config.data` is the serialized request body, which contains the seed phrase twice. Any failed create (validation error, 500, network drop) therefore prints the mainnet mnemonic into DevTools, where it is readable by browser extensions, captured by Playwright traces / screen shares / support screenshots, and would be shipped verbatim by any console-capturing error reporter added later. This violates the service rule "never log tokens" and the engineering standard ("never log passwords, tokens, or private keys"). Separately, the input (`BotManager.tsx:1109-1115`) is `type="password"` with no `autoComplete` attribute, so browsers offer to save the seed phrase in the password manager / sync it to the cloud.
- Root cause: generic `console.error(label, err)` pattern used on a request that carries a secret; `requestJson` is the one API path that does not normalise errors to a message.
- Fix: in `handleCreateBot` log only `toOperatorErrorMessage(err, …)`; make `requestJson` reject with a sanitized error (message, status, trace id — no `config`). Add `autoComplete="off"` plus `data-1p-ignore`/`data-lpignore` and `spellCheck={false}` to the mnemonic input and clear `createForm.mnemonic` in a `finally`. Longer term prefer selecting a stored key (`/api/v1/keys`) over typing a seed into this form.
- Verification: vitest: mock `botApi.createBotInstance` to reject with an `AxiosError` whose `config.data` contains `"abandon abandon"`, spy on `console.error`, assert no call argument stringifies to that text. Manual: submit the form against a stopped backend and inspect the console.
- Effort: S | Blast radius: low | Depends on: —

### FRONT-P1-004 — Logout does not clear the React Query cache; the next user on the same browser is served the previous user's data
- Priority: P1 | Type: security | Area: store/auth, components/Sidebar
- Evidence: frontend/src/components/Sidebar.tsx:47-51; frontend/src/store/auth.ts:209-212
  ```tsx
    const handleLogout = () => {
      logout();
      onClose?.();
      navigate('/login');
    };
  ```
  ```ts
        logout: () => {
          api.logout();
          set(buildLoggedOutState());
        },
  ```
- Impact: the only code that calls `queryClient.clear()` on logout is `useLogout()` (`src/api/hooks.ts:402-414`), which has zero callers (`grep -rn "useLogout()" src` → none). Logout is an SPA navigation, not a reload, and query keys are not user-scoped (`queryClient.ts:34-36`: `['bots', params]`, `['strategies']`), with `staleTime` 5 min / `gcTime` 10 min (`queryClient.ts:85-87`). A second account that logs in within that window is rendered the previous account's bots, strategies, backtests, CRM client lists and commission figures from cache without a refetch. The same applies to the forced `auth:session-expired` path in `App.tsx:264`.
- Root cause: two logout implementations; the one that is wired to the UI lost the cache clear.
- Fix: clear the cache in one choke point — subscribe to the existing `auth:changed` event (`detail.authenticated === false`) next to the `QueryClient` and call `queryClient.clear()`; delete the unused `useLogout` or make the Sidebar use it.
- Verification: vitest: seed `queryClient.setQueryData(['strategies'], [...])`, call `useAuthStore.getState().logout()`, assert `queryClient.getQueryData(['strategies'])` is `undefined`.
- Effort: S | Blast radius: low | Depends on: —

### FRONT-P1-005 — Go-live dialog renders "Free Collateral" with the sign stripped and missing values as `$0.00`
- Priority: P1 | Type: bug | Area: utils/format, components/StrategyManager
- Evidence: frontend/src/utils/format.ts:26-34; frontend/src/components/StrategyManager.tsx:2314
  ```ts
  export const formatUsdFixed = (value: number | undefined | null): string =>
    typeof value === 'number' && Number.isFinite(value)
      ? `$${Math.abs(value).toLocaleString('en-US', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}`
      : '$0.00';
  ```
  ```tsx
                            {formatUsdFixed(startDialogReadiness.available_collateral)}
  ```
- Impact: `formatUsdFixed` applies `Math.abs`, so a negative free collateral (an under-margined dYdX subaccount) is shown to the operator as a positive balance in the dialog that gates a mainnet start; an absent/NaN field is shown as a real-looking `$0.00` instead of "unavailable". The same helper renders trade size, capital allocation and minimum collateral in that dialog (`StrategyManager.tsx:2322, 2415, 2421`) and all IB/CRM commission and rebate figures (`pages/ib/IBCommissions.tsx:62-77`, `pages/crm/CRMCommissions.tsx:130-203`), where a negative net commission (clawback) would also read as positive. `formatUsd` (`format.ts:12-15`) has the same two behaviours.
- Root cause: unsigned helpers created for magnitudes were reused for balances; "no data" and "zero" share one rendering.
- Fix: keep the sign in `formatUsd`/`formatUsdFixed` (`-$1,234.50`) and return an em dash for non-finite/undefined input; offer an explicit `formatUsdMagnitude` for the few places that really want `abs`. Update `src/utils/format.test.ts` accordingly.
- Verification: `cd frontend && npx vitest run src/utils/format.test.ts` with new cases `formatUsdFixed(-12.5) === '-$12.50'` and `formatUsdFixed(undefined) === '—'`.
- Effort: S | Blast radius: med | Depends on: —

### FRONT-P1-006 — Manual runtime form defaults to mainnet and lets `chain_id` and `is_testnet` contradict each other
- Priority: P1 | Type: bug | Area: components/BotManager
- Evidence: frontend/src/components/BotManager.tsx:566-571 and 691-699
  ```tsx
    const [createForm, setCreateForm] = useState({
      instance_id: '',
      chain_id: 'dydx-mainnet-1',
      address: '',
      mnemonic: '',
      is_testnet: false,
  ```
  ```tsx
            network: createForm.is_testnet ? 'testnet' : 'mainnet',
            chain_id: createForm.chain_id,
  ```
- Impact: the "Chain ID" select (`1078-1086`) and the "Use Testnet" checkbox (`1162-1170`) are independent controls feeding one payload. Selecting "dYdX Testnet" without ticking the box submits `chain_id: 'dydx-testnet-4'` with `network: 'mainnet'` and `trading_params.is_testnet: false` (and vice versa); which field wins is left to downstream services, so an operator who believes they created a testnet runtime can end up trading real funds. The form also defaults to mainnet, whereas the strategy start dialog defaults to testnet (`StrategyManager.tsx:741`). The numeric inputs store `parseFloat('')`/`parseInt('')` → `NaN` (`1127, 1141, 1156`), which `JSON.stringify` turns into `null` for `usd_per_trade`, `zscore_threshold`, `max_half_life`; `handleCreateBot` validates only the three text fields (`679`).
- Root cause: duplicated source of truth for the network; no schema validation on the create form.
- Fix: keep a single `network` control and derive `chain_id`/`is_testnet` from it; default to testnet; validate numeric fields (finite, `usd_per_trade >= 1`, `zscore_threshold > 0`) before enabling submit; require an explicit typed confirmation for mainnet.
- Verification: jsdom test: choose testnet, submit, assert the mocked `createBotInstance` payload has `network === 'testnet'`, `chain_id === 'dydx-testnet-4'`, `is_testnet === true`; clear the USD field and assert submit is blocked.
- Effort: M | Blast radius: low | Depends on: —

---

## P2

### FRONT-P2-007 — Runtime cards show `$0` P&L / `0` open positions when no stats were received
- Priority: P2 | Type: bug | Area: components/BotManager
- Evidence: frontend/src/components/BotManager.tsx:300-303
  ```tsx
    const stats = rawStats ? mapBotStats(rawStats) : { ...EMPTY_BOT_STATS };
    const hasStatsPayload = rawStats !== null;
    const shouldShowStatsWarning =
      stats.degraded === true || (!!liveStatsQuery.error && !hasStatsPayload);
  ```
- Impact: while the first payload is loading, when the REST stats query fails (`statsQuery.error` is never consulted), or when the stream is disabled, the card renders the zeroed `EMPTY_BOT_STATS` (`220-230`) as real numbers: "P&L $0", "Open 0", "Closed 0", "Trades 0" (`389-406`). `mapBotStats` likewise defaults every absent field to `0` via `toNumber` (`76-83`). An operator deciding whether a stopped/failed runtime still has exposure sees "Open 0" when the truth is "unknown".
- Root cause: no distinction between "zero" and "no data" in the view model.
- Fix: render an em dash/skeleton for all four tiles when `!hasStatsPayload`; include `statsQuery.isError` in `shouldShowStatsWarning`; show `stats.last_update` age on the collapsed card.
- Verification: jsdom test rendering `BotCard` with both hooks mocked to `{ data: undefined, error: new Error('x') }`; assert the P&L tile shows `—` and the warning banner is present.
- Effort: S | Blast radius: low | Depends on: —

### FRONT-P2-008 — A failed system-status call is replaced by a fabricated "operational / healthy" payload
- Priority: P2 | Type: observability | Area: api/botApi
- Evidence: frontend/src/api/botApi.ts:437-458
  ```ts
    private static readonly SYSTEM_STATUS_FALLBACK: Entity = {
      status: 'operational',
      components: {
        database: 'healthy',
        bot_api: 'healthy',
  ```
  ```ts
      } catch {
        return BotApiClient.SYSTEM_STATUS_FALLBACK;
      }
  ```
- Impact: when `/api/v1/system/status` times out, 5xx-es, or the backend is down, callers receive a success result claiming every component is healthy. `useSystemStatus`, `pages/Backtests.tsx:615-622` (capacity panel → queue depth 0, active jobs 0, no sync lock) and `SyncHealthPanel.tsx:111-114` never enter their error state, so the outage is invisible exactly when the operator needs the signal. `getHealth`/`getReadiness` degrade to `unknown`, which is acceptable; this one asserts health it did not observe.
- Root cause: error silenced with an optimistic default.
- Fix: let the error propagate (React Query already handles retry and error state), or return `{ status: 'unknown', components: {} }` and have consumers render "status unavailable". Update `src/api/botApi.test.ts`.
- Verification: `cd frontend && npx vitest run src/api/botApi.test.ts` with a case where the client mock rejects and the result must not contain `'operational'`/`'healthy'`.
- Effort: S | Blast radius: low | Depends on: —

### FRONT-P2-009 — Managed WebSocket (and its 5 s request timer) leaks when the component unmounts during the handshake
- Priority: P2 | Type: perf | Area: api/hooks (`useManagedWebSocket`)
- Evidence: frontend/src/api/hooks.ts:305-307
  ```ts
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.close();
        }
  ```
- Impact: cleanup closes the socket only if it is already `OPEN`. If the effect is torn down while the socket is `CONNECTING` (fast navigation, expanding/collapsing a bot card, React StrictMode double-mount, any dependency change), the socket is left alive with its handlers attached. When it opens, `onopen` (`185-195`) still runs `onOpen`, which for `useBotRuntimeStatsStream` starts `window.setInterval(requestRuntimeState, 5000)` (`hooks.ts:831`); its cleanup handle is stored in a closure nobody will call again. Result: an orphaned connection per occurrence that polls the backend (and through it the bot service) every 5 s until the tab closes, plus state updates on an unmounted tree. One stream is opened per RUNNING runtime card (`BotManager.tsx:289-293`), so the leak scales with the desk.
- Root cause: the guard was written to avoid the "closed before established" console warning.
- Fix: in cleanup, null out `onopen/onmessage/onerror/onclose` and call `socket.close()` for both `OPEN` and `CONNECTING`; additionally bail out at the top of `onopen` when `closedByEffect` is true.
- Verification: vitest with a fake `WebSocket` class: mount the hook, unmount before firing `onopen`, then fire it; assert `close` was called and `onOpen` was not invoked (`vi.getTimerCount() === 0`).
- Effort: S | Blast radius: low | Depends on: —

### FRONT-P2-010 — Backtest push sockets are all closed and reopened on every progress update
- Priority: P2 | Type: perf | Area: pages/Backtests
- Evidence: frontend/src/pages/Backtests.tsx:717-733
  ```tsx
        ws.addEventListener('message', () => {
          void queryClient.invalidateQueries({ queryKey: ['backtests', 'active-statuses'] });
          void queryClient.invalidateQueries({ queryKey: ['backtests'] });
        });
  ...
      return () => {
        // Component unmount: close all sockets
        for (const ws of sockets.values()) {
  ```
- Impact: the cleanup is not unmount-only — it runs whenever `activeRunStatusIds` changes identity. That array derives from `backtestsQuery.data` (`680-694`), which gets a new reference each time a push message invalidates `['backtests']` and the refetched progress differs. So each progress push tears down every socket (`sockets` is the same `Map` as `wsRefs.current`, and it is `clear()`ed) and the effect immediately reopens one per active run: a connect/upgrade/auth cycle per message per run against the backend's Redis-backed push endpoint, with messages lost in the gaps. The incremental "close sockets for runs no longer active" block (`705-711`) is dead code as a consequence.
- Root cause: the effect cleanup and the incremental diff logic contradict each other; dependency is an unstable array instead of a stable key.
- Fix: depend on a stable string key (`activeRunStatusIds.join(',')`), do the diffing in the effect body only, and move the close-all loop into a separate `useEffect(() => () => {...}, [])`. Debounce the two invalidations.
- Verification: jsdom test with a counting fake `WebSocket`: render with one active run, emit three messages that change `progress_pct`, assert the constructor ran once.
- Effort: M | Blast radius: low | Depends on: —

### FRONT-P2-011 — The shared axios client has no request timeout
- Priority: P2 | Type: reliability | Area: api
- Evidence: frontend/src/api.ts:1786-1792
  ```ts
      this.client = create({
        baseURL: API_BASE_URL,
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json',
        },
      });
  ```
- Impact: axios defaults to `timeout: 0`. Only three calls set one (`api.ts:2109`, `2614`, `2909`). A stalled backend or proxy leaves start/stop/create requests pending indefinitely: `StrategyManager` stays in the optimistic `stopping`/`starting` state (`943-951`), action buttons stay disabled, and the operator cannot tell whether the command was delivered.
- Root cause: default never configured.
- Fix: set a client default (e.g. 15 s reads) with explicit longer budgets on known slow calls (backtest create, exports); surface `ECONNABORTED` through `classifyApiError` as "command outcome unknown — check runtime state" rather than a generic failure. Do this together with FRONT-P1-001 so a timeout does not trigger a blind re-send.
- Verification: unit test asserting the created instance has `defaults.timeout > 0`; manual: `tc`/DevTools throttling to "offline after connect" and confirm the UI leaves the pending state.
- Effort: S | Blast radius: med | Depends on: FRONT-P1-001

### FRONT-P2-012 — Logout is fire-and-forget: a failed server logout is invisible and the session silently resumes on reload
- Priority: P2 | Type: security | Area: api
- Evidence: frontend/src/api.ts:2250
  ```ts
      void axios.post(`${API_BASE_URL}/api/v1/auth/logout`, {}, { withCredentials: true });
  ```
- Impact: no `catch`, no timeout, no result. If the request fails (offline, 5xx, tab closed right after the click) the promise rejection is unhandled and the HttpOnly session cookie stays valid. The client-side cookie expiry loop that follows (`2252-2266`) cannot remove an HttpOnly cookie. On an HTTPS deployment `shouldAttemptCookieRefresh()` is unconditionally true (`api.ts:2080-2082`, `origin.ts:186-211`), so the next page load calls `/auth/refresh` and signs the "logged out" operator back into a trading console without credentials.
- Root cause: logout modelled as a synchronous local state change.
- Fix: make `logout()` async, await the POST with a short timeout and one retry, and if it still fails keep the user on a "Sign-out could not be confirmed — retry" state instead of reporting success; always `.catch` the promise.
- Verification: vitest: mock `axios.post` to reject; assert no unhandled rejection and that the store exposes a logout-failed flag/toast.
- Effort: M | Blast radius: med | Depends on: —

### FRONT-P2-013 — Any failure of `GET /users/me` destroys the server session
- Priority: P2 | Type: reliability | Area: store/auth
- Evidence: frontend/src/store/auth.ts:222-226
  ```ts
          } catch (error) {
            console.error('❌ auth.ts: getCurrentUser failed:', error);
            api.logout();
            set(buildLoggedOutState());
          }
  ```
- Impact: the catch does not look at the status. A transient 500/502, a network blip or a request abort during profile refresh (also invoked after `verify2FA`, `auth.ts:338`) posts `/auth/logout` and throws the operator out of the console mid-session — while live runtimes keep running unattended. This contradicts the interceptor's own policy of expiring the session only on 401/403 (`api.ts:1954`).
- Root cause: error handling that treats every failure as "unauthenticated".
- Fix: log out only when the error is a 401/403 (use `classifyApiError`); otherwise keep the existing user and surface a non-blocking warning.
- Verification: extend `src/store/auth.test.ts`: `getCurrentUser` rejecting with a 503 must not call `api.logout`; with a 401 it must.
- Effort: S | Blast radius: low | Depends on: —

### FRONT-P2-014 — No automated tests on the live-trading controls, the auth interceptor, or the WebSocket hook; contract guards cover four backtest endpoints by key presence only
- Priority: P2 | Type: test | Area: tests
- Evidence: frontend/src/api/contractGuards.ts:41-46
  ```ts
  export const contractSnapshots = {
    runBacktest: ['run_id'],
    listBacktests: ['backtests'],
    backtestStatus: ['run_id', 'status', 'progress_pct'],
    syncHealth: ['runs'],
  } as const;
  ```
- Impact: the 25 test files (132 tests) cover utilities, routing manifests and theme widgets. There is no test for `StrategyManager.tsx` (2.4k lines, start/stop live), `BotManager.tsx` (create/start/stop/delete), the 401→refresh→retry interceptor (`api.ts:1829-1991`), `useManagedWebSocket`, or `queryClient` defaults — the exact places where findings 001-004, 006, 007, 009 live. Contract guards validate only that a top-level key exists (no types), and none protects the trading surfaces (`/bots/:id/realtime-stats`, `/strategies/:id/runtime`, `/strategies/:id/start-readiness`), where a renamed field degrades silently to `0` (see FRONT-P2-007). `e2e/smoke.spec.ts` is the only browser test.
- Root cause: test investment followed the easy-to-test pure modules.
- Fix: add jsdom tests for the behaviours listed in the Verification lines of findings 001-010; extend `contractSnapshots` with typed guards for start-readiness, strategy runtime and realtime stats, and update them together with backend route changes.
- Verification: `cd frontend && npm run test` shows the new suites; `npx vitest run --coverage` (coverage provider would be a new dev dependency — confirm before adding).
- Effort: L | Blast radius: low | Depends on: —

### FRONT-P2-015 — Production CSP allows connections to any HTTPS/WS host and inline scripts
- Priority: P2 | Type: security | Area: docker/nginx.conf
- Evidence: docker/nginx.conf:9 (single line, excerpt)
  ```nginx
  default "default-src 'self'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; ... connect-src 'self' https: ws: wss:; ...
  ```
- Impact: `connect-src https: ws: wss:` means an injected script (or a compromised dependency) may exfiltrate to any origin, including plaintext `ws:`; `script-src 'unsafe-inline'` removes CSP as a second line of defence against XSS on a console that can start mainnet trading and accepts seed phrases. The comment explains the reasons (deployment-configurable API base, the pre-paint theme script in `index.html:25-50`), but both have narrower solutions. No `Strict-Transport-Security` header is set here (may be added by the ingress — see Needs verification).
- Root cause: CSP written once for all deployments instead of being templated from the known API origin.
- Fix: template `connect-src` from the deployment's API/WS origin (the image already takes `VITE_API_BASE_URL`; use an nginx `envsubst` template or the same ConfigMap that provides `executionlab-config.js`); move the theme bootstrap into a static file (`/theme-init.js`) or add its SHA-256 hash, then drop `'unsafe-inline'` from `script-src`.
- Verification: `docker build -f docker/Dockerfile.frontend -t front-csp . && docker run --rm -p 8080:80 front-csp` then `curl -sI localhost:8080 | grep -i content-security-policy`; load the app and confirm zero CSP violations in the console, Turnstile still renders on `/register`.
- Effort: M | Blast radius: med | Depends on: —

### FRONT-P2-016 — CI has no dependency-vulnerability gate for the frontend
- Priority: P2 | Type: security | Area: .github/workflows/bot-quality.yml
- Evidence: .github/workflows/bot-quality.yml:783-803 (complete step list of `frontend-quality`)
  ```yaml
            - name: Install dependencies
              run: npm ci
            - name: Lint
              run: npm run lint
            - name: Type check
              run: npm run typecheck
  ```
- Impact: the job runs lint, typecheck, `npm test`, build and Playwright, but nothing scans the npm tree (`grep -n "npm audit" .github/workflows/*.yml` → no matches), while the Python side already has `pip-audit` (`bot-quality.yml:338-364`). The dashboard ships axios, react-router and a charting library to a browser that handles session cookies and seed phrases; a vulnerable release would go unnoticed. During this audit `npm audit` could not be run either (registry returned 503, see Checks run), so the current state is unknown.
- Root cause: frontend gate was added later than the bot gates and the audit step was not mirrored.
- Fix: add `npm audit --omit=dev --audit-level=high` as a step (non-blocking first, as was done for pip-audit, then gating). Also add `npm run format:check`, which exists in `package.json` but is not enforced.
- Verification: push a branch and confirm the new step appears in the `frontend-quality` job summary; locally `cd frontend && npm audit --omit=dev --audit-level=high`.
- Effort: S | Blast radius: low | Depends on: —

---

## P3

### FRONT-P3-017 — Frontend image: Node major differs from CI, floating nginx tag, root user, no healthcheck, dead build arg
- Priority: P3 | Type: tech-debt | Area: docker/Dockerfile.frontend
- Evidence: docker/Dockerfile.frontend:6, 32, 44
  ```dockerfile
  FROM node:26-alpine AS builder
  ...
  ARG VITE_FORCE_MOCK_DATA=false
  ...
  FROM nginx:alpine
  ```
- Impact: CI builds and tests on Node 24 (`bot-quality.yml:769`), the shipped bundle is built on Node 26, so the artefact that reaches production is never the one CI validated; `package.json` has no `engines` field and there is no `.nvmrc`. `nginx:alpine` is an unpinned moving tag (non-reproducible, unreviewed upgrades). The runtime stage runs nginx as root on port 80 and declares no `HEALTHCHECK`. `VITE_FORCE_MOCK_DATA` is declared and exported but nothing in `src/` reads it (`grep -rn FORCE_MOCK_DATA frontend/src` → no matches).
- Root cause: image file evolved separately from the CI definition.
- Fix: pin both bases by version+digest and align Node with CI (`node:24-alpine@sha256:…`); add `"engines": {"node": ">=24 <25"}`; switch to `nginxinc/nginx-unprivileged` (listen 8080) or add `USER nginx` with adjusted paths; add `HEALTHCHECK CMD wget -qO- http://127.0.0.1/ || exit 1`; delete the unused arg. Coordinate the port change with the deploy manifests.
- Verification: `docker build -f docker/Dockerfile.frontend -t front-test .` then `docker run --rm front-test id -u` (non-zero) and `docker inspect --format '{{.Config.Healthcheck}}' front-test`.
- Effort: M | Blast radius: med | Depends on: —

### FRONT-P3-018 — API client carries methods for routes the backend does not expose, and two parallel implementations of the bot surface
- Priority: P3 | Type: tech-debt | Area: api
- Evidence: frontend/src/api/botApi.ts:143-144; frontend/src/api.ts:4326-4331
  ```ts
    async updateBotInstance(instanceId: string, updates: object): Promise<Entity> {
      const result = await this.request(`/api/v1/bots/${instanceId}`, 'put', updates);
  ```
  ```ts
        const response = await this.client.put<ApiResponse>(
          `/api/v1/bots/${instanceId}/config`,
  ```
- Impact: the backend registers no `PUT` under `/api/v1/bots` (`grep -rn '\.PUT(' backend --include=*.go | grep -i bot` → only `settings.PUT("/bot/:id")`; bot routes are in `backend/internal/routes/bot_instance_routes.go:40-67` and `bot_api_delegate_routes.go:3091-3349`). `useUpdateBotInstance` (`hooks.ts:535-541`) and `updateBotConfig` have no callers today, so nothing is broken yet, but they are exported API that will 404 the moment someone wires them up. In addition `src/api.ts:4086-4331` and `src/api/botApi.ts:105-200` each implement the same ~20 `/api/v1/bots/*` calls with different error and envelope handling (one throws `new Error(message)`, the other leaks the raw `AxiosError` — see FRONT-P1-003), and `botApi.ts` interpolates `instanceId` without `encodeURIComponent`.
- Root cause: incomplete consolidation (comment at `botApi.ts:1-5`).
- Fix: delete the two dead methods and the unused hook; keep one bot client (`botApi.ts`), remove the duplicate block from `api.ts`, encode path params.
- Verification: `cd frontend && npm run typecheck && npm run lint && npm run test`.
- Effort: M | Blast radius: low | Depends on: —

### FRONT-P3-019 — Dead components, a workflow file that never runs, and agent docs pointing at a file that does not exist
- Priority: P3 | Type: docs | Area: components, docs, .github
- Evidence: frontend/.github/workflows/ci.yml:23-25; frontend/AGENTS.md:19
  ```yaml
              uses: actions/setup-node@v4
              with:
                  node-version: "18"
  ```
  ```md
    - `src/api/enhancedClient.ts`: wrapper used by React Query hooks; many methods use `fetchWithAuth` + cookie-aware 401 retry.
  ```
- Impact: `src/components/TradeHistory.tsx` (198 lines), `PerformanceMetrics.tsx` (198) and `JobDetailsPanel.tsx` (267) have zero references outside their own file; `TradeHistory` would also render sub-cent perpetual prices as `$0.00` through `formatUsdFixed` if revived. `frontend/.github/workflows/ci.yml` is never loaded by GitHub (acknowledged in `bot-quality.yml:745-747`) yet describes a Node 18 pipeline that differs from the real gate — misleading for anyone reading the service directory. `frontend/AGENTS.md:19,59` (and the sibling agent-guidance file in the same directory, line 50) describe `src/api/enhancedClient.ts`, which does not exist; the service profile lists "Recharts 3" although `package.json` depends on `lightweight-charts` only. `@tanstack/react-query-devtools` sits in `dependencies` although it is DEV-gated (`QueryProvider.tsx:18`).
- Root cause: refactors (FE-015 consolidation, chart migration) not followed through in docs and leftovers.
- Fix: delete the three components and the nested workflow; correct the three docs; move devtools to `devDependencies`.
- Verification: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`; `python3 scripts/validate_docs_governance.py` from the repo root.
- Effort: S | Blast radius: low | Depends on: —

---

## Needs verification

- **Does `GET /api/v1/bots` ever return credentials inside `configuration`?** `BotManager.tsx:528-533` prints `JSON.stringify(bot.configuration, null, 2)` verbatim in the expanded card. The backend stores a `config` JSON next to the instance (`backend/internal/handlers/bot_instance_handler.go:436-447`) and forwards `credentials` to the bot service (`:452`). Check: create a runtime on a local stack, then `curl -s -b cookies.txt localhost:8888/api/v1/bots | jq '.data[].configuration'` and confirm no `mnemonic`/`secret_phrase`/`address` key is present. If any is, this becomes a P0 for the backend and the frontend must whitelist keys.
- **Are `POST /api/v1/strategies/:id/start`, `POST /api/v1/bots`, `POST /api/v1/backtests/run` idempotent on the backend?** Determines whether FRONT-P1-001 produces real duplicates or only redundant calls. Check: send the same request twice within one second against a local stack and compare resulting instance/run rows.
- **HSTS and TLS redirect for the dashboard host.** `docker/nginx.conf` listens on 80 and sets no `Strict-Transport-Security`. Check on the deployed host: `curl -sI https://app.executionlab.io | grep -i strict-transport` and `curl -sI http://app.executionlab.io | head -3`; also inspect the ingress manifests under `deploy/`.
- **npm dependency vulnerabilities.** `npm audit` could not reach the advisory endpoint during this audit (HTTP 503, registry maintenance). Re-run `cd frontend && npm audit --omit=dev` and `npm audit` when the registry is back.
- **Backtest push reconnect storm (FRONT-P2-010) frequency in practice.** Derived from code reading; confirm in a browser: open `/backtests` with one running backtest, DevTools → Network → WS, and count `…/push` connections opened per minute.
- **`frontend/.env.production` is not git-ignored** (`git check-ignore frontend/.env.production` prints nothing, while `frontend/.env` and `.env.local` are ignored). No such file is tracked today (`git ls-files frontend | grep -i '\.env'` → only `.env.example`). Decide whether to add `.env.*` + `!.env.example` to `frontend/.gitignore`.

---

## Checks run

All commands executed from `/home/chris/workspace/dydx-trading-bot/frontend` (`node_modules/` present; nothing was installed). `git status --porcelain` before and after every command was identical: the same three pre-existing untracked entries (a local tool-settings file, `docs/audit/`, `monorepo.zip`) and nothing else.

| Command | Result |
| :--- | :--- |
| `npm run lint` | exit 0 — `eslint src --ext .ts,.tsx --max-warnings 0`, no output (0 errors, 0 warnings) |
| `npm run typecheck` | exit 0 — `tsc --noEmit`, no output |
| `npm run test:contracts` | exit 0 — `Test Files  1 passed (1)`, `Tests  8 passed (8)`, duration 304ms |
| `npm run test 2>&1 \| tail -30` | exit 0 — `Test Files  25 passed (25)`, `Tests  132 passed (132)`, duration 1.32s |
| `npm audit --omit=dev 2>&1 \| tail -30` | **not completed**, exit 1 — `npm warn audit 503 Service Unavailable - POST https://registry.npmjs.org/-/npm/v1/security/advisories/bulk - We are currently performing maintenance.` / `npm error audit endpoint returned an error` (retried once ~6 minutes later, same 503). No vulnerability result is claimed. |
| `npm audit` (incl. dev) | **not completed**, same 503 |
| `npm run build` | not run (not required; `dist/` is git-ignored but already populated — left untouched) |
| `npm run test:e2e` | not run (would start a dev server and needs Playwright browsers) |
| `grep -rn "dangerouslySetInnerHTML\|innerHTML\|eval(\|new Function(" src index.html` | no matches |
| `grep -rn "8889" src vite.config.ts .env.example index.html` | no matches |
| `grep -rlE "localhost:8889\|BOT_API_TOKEN\|JWT_SECRET\|BEGIN (RSA\|PRIVATE)" dist` | no matches; no `*.map` files in `dist/assets` |
| `grep -rn "retry:" src` / `grep -rni idempotency src` | only query-level overrides / no matches (supports FRONT-P1-001) |
| `grep -rn "useLogout()" src` | no matches (supports FRONT-P1-004) |
| `grep -rn '\.PUT(' ../backend --include=*.go \| grep -i bot` | only `settings.PUT("/bot/:id", …)` (supports FRONT-P3-018) |

Tools not available: npm advisory endpoint (503). The IDE-backed inspection servers were unreachable and were not needed.
