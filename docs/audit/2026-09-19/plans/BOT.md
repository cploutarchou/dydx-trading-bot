# Plan — BOT (`bot/`) — 2026-09-19

Evidence, impact and root cause for every ID: `../findings/BOT.md`. Order: P0 → P3, dependencies first, smallest blast radius first.
Verification baseline (run before any change, 2026-09-19): `pytest` 1424 passed / 13 skipped; `mypy src` clean; `flake8` clean.
All fixes are verified with the hermetic suite (fakes only). Nothing in this plan connects to an exchange.

## P0

### BOT-P0-003 — Scoped abort with an empty tracked set flattens the whole subaccount
- Root cause: `abort_all_positions` and `cancel_all_orders` build the scope with `... if markets else None`; an empty list is falsy, so "this instance tracks nothing" is treated as "no scope" (legacy whole-subaccount kill switch).
- Fix: distinguish `None` (whole subaccount) from an empty collection (scope to nothing → no cancels, no closes) in both functions; test both.
- Verification: new tests in `bot/tests` for `markets=[]` (no order placed, no cancel) and `markets=None` (legacy behaviour kept); full bot suite.
- Effort: S | Blast radius: low | Status: done (36723306) — empty scope is a no-op in abort and cancel-all; 4 tests

### BOT-P0-004 — Abort treats a failed position fetch as "no positions" and clears tracked state even when closes failed
- Root cause: `except Exception: positions = {}` with a warning; `clear_tracked_positions()` runs unconditionally before the error is raised.
- Fix: a failed position fetch is recorded in `cleanup_errors` (CRITICAL log); tracked state is cleared only when the abort had no failures, so the next start still knows about possible exposure. Raise as today.
- Verification: new tests: fetch failure → raises, tracked state kept; close failure → raises, tracked state kept; clean abort → state cleared. Full bot suite.
- Effort: S | Blast radius: low | Depends on: BOT-P0-003 (same function) | Status: done (36723306) — failed position fetch fails closed; tracked state kept when exposure is unknown; 2 tests

### BOT-P0-005 — Leg-2 emergency close is priced with leg-1's fail-safe price
- Root cause: both leg-2 emergency paths pass `price=self.accept_failsafe_base_price` (market 1) for an order on market 2.
- Fix: price the leg-2 close from market 2's own fail-safe price for the closing side; test that the close order for `market_2` carries a market-2 price on both paths (status-check failure, partial fill).
- Verification: new unit tests on `bot_agent` with fakes; full bot suite.
- Effort: S | Blast radius: low | Status: done (36723306) — leg-2 close uses a market-2 fail-safe price (new required BotAgent argument); 2 tests extended

### BOT-P0-001 — Bot list/detail endpoints return wallet mnemonics and Telegram tokens in plaintext
- Root cause: `to_api_status()` returns `config=self.config.model_dump()` with no redaction.
- Fix: redact secret-bearing fields in the API status view (mnemonic, API/Telegram tokens → presence flag only); confirm no consumer in `backend/` or `frontend/` reads those fields from the response before changing; regenerate nothing by hand.
- Verification: new test asserting no secret value appears in the serialized status; consumer grep recorded in LOG.md; full bot suite, backend tests.
- Effort: S | Blast radius: med (response shape) | Status: done (36723306) — status view drops mnemonic and Telegram token, adds presence flags; 1 test

### BOT-P0-002 — Open self-registration issues an active user and JWT; lifecycle routes need only any active user
- Status: done (f0dbc203) — register returns 403 unless BOT_API_ALLOW_SELF_REGISTRATION=true; six mutating lifecycle routes need an admin principal; 17 tests

## P1

### BOT-P1-005 — Fill pagination cursor never advances (only the newest 100 fills are visible)
- Fix: advance the cursor per page until exhaustion or the lower time bound; test with a fake indexer returning 3 pages.
- Verification: new unit test (previously 0/10 fills found offline); full bot suite.
- Effort: S | Blast radius: low | Status: done (36723306) — cursor advances from the oldest fill of each page with a no-progress guard; 4 tests, existing pagination test unchanged

### BOT-P1-010 — Auth-bypass environment check fails open when the environment variable is unset
- Fix: treat an unset/unknown environment as production for the bypass decision (fail closed); local development keeps working by setting the variable explicitly, as the compose files already do `[verify in task]`.
- Verification: new tests for unset / `production` / `development`; full bot suite.
- Effort: S | Blast radius: med | Status: done (36723306) — bypass needs an explicit dev/test label and no conflicting label; unset environment denies; 6 tests

