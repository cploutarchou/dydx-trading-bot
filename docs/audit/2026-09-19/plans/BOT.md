# Plan — BOT (`bot/`) — 2026-09-19

Evidence, impact and root cause for every ID: `../findings/BOT.md`. Order: P0 → P3, dependencies first, smallest blast radius first.
Verification baseline (run before any change, 2026-09-19): `pytest` 1424 passed / 13 skipped; `mypy src` clean; `flake8` clean.
All fixes are verified with the hermetic suite (fakes only). Nothing in this plan connects to an exchange.

## P0

### BOT-P0-003 — Scoped abort with an empty tracked set flattens the whole subaccount
- Root cause: `abort_all_positions` and `cancel_all_orders` build the scope with `... if markets else None`; an empty list is falsy, so "this instance tracks nothing" is treated as "no scope" (legacy whole-subaccount kill switch).
- Fix: distinguish `None` (whole subaccount) from an empty collection (scope to nothing → no cancels, no closes) in both functions; test both.
- Verification: new tests in `bot/tests` for `markets=[]` (no order placed, no cancel) and `markets=None` (legacy behaviour kept); full bot suite.
- Effort: S | Blast radius: low | Status: done (pending commit) — empty scope is a no-op in abort and cancel-all; 4 tests

### BOT-P0-004 — Abort treats a failed position fetch as "no positions" and clears tracked state even when closes failed
- Root cause: `except Exception: positions = {}` with a warning; `clear_tracked_positions()` runs unconditionally before the error is raised.
- Fix: a failed position fetch is recorded in `cleanup_errors` (CRITICAL log); tracked state is cleared only when the abort had no failures, so the next start still knows about possible exposure. Raise as today.
- Verification: new tests: fetch failure → raises, tracked state kept; close failure → raises, tracked state kept; clean abort → state cleared. Full bot suite.
- Effort: S | Blast radius: low | Depends on: BOT-P0-003 (same function) | Status: done (pending commit) — failed position fetch fails closed; tracked state kept when exposure is unknown; 2 tests

### BOT-P0-005 — Leg-2 emergency close is priced with leg-1's fail-safe price
- Root cause: both leg-2 emergency paths pass `price=self.accept_failsafe_base_price` (market 1) for an order on market 2.
- Fix: price the leg-2 close from market 2's own fail-safe price for the closing side; test that the close order for `market_2` carries a market-2 price on both paths (status-check failure, partial fill).
- Verification: new unit tests on `bot_agent` with fakes; full bot suite.
- Effort: S | Blast radius: low | Status: done (pending commit) — leg-2 close uses a market-2 fail-safe price (new required BotAgent argument); 2 tests extended

### BOT-P0-001 — Bot list/detail endpoints return wallet mnemonics and Telegram tokens in plaintext
- Root cause: `to_api_status()` returns `config=self.config.model_dump()` with no redaction.
- Fix: redact secret-bearing fields in the API status view (mnemonic, API/Telegram tokens → presence flag only); confirm no consumer in `backend/` or `frontend/` reads those fields from the response before changing; regenerate nothing by hand.
- Verification: new test asserting no secret value appears in the serialized status; consumer grep recorded in LOG.md; full bot suite, backend tests.
- Effort: S | Blast radius: med (response shape) | Status: done (pending commit) — status view drops mnemonic and Telegram token, adds presence flags; 1 test

### BOT-P0-002 — Open self-registration issues an active user and JWT; lifecycle routes need only any active user
- Status: proposal (needs human decision: is self-registration on the bot API intended at all, and which role may create/start/stop/delete instances?). Proposed change: disable the register routes unless an explicit env flag is set, and require an admin/operator role plus ownership on lifecycle routes. See OPEN-QUESTIONS.md.

## P1

### BOT-P1-005 — Fill pagination cursor never advances (only the newest 100 fills are visible)
- Fix: advance the cursor per page until exhaustion or the lower time bound; test with a fake indexer returning 3 pages.
- Verification: new unit test (previously 0/10 fills found offline); full bot suite.
- Effort: S | Blast radius: low | Status: done (pending commit) — cursor advances from the oldest fill of each page with a no-progress guard; 4 tests, existing pagination test unchanged

### BOT-P1-010 — Auth-bypass environment check fails open when the environment variable is unset
- Fix: treat an unset/unknown environment as production for the bypass decision (fail closed); local development keeps working by setting the variable explicitly, as the compose files already do `[verify in task]`.
- Verification: new tests for unset / `production` / `development`; full bot suite.
- Effort: S | Blast radius: med | Status: done (pending commit) — bypass needs an explicit dev/test label and no conflicting label; unset environment denies; 6 tests

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
