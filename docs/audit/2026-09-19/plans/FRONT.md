# Plan — FRONT (`frontend/`) — 2026-09-19

Evidence, impact and root cause for every ID: `../findings/FRONT.md`.
Verification baseline (2026-09-19): `npm run lint` clean; `npm run typecheck` clean; `npm run test` 25 files / 132 tests passed; `npm run test:contracts` 8 passed.

## P1

### FRONT-P1-001 — Global `mutations.retry: 1` re-sends non-idempotent trading POSTs
- Root cause: the query client retries every mutation once; create/start/backtest POSTs carry no idempotency key.
- Fix: `mutations.retry: 0` globally (a mutation that is safe to retry opts in locally); test the default.
- Verification: new vitest on the query client defaults; `npm run lint && npm run typecheck && npm test`.
- Effort: S | Blast radius: low | Status: done (36723306) — mutations.retry 0 globally; 1 test

### FRONT-P1-003 — Wallet mnemonic reaches the browser console through raw error logging
- Root cause: `console.error('Failed to create bot:', err)` logs the Axios error, whose `config.data` holds the request body (mnemonic).
- Fix: log a sanitised summary (status, code, operator message) instead of the raw error in the create path; add `autoComplete="off"` and `spellCheck={false}` to the seed input.
- Verification: vitest asserting the logged value does not contain the request body; lint, typecheck, tests.
- Effort: S | Blast radius: low | Status: done (36723306) — create path logs a sanitised summary; seed input autocomplete/spellcheck off; 2 tests

### FRONT-P1-004 — Logout never clears the React Query cache
- Fix: clear the query cache on logout in the code path the sidebar actually uses (the existing `useLogout` hook is unused); test.
- Verification: vitest: after logout the cache is empty; lint, typecheck, tests.
- Effort: S | Blast radius: low | Status: done (36723306) — every logged-out transition clears user-scoped queries (public queries kept; a full clear blanked the app shell and failed e2e); 2 tests

### FRONT-P1-005 — `formatUsdFixed` strips the sign and renders missing values as `$0.00`
- Root cause: `Math.abs(value)` and a `$0.00` fallback; used for Free Collateral in the go-live dialog.
- Fix: keep the sign (`-$12.50`) and render missing/non-finite values as `—`; update the existing format tests; check each call site renders sensibly.
- Verification: `npm test` (format tests updated and extended); lint, typecheck.
- Effort: S | Blast radius: med (shared formatter) | Status: done (36723306) — new formatUsdBalance (signed, missing renders as em dash) used in the go-live dialog; shared formatters left unchanged; 1 test

### Proposal-only / deferred
- FRONT-P1-002 stopping a live runtime has no confirmation and is bound to a bare `s` key — proposal (operator workflow change on a live-trading control; proposed: confirmation dialog naming the target, remove the bare-key binding or require a modifier).
- FRONT-P1-006 manual runtime form defaults to mainnet; `chain_id` / `is_testnet` can contradict — proposal (default network is a business decision; proposed: default to testnet, derive `is_testnet` from `chain_id`, validate numerics).

## P2 / P3 — deferred to the next run
- FRONT-P2-007 `$0` P&L when stats are absent — deferred (S; follows FRONT-P1-005's missing-value convention).
- FRONT-P2-008 failed system-status call replaced by a fabricated healthy payload — deferred (S/M; needs an error-state design).
- FRONT-P2-009 WebSocket + interval leak while CONNECTING — deferred (M).
- FRONT-P2-010 backtest sockets reopened on every progress update — deferred (M).
- FRONT-P2-011 no default axios timeout — deferred (needs per-endpoint budgets `[CONFIRM]`; long-running backtest calls).
- FRONT-P2-012 logout POST is fire-and-forget — deferred (S).
- FRONT-P2-013 any `/users/me` failure forces logout — deferred (S/M).
- FRONT-P2-014 no tests on live-trading controls, auth interceptor, WS hook — deferred (L).
- FRONT-P2-015 CSP allows broad `connect-src` and `'unsafe-inline'` — deferred (needs the deployed origin list `[CONFIRM]`).
- FRONT-P2-016 no npm vulnerability step in CI — merged into REPO-P2-002.
- FRONT-P3-017 Dockerfile: Node 26 vs CI 24, floating nginx tag, root — merged into REPO-P2-001, INFRA-P2-001, INFRA-P2-006.
- FRONT-P3-018 dead client methods / duplicated bot API surface — deferred.
- FRONT-P3-019 dead components and a never-executed nested workflow — deferred.

## Queue 2 — unblocked by the owner's decisions (2026-09-19)

### FRONT-P1-006 — Manual runtime form network default
- Decision: default to testnet; derive `is_testnet` from `chain_id`; validate numeric inputs; mainnet is an explicit choice.
- Verification: vitest on the payload builder (no contradictory pair possible, NaN rejected); lint, typecheck, unit and Playwright suites.
- Effort: S | Blast radius: low | Status: done (f0dbc203) — form defaults to testnet; network and is_testnet derived from chain_id; NaN/zero/negative numerics rejected; 10 tests

### FRONT-P1-002 — Confirm runtime stop
- Decision: confirmation dialog naming the runtime; remove the bare `s` shortcut.
- Verification: vitest/RTL: stop is not sent before confirm; key press does nothing; lint, typecheck, unit and Playwright suites.
- Effort: S | Blast radius: low | Status: done (f0dbc203) — stop asks for confirmation naming the runtime; the s shortcut and its hint are removed. No component test (StrategyManager has no test harness, FRONT-P2-014); verified by lint, typecheck and the e2e smoke suite