### Proposal-only (order path or design-level; exact proposals in the finding records)
- BOT-P1-001 tx rejection detection and order-id binding — proposal (changes order-result interpretation on the live path).
- BOT-P1-002 SIGTERM handler raises into an arbitrary frame — proposal (shutdown redesign: flag + cooperative stop).
- BOT-P1-003 no write-ahead entry intent — proposal (new persistence + recovery flow).
- BOT-P1-004 tracked-position store ignores DB write failures — proposal (consistency model decision).
- BOT-P1-006 emergency-close retry loop bypassed by exceptions — proposal (live close path).
- BOT-P1-007 reduce-only close re-sent with a new client id after unknown outcome — proposal (live close path; needs idempotent client id policy).
- BOT-P1-008 entries continue after failed emergency cleanup — proposal (halt latch semantics and operator reset flow).
- BOT-P1-009 realised P&L never recorded for live trades — proposal (needs the P&L definition: fees, funding, rounding).
- BOT-P1-012 mnemonics stored in plaintext when no encryption key is set — proposal (fail-closed start without a key changes every existing deployment).

### Deferred
- BOT-P1-011 advisory on the signing SDK and `ecdsa`; audit steps are `continue-on-error` — deferred (needs verification NV-1 of the advisory's scope and an SDK upgrade decision; dependency changes need a dedicated change per repo policy).

## P2 / P3 — deferred to the next run
- BOT-P2-001 float for sizes/prices/P&L — deferred (L; schema + arithmetic migration, needs a design).
- BOT-P2-002 no cross-worker entry lock — deferred (merged with the single-writer lock proposal in INFRA-P0-001).
- BOT-P2-003 stop-loss evaluation gated on historical order look-ups — deferred (order path; M).
- BOT-P2-004 `Dockerfile.api` runs as root, unpinned base — merged into INFRA-P2-001 / INFRA-P2-006.
- BOT-P2-005 internal exception text returned to clients — deferred (M; many sites).
- BOT-P2-006 JWT secret falls back to a per-process random value — deferred (fail-closed start changes deployments; pair with BOT-P1-012).
- BOT-P3-001 naive datetimes in pool monitor / DataFrame registry — deferred (S; low value this run).

## Queue 2 — unblocked by the owner's decisions (2026-09-19)

### BOT-P0-002 — Disable self-registration; admin/operator on lifecycle routes
- Decision: registration off unless an explicit environment flag enables it; create/start/stop/delete need an admin or operator role. The backend's service token keeps working (it maps to a superuser principal today; verify in task).
- Verification: route tests: register → 403/404 by default; lifecycle as a plain user → 403; service token → allowed; full bot suite; backend delegated-route tests.
- Effort: M | Blast radius: med | Status: todo

### BOT-P1-011 — Signing SDK advisory
- Decision: verify the advisory's affected range and the installed package integrity first, then upgrade `dydx-v4-client` in a dedicated change; make `pip-audit` blocking with a dated ignore for `ecdsa`.
- Verification: `pip-audit -r requirements.txt` clean apart from the documented ignore; full bot suite; no order-signing test regressions.
- Effort: M | Blast radius: high (signing path) | Status: todo

### BOT-P1-009 — Realised P&L for live trades
- Decision: net of fees, from fills. Per leg (exit VWAP − entry VWAP) × size × side, minus fees on all four fills; funding stored separately; `Decimal`, 6 dp at storage.
- Verification: unit tests with fixed fills (long/short legs, partial fills, fees); stats count winners and losers correctly; full bot suite.
- Effort: M | Blast radius: med | Status: todo

### Order-path items moved from proposal to the queue at the owner's request (2026-09-19)

Each is its own change with tests on fakes only; nothing connects to an exchange. Full evidence and the detailed fix: `../findings/BOT.md`. Order follows the dependencies.

### BOT-P1-001 — Detect transaction rejection from the broadcast response; bind order ids deterministically
- Fix: inspect the broadcast response and raise a typed `OrderRejectedError` on a non-zero code instead of matching `"code" in str(order)`; resolve the order by its client id, never by "latest order" heuristics.
- Verification: `pytest tests/ -q -k "place_market_order or resolve_order"` with new tests (rejected tx raises; an older order is never bound); full bot suite.
- Effort: M | Blast radius: low | Status: done (b357131e) — non-zero broadcast code raises OrderRejectedError before any polling; the order-id fallback only binds orders placed at or after this placement (createdAtHeight or goodTilBlock); 10 tests

### BOT-P1-006 — Emergency-close retry loop must survive placement exceptions
- Fix: wrap placement in the retry loop, always fall through to the open-position check (fail closed on error), and only report success when the position is verified flat.
- Verification: `pytest tests/ -q -k "emergency_close"` with a test where the first placement raises and the second fills; full bot suite.
- Effort: S | Blast radius: low | Depends on: BOT-P1-001 | Status: done (b357131e) — a failed attempt no longer ends the close loop; a flat reading counts only after a close order was placed; 4 tests, existing escalation test unchanged

### BOT-P1-007 — One client id per logical reduce-only close
- Fix: generate the `client_id` once per logical close and reuse it across retries, so an unknown-outcome first attempt cannot be doubled by the retry on a shared subaccount.
- Verification: `pytest tests/ -q -k "reduce_only_close"` with a test asserting the same client id across attempts; full bot suite.
- Effort: M | Blast radius: low | Depends on: BOT-P1-001 | Status: deferred (needs the dYdX v4 semantics for re-submitting a short-term order with the same client id after an unknown outcome, verified on testnet; guessing a chain contract on the close path is not acceptable. See OPEN-QUESTIONS.md)

### BOT-P1-008 — Halt new entries after a failed emergency cleanup
- Fix: raise a typed `UnhedgedExposureError`; on it set a persisted, instance-level "entries halted" latch that blocks new entries until an operator clears it; alert through the messenger. Exits and risk controls keep running.
- Verification: `pytest tests/ -q -k "open_positions and halt"` (no entry is attempted while latched; latch survives restart; explicit reset clears it); full bot suite.
- Effort: M | Blast radius: low | Status: done (b357131e) — UnhedgedExposureError from every emergency-closure failure; persisted per-instance entry halt latch honoured by the scan, set mid-cycle, cleared only by the operator CLI; 5 tests

### BOT-P1-004 — Tracked-position store must not ignore write failures
- Fix: one authoritative store per deployment; a failed DB write raises/alerts and marks the instance degraded instead of a DEBUG log, so reads can never prefer a store that silently missed writes.
- Verification: `pytest tests/ -q -k "bot_agents_state"` with a failing-writer fake; full bot suite. Document restart/reconciliation behaviour (state-safety rule).
- Effort: M | Blast radius: low | Status: todo

### BOT-P1-002 — Cooperative shutdown instead of raising from the signal handler
- Fix: `loop.add_signal_handler` sets a stop flag / `asyncio.Event`; the in-flight entry or exit completes (or runs its cleanup) before the loop ends; bounded by a timeout below the deployment's grace period.
- Verification: `pytest tests/ -q -k "main_instance and signal"` with a test that signals mid-entry and asserts both legs end consistent; full bot suite.
- Effort: M | Blast radius: med | Status: todo

### BOT-P1-003 — Write-ahead entry intent and restart recovery
- Fix: persist an intent (pair, sides, sizes, client ids) before leg 1, update it after each step, and on start-up reconcile any unfinished intent against the exchange: complete the hedge or flatten, fail closed when the state is unknown. Needs a migration in `bot/migrations` (expand-only).
- Verification: `pytest tests/ -q -k "entry_intent or restart_recovery"` (crash between legs → recovery flattens or completes; unknown → halts via BOT-P1-008); migration applies and rolls back on a scratch database only; full bot suite.
- Effort: L | Blast radius: med | Depends on: BOT-P1-004, BOT-P1-008 | Status: todo

### BOT-P1-012 — Refuse to store mnemonics in plaintext outside dev/test
- Fix: require the credentials encryption key whenever the instance network is mainnet or the environment is not an explicit dev/test label; start-up and instance creation fail with a clear error otherwise. Existing plaintext records are not rewritten silently: a documented one-off re-seal command is provided.
- Verification: `pytest tests/ -q -k "credentials_cipher"` (mainnet without key → refused; dev without key → allowed with a warning; with key → sealed); full bot suite. Deployment note: the GitOps repository must provision the key before this ships.
- Effort: S | Blast radius: med | Status: done (b357131e) — plaintext credential storage only in an explicit dev/test environment; shared fail-closed environment helper reused by the auth bypass gate; 13 tests
