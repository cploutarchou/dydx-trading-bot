# Findings — BOT (`bot/`, Python 3.12 FastAPI control plane + trading workers)

Audit date: 2026-09-19. Scope: `bot/src`, `bot/tests`, `bot/migrations`, `bot/internal`, `docker/Dockerfile.api`,
`docker/Dockerfile.worker`, `.github/workflows/bot-quality.yml`. Read-only investigation; no exchange connection,
no order placement, no migrations run. All paths are relative to the repository root. Every snippet below was read
from the working tree on branch `audit/2026-09-19-all`.

Summary: 5 × P0, 12 × P1, 6 × P2, 1 × P3, plus 4 items under "Needs verification".

---

## P0 — Critical

### BOT-P0-001 — Bot status endpoints return wallet mnemonics and Telegram tokens in plaintext
- Priority: P0 | Type: security | Area: api/bot-lifecycle
- Evidence: bot/src/infrastructure/domain/bot_api_models.py:178-186 (served by bot/src/api/v1/bot_lifecycle.py:396-420 and 431-456)
  ```python
        return BotInstanceStatus(
            instance_id=self.instance_id,
            status=self.status,
            ...
            config=self.config.model_dump(),
            trading_stats=self.trading_stats,
  ```
  `BotInstanceConfig.credentials` is `BotCredentials` (bot_api_models.py:88-93) with a plain `mnemonic: str`.
  Reproduced offline with a dummy value: `to_api_status().model_dump(mode="json")["config"]["credentials"]` →
  `{'chain_id': 'dydx-testnet-4', 'address': 'dydx1dummy', 'mnemonic': 'DUMMY-NOT-A-REAL-MNEMONIC'}`.
  No redaction exists in `api_response`, `responses.py` or the route handlers (grep for `redact|mask|mnemonic` is empty).
- Impact: `GET /api/v1/bots` and `GET /api/v1/bots/{instance_id}` hand the signing seed of every configured wallet
  (testnet and mainnet) plus Telegram bot tokens to any authenticated caller; combined with BOT-P0-002 any client
  that can reach :8889 can obtain them. Full loss of funds in the affected wallets. Secrets also transit the
  backend and any HTTP access log/proxy that records bodies.
- Root cause: the API view model reuses the internal config model and dumps it wholesale; credentials are sealed at
  rest but never excluded from the read path.
- Fix: build an explicit public view (`instance_name`, `address`, `chain_id`, `trading_params`, `telegram.enabled`)
  and never serialise `mnemonic`/`telegram.token`; make `mnemonic` a `SecretStr` so accidental dumps are masked;
  add a regression test asserting the mnemonic string is absent from both endpoints and from `quick-deploy`/create
  responses. Rotate any wallet whose mnemonic has been served through these endpoints.
- Verification: `cd bot && .venv/bin/python -m pytest tests/test_bot_lifecycle_routes.py -q` (new test
  `test_bot_status_never_exposes_mnemonic`); `grep -c mnemonic` on a captured `GET /api/v1/bots` body must be 0.
- Effort: M | Blast radius: high (API contract read by backend/frontend) | Depends on: —

### BOT-P0-002 — Open self-registration plus no ownership/admin check on live-trading lifecycle routes
- Priority: P0 | Type: security | Area: api/auth
- Evidence: bot/src/api/v1/auth/__init__.py:238-244 (route at :198 has no auth dependency, returns a token at :268)
  ```python
    user = User(
        username=username,
        email=email,
        hashed_password=PasswordUtils.hash_password(payload.password),
        full_name=full_name or None,
        is_active=True,
  ```
  and bot/src/api/v1/bot_lifecycle.py:526-530 (same pattern on create :296, delete :467, stop :604, restart :681, quick-deploy :811)
  ```python
  @router.post("/api/v1/bots/{instance_id}/start")
  async def start_bot_instance(
      instance_id: str,
      background_tasks: BackgroundTasks,
      current_user: User = Depends(get_current_active_user),
  ```
  `app.openapi()` lists `POST /auth/register` and `POST /api/v1/auth/register` without any security requirement;
  there is no registration feature flag (`grep -i "registration|ALLOW_REGISTER"` in `src` is empty).
- Impact: anyone who can reach the control plane can register, receive a JWT immediately, then create/start/stop/
  delete any instance (including mainnet) and read every instance's config (BOT-P0-001). `current_user` is unused
  for authorisation (`_ = current_user`), so there is also no per-user ownership (IDOR) between legitimate users.
- Root cause: lifecycle routes depend on `get_current_active_user` instead of an admin/service principal, and
  registration is public with `is_active=True`.
- Fix: gate registration behind an env flag that defaults to off (or admin-only), create users inactive by default,
  and require `get_admin_user` (service token or admin) on every mutating lifecycle route; keep read routes on a
  least-privilege role. Add tests: non-admin JWT → 403 on start/stop/delete/create.
- Verification: `cd bot && .venv/bin/python -m pytest tests/test_bot_lifecycle_routes.py tests/test_auth_middleware_service_token.py -q`
  (new tests `test_lifecycle_requires_admin`, `test_register_disabled_by_default`).
- Effort: M | Blast radius: high (backend delegation uses the service token, which stays superuser; user-JWT passthrough callers must be checked) | Depends on: —

### BOT-P0-003 — "Scoped" abort silently becomes a whole-subaccount flatten when the tracked set is empty
- Priority: P0 | Type: bug | Area: trading/abort
- Evidence: bot/src/trading/account_manager.py:702-705 (same falsy test for orders at :620-622)
  ```python
    cleanup_errors: List[str] = []
    market_scope: Optional[set[str]] = (
        {str(m).strip() for m in markets if str(m).strip()} if markets else None
    )
  ```
  caller bot/src/main_instance.py:686-688 always passes a list built from tracked positions:
  ```python
                await self._maybe_await(
                    abort_all_positions(self.client, markets=abort_markets)
                )
  ```
- Impact: an instance started with `abortAllPositions=true` and no tracked positions (fresh instance, cleared state,
  or DB+file read returning `[]`) passes `markets=[]`; `[]` is falsy so `market_scope=None` = "legacy whole-subaccount
  kill switch": every open order is cancelled and every position on the subaccount is market-closed, including
  other instances' hedged pairs on a shared subaccount (a documented supported topology). Real-money loss and
  orphaned legs for the other instances.
- Root cause: `None` (kill switch) and "empty scope" are conflated by a truthiness check.
- Fix: distinguish `markets is None` from an empty collection; an empty scope must be a no-op (log + return `[]`).
  Make the whole-subaccount mode an explicit keyword (`scope="subaccount"`). Test both.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "abort_all_positions"` (new test
  `test_abort_with_empty_scope_places_no_orders` using a fake client that fails on any `place_order`).
- Effort: S | Blast radius: low | Depends on: —

### BOT-P0-004 — `abort_all_positions` treats an unknown position state as "no positions" and wipes tracked state even when closes failed
- Priority: P0 | Type: bug | Area: trading/abort
- Evidence: bot/src/trading/account_manager.py:725-730
  ```python
    try:
        positions = await get_open_positions(client)
    except Exception as e:
        # If the indexer returns 404 or similar, assume no positions for this test account
        logger.warning("Could not fetch open positions: {}", e)
        positions = {}
  ```
  and bot/src/trading/account_manager.py:786 — `await clear_tracked_positions()` runs unconditionally, before the
  `if cleanup_errors: raise` at :788.
- Impact: `get_open_positions` already maps a genuine 404 to `{}` (:216-223); everything that reaches this `except`
  is a timeout, 5xx or open circuit breaker. The abort then closes nothing, adds nothing to `cleanup_errors`,
  clears the tracked-position store and returns success; the caller logs "Positions closed". Live positions remain
  open with no tracked record, so stop-loss/timeout/z-score exits never run for them again. The same wipe happens
  when individual close orders failed. Violates the service's own fail-closed rule ("unknown states must never be
  treated as no position").
- Root cause: legacy testnet convenience catch kept after `get_open_positions` gained its own 404 handling; state
  clearing is not conditional on verified flatness.
- Fix: let the fetch failure append to `cleanup_errors` (or retry with backoff) and re-raise; only remove tracked
  pairs whose markets are verified flat after the closes; keep the rest tracked with `pair_status=ABORT_FAILED`.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "abort_all_positions"` (new tests
  `test_abort_raises_when_positions_unreadable`, `test_abort_keeps_tracked_state_when_close_fails`).
- Effort: M | Blast radius: low | Depends on: BOT-P0-003

### BOT-P0-005 — Emergency close of leg 2 uses leg 1's fail-safe price (wrong market, wrong direction)
- Priority: P0 | Type: bug | Area: trading/entry-cleanup
- Evidence: bot/src/trading/bot_agent.py:562-567 (identical at :595-600)
  ```python
                await self._emergency_close_leg(
                    market=self.market_2,
                    side=self.quote_side,
                    size=self.quote_size,
                    price=self.accept_failsafe_base_price,
                )
  ```
  the price is derived from market 1 only — bot/src/trading/position_manager.py:1087-1089:
  ```python
                    failsafe_base_price = (
                        base_price * 0.05 if z_score < 0 else base_price * 1.7
                    )
  ```
- Impact: for z<0 the quote leg is a SELL, so its emergency close is a BUY on market 2 limited to `0.05 × price(market 1)`;
  for z>0 it is a SELL on market 2 with a floor of `1.7 × price(market 1)`. Unless the two markets' prices happen to
  differ by ~20×/1.7× in the right direction the order cannot fill; after three attempts `_emergency_close_leg`
  raises, leg 1 is closed, and the partially filled / unknown leg 2 stays open, unhedged and untracked (only the
  detection-only untracked-exposure alert sees it). The value is also formatted with market 1's tick size.
- Root cause: `BotAgent` carries a single fail-safe price; the leg-2 cleanup paths added later reuse it.
- Fix: compute and pass a market-2 fail-safe price (`quote_price × 1.7 / × 0.3` formatted with the quote tick size,
  mirroring `_failsafe_close_price`), and use it in both leg-2 cleanup sites. Add tests that assert the close order's
  market/price pair for both z-score signs.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "bot_agent"` (new tests
  `test_leg2_emergency_close_uses_quote_failsafe_price[z_neg|z_pos]`).
- Effort: S | Blast radius: low | Depends on: —

---

## P1 — High

### BOT-P1-001 — Placement result is never checked and the order-id fallback can bind to a different order
- Priority: P1 | Type: bug | Area: trading/orders
- Evidence: bot/src/trading/account_manager.py:428-433
  ```python
    # Print something if error returned
    if "code" in str(order):
        logger.error("Order returned error payload: {}", order)

    # Return result
    return (order, order_id)
  ```
  and the last-attempt heuristic at :482-518 (`allow_fallback=(attempt == max_attempts)`, :573) which matches on
  clob pair + side + reduceOnly + size and picks the highest `createdAtHeight`, with no lower bound on height.
- Impact: a node-rejected transaction is only logged (after ~9 s of indexer polling); on the final attempt the
  fallback can return the id of an older order of the same market/side/size (sizes repeat because every entry is
  `USD_PER_TRADE / price` floored to the step). That older order is FILLED, so `check_order_status_by_id` reports
  "live", leg 2 is placed against a leg 1 that does not exist, and the pair is tracked as LIVE with one naked leg.
  The real rejection reason is lost behind a generic `RuntimeError`.
- Root cause: string-sniffing instead of reading `tx_response.code`; heuristic identity match instead of the
  deterministic `clientId`.
- Fix: inspect the broadcast response and raise a typed `OrderRejectedError` immediately on non-zero code; drop the
  heuristic or restrict it to orders with `createdAtHeight >= current_block` captured before placement.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "place_market_order or resolve_order"` (new tests
  `test_rejected_tx_raises_without_polling`, `test_fallback_ignores_orders_older_than_placement_block`).
- Effort: M | Blast radius: low | Depends on: —

### BOT-P1-002 — SIGTERM/SIGINT handler raises an exception into whatever frame is running, including mid-entry
- Priority: P1 | Type: reliability | Area: worker/lifecycle
- Evidence: bot/src/main_instance.py:564-569
  ```python
        def signal_handler(signum: int, frame: Any) -> None:
            self._require_logger().info(
                f"Received signal {signum}, shutting down instance {self.instance_id}..."
            )
            self.running = False
            raise GracefulShutdownException("Shutdown signal received")
  ```
  `GracefulShutdownException` subclasses `Exception` (:871); operator stop sends `process.terminate()`
  (bot/src/bot_instance_manager.py:1447).
- Impact: an ordinary "stop" arriving between leg-1 fill and leg-2 placement either unwinds the event loop (leg 1
  left open, nothing tracked) or is caught by one of `open_trades`' broad `except Exception` blocks and
  misinterpreted as a placement error, triggering an emergency close that itself races the 30 s kill timer. The
  `while self.running` flag is never given the chance to end the cycle cleanly.
- Root cause: synchronous `signal.signal` handler raising instead of cooperative cancellation.
- Fix: use `loop.add_signal_handler` to set `self.running = False`/an `asyncio.Event`; finish the in-flight
  `open_trades`/`manage_trade_exits` call, then exit. Make the 5 s sleep interruptible by the event. Keep the
  manager's 30 s grace ≥ the worst-case entry duration or extend it while an entry is in flight.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "main_instance and signal"` (new test sending
  SIGTERM to a loop with a fake in-flight entry and asserting both legs complete and state is persisted).
- Effort: M | Blast radius: med | Depends on: —

### BOT-P1-003 — No write-ahead record of an in-flight entry; a crash between fills leaves exposure that is only alerted, never recovered
- Priority: P1 | Type: reliability | Area: trading/restart-recovery
- Evidence: bot/src/trading/position_manager.py:1282-1286 (the first and only persistence of an entry, after both legs are LIVE)
  ```python
                            # Save trade using atomic per-instance state update.
                            await append_tracked_position(bot_open_dict)
                            persisted_trade_id = persist_live_trade_opened(
                                bot_open_dict
                            )
  ```
  and the backstop is explicitly detection-only — position_manager.py:399-403:
  ```python
    order landed despite a "failed" entry (or a partial fill escaped cleanup),
    the position shows up here as exposure with no owner. Detection only —
    closing is deliberately left to the operator, because on a shared
  ```
- Impact: process kill/OOM/SIGKILL (or BOT-P1-002) after leg 1 fills leaves a naked position with no order id, no
  pair context and no stop-loss. After restart the only signal is a Telegram alert rate-limited by an in-memory
  cooldown; with `UNTRACKED_EXPOSURE_ALERTS_ENABLED=false` (recommended for shared subaccounts) there is none.
- Root cause: entry is not modelled as a persisted state machine (`INTENT → LEG1_SENT → LEG1_FILLED → LEG2_SENT → LIVE`).
- Fix: persist an intent row (pair, sides, sizes, client ids) before leg 1, update it after each step, and on start-up
  reconcile non-terminal intents against indexer orders/fills by `clientId`, closing or completing them.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "entry_intent or restart_recovery"` (new tests
  simulating a crash after leg 1 and asserting start-up reconciliation issues a reduce-only close).
- Effort: L | Blast radius: med | Depends on: BOT-P1-004

### BOT-P1-004 — Tracked-position store ignores DB write failures while reads prefer the DB (split-brain → lost positions)
- Priority: P1 | Type: data | Area: trading/state
- Evidence: bot/src/trading/bot_agents_state.py:119-121
  ```python
    except Exception as exc:
        logger.debug("DB save tracked positions failed ({}); falling back to file", exc)
        return False
  ```
  the return value is discarded by every caller (:210 `_db_save_positions(positions)`, :241, :243, :278), while
  `load_tracked_positions` returns the DB row whenever one exists (:185-187). A non-list DB payload is silently
  coerced to "no positions" (:75 `return data if isinstance(data, list) else []`).
- Impact: a DB blip during `append_tracked_position` writes the new pair to the JSON file only; once the DB is
  reachable again the stale DB row wins and the pair disappears from exit management (no stop-loss, no timeout).
  The reverse case resurrects closed pairs and double-persists their close. Failures are logged at DEBUG, so
  production logs show nothing.
- Root cause: dual-write without a source of truth, version, or error propagation.
- Fix: make one store authoritative per deployment; on DB write failure raise/alert and mark the instance degraded
  (block new entries); add an `updated_at`/version to both copies and reconcile newest-wins at load; treat a
  non-list payload as an error. Log at ERROR.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "bot_agents_state"` (new tests
  `test_append_survives_db_outage_then_recovery`, `test_non_list_payload_raises`).
- Effort: M | Blast radius: low | Depends on: —

### BOT-P1-005 — Fill pagination never advances: only the newest 100 fills per market are ever visible
- Priority: P1 | Type: bug | Area: trading/fills
- Evidence: bot/src/trading/account_manager.py:289-293
  ```python
            if page_cursor is None:
                page_cursor = (
                    str(fill.get("createdAt") or fill.get("created_at") or "") or None
                )
        cursor = page_cursor
  ```
  The cursor is taken from the FIRST (newest) fill of the page, so page 2 re-requests the same window; all rows are
  de-duplicated, `page_cursor` stays `None`, and page 3+ re-fetch page 1. Reproduced offline with an in-memory fake
  (250 fills, target order at positions 150-159): cursors used `[None, '2026-01-01T00:59:59.000Z', None, None, None]`,
  target fills found `0` (expected 10).
- Impact: `_verify_no_partial_fill` (bot_agent.py:238-243) returns "no fill" for an order whose fills are older than
  the newest 100 in that market, so a partially filled leg is treated as unfilled and left open; entry/exit VWAPs are
  truncated. The docstring claims this exact problem was fixed.
- Root cause: cursor assigned from the first element instead of the last (oldest) element of the page.
- Fix: set the cursor from the last fill of each page (prefer `created_before_or_at_height` with `createdAtHeight`),
  stop when a page yields no new ids, and route the call through `resilience.call_async` like the other indexer calls.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "get_order_fills"` (new test with a 250-fill fake
  asserting all 10 target fills are returned and cursors strictly decrease).
- Effort: S | Blast radius: low | Depends on: —

### BOT-P1-006 — Emergency-close retry loop is bypassed by any exception from `place_market_order`
- Priority: P1 | Type: bug | Area: trading/entry-cleanup
- Evidence: bot/src/trading/bot_agent.py:134-143
  ```python
        for attempt in range(1, retries + 1):
            close_order, order_id = await place_market_order(
                self.client,
                market=market,
                side=close_side,
                size=size,
  ```
  No `try` surrounds the call; the docstring (:126-128) claims a rejected reduce-only close "no-ops and the position
  check ends the retry loop".
- Impact: when leg 1 never filled, the reduce-only close is rejected by the node, never appears on the indexer, and
  `_resolve_recent_order_id` raises `RuntimeError` — so a benign "placement failed, nothing filled" becomes
  "Unexpected emergency closure error … position_open_after_cleanup=unknown". When leg 1 did fill, a single
  transient node/indexer error aborts all three attempts and the position check is never reached.
- Root cause: retry loop only covers the status-polling half of the attempt.
- Fix: wrap placement in `try/except`, always fall through to `is_open_positions` (fail-closed on error), and only
  raise after the final attempt with the position still (or possibly) open.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "emergency_close"` (new tests
  `test_emergency_close_returns_when_flat_after_rejected_close`, `test_emergency_close_retries_after_placement_error`).
- Effort: S | Blast radius: low | Depends on: BOT-P1-001

### BOT-P1-007 — Reduce-only close is re-sent after an unknown outcome; on a shared subaccount this closes other instances' exposure
- Priority: P1 | Type: bug | Area: trading/exits
- Evidence: bot/src/trading/position_manager.py:660-670
  ```python
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Reduce-only close attempt {}/{} failed for {}: {}",
  ```
  `place_market_order` raises both before broadcast and after a successful broadcast when the order id cannot be
  resolved (account_manager.py:601-604), and each retry uses a fresh random `client_id` (:391). The same applies to
  `_emergency_close_leg`, which also uses the subaccount-wide `is_open_positions` as its stop condition.
- Impact: up to three reduce-only closes of the tracked size can land. On a dedicated subaccount reduce-only caps the
  damage; on a shared subaccount (explicitly supported, see :607-611) the extra closes eat into another instance's
  position in the same market, un-hedging its pair.
- Root cause: no idempotency key across retries and no distinction between "not sent" and "sent, outcome unknown".
- Fix: generate the `client_id` once per logical close and reuse it across retries (the chain rejects duplicates
  within the good-til-block window); on an unknown outcome, look the order up by `clientId` before re-sending.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "reduce_only_close"` (new test: first attempt
  broadcasts then fails id resolution → exactly one `place_order` call observed).
- Effort: M | Blast radius: low | Depends on: BOT-P1-001

### BOT-P1-008 — Entries continue after a failed emergency cleanup
- Priority: P1 | Type: reliability | Area: trading/risk
- Evidence: bot/src/trading/position_manager.py:1205-1209 … 1230
  ```python
                        try:
                            bot_open_dict = await bot_agent.open_trades()
                        except Exception as exc:
                            record_rejection("entry_execution_failed")
                            _record_entry_failure(pair_key, exc)
  ```
  followed by `continue` at :1230. `open_trades` raises only when an emergency close failed
  (`position_open_after_cleanup` true/unknown).
- Impact: with a known naked, untracked leg on the book the scanner moves on to the next pair in the same cycle and
  keeps adding exposure; the only brake is a per-pair cooldown. Portfolio guards count markets, not hedge integrity.
- Root cause: cleanup failure is handled like an ordinary entry rejection.
- Fix: raise a typed `UnhedgedExposureError`; on it, set an instance-level "entries halted" latch (persisted),
  alert critical, and require operator acknowledgement or a successful reconciliation before `placeTrades` resumes.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "open_positions and halt"` (new test asserting no
  further `BotAgent` is constructed after a cleanup failure).
- Effort: M | Blast radius: low | Depends on: —

### BOT-P1-009 — Realised P&L is never recorded for live trades (always 0.0)
- Priority: P1 | Type: data | Area: persistence/trades
- Evidence: bot/src/trading/trade_persistence.py:177-183
  ```python
        uow.trades.update_trade_exit(
            trade_id,
            exit_price1=_float_or_zero(exit_price1),
            exit_price2=_float_or_zero(exit_price2),
            exit_size1=_float_or_zero(exit_size1),
            exit_size2=_float_or_zero(exit_size2),
  ```
  and bot/src/infrastructure/persistence/repository.py:603-604 writes the defaults:
  `trade.realized_pnl = realized_pnl` / `trade.realized_pnl_pct = realized_pnl_pct` (both default `0.0`);
  `profit_loss` is never set on this path. `grep -rn realized_pnl src/trading` shows no other writer.
- Impact: every closed live trade is stored with zero P&L; `get_trade_statistics` (repository.py:551-580) therefore
  counts all of them as losing (`profit_loss <= 0`), reports `total_profit_loss = 0` and a 0 % win rate. There is no
  trustworthy financial record to reconcile against the exchange. The alternative `close_trade` (:536-537)
  hard-codes leg 1 long / leg 2 short and would be wrong for half the trades if used.
- Root cause: exit persistence was reduced to price/size bookkeeping; P&L computation was left to a parameter no
  caller supplies.
- Fix: compute side-aware realised P&L (and fees from fills) in one place using `Decimal`, pass it to
  `update_trade_exit`, set `profit_loss` aliases consistently, and make repeated closes idempotent (do not overwrite
  `closed_at`). Backfill is a separate, human-run script.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "persist_live_trade_closed or trade_statistics"`
  (new tests for BUY/SELL and SELL/BUY pairs with known fills).
- Effort: M | Blast radius: med | Depends on: BOT-P2-001

### BOT-P1-010 — Auth-bypass environment check fails open: an unset environment resolves to "development"
- Priority: P1 | Type: security | Area: api/auth
- Evidence: bot/src/middleware/auth_middleware.py:63-68
  ```python
  def current_environment_name() -> str:
      for key in ("APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV"):
          value = os.getenv(key, "").strip()
          if value:
              return value
      return "development"
  ```
  `docker/Dockerfile.api` sets none of these variables (the worker image sets `APP_ENV=prod`, the API image does not).
- Impact: `API_BYPASS_AUTH=true` leaking into an API container without an explicit environment variable grants every
  unauthenticated request a superuser principal (`_BypassUser`, :224-233) over live-trading controls. First-match
  precedence also lets `APP_CONFIG_ENV=development` override `ENVIRONMENT=production`.
- Root cause: permissive default and "first non-empty wins" resolution.
- Fix: default to `production` when nothing is set; if ANY of the four variables names a forbidden environment, deny;
  refuse to start (already implemented in `validate_auth_bypass_configuration`) under the same stricter rule; set
  `APP_ENV=prod` in `Dockerfile.api`.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "auth_bypass"` (new tests
  `test_bypass_denied_when_environment_unset`, `test_any_production_marker_wins`).
- Effort: S | Blast radius: low (local dev must set `APP_ENV=dev`) | Depends on: —

### BOT-P1-011 — Open advisory on the transaction-signing SDK; dependency and code security scans do not gate CI
- Priority: P1 | Type: security | Area: dependencies/ci
- Evidence: bot/requirements.txt:31 `dydx-v4-client==1.1.6`; pip-audit output (this session):
  ```
  dydx-v4-client 1.1.6   GHSA-4f84-67cv-qrv3 1.1.5
  ecdsa          0.19.2  PYSEC-2026-1325
  ```
  and .github/workflows/bot-quality.yml:361 (same for bandit at :307)
  ```yaml
              continue-on-error: true # phase 1: reporting-only, does not gate
  ```
  `requirements.txt` has 0 `--hash` entries and 31 non-`==` specifiers (e.g. `pyyaml`, `pandas>=2.3.0`).
- Impact: the package that receives the wallet mnemonic has a published advisory whose listed fix version is LOWER
  than the pinned one, and `ecdsa` (signing) has an advisory with no fix; neither can fail a build, and unhashed,
  range-pinned requirements mean the Docker image installs whatever PyPI serves at build time.
- Root cause: security jobs left in "phase 1 reporting-only"; image installs from `requirements.txt` rather than the
  hashed lockfile (`uv.lock`).
- Fix: triage GHSA-4f84-67cv-qrv3 (see Needs verification NV-1) and pin a known-good release; make pip-audit
  blocking with an explicit, dated ignore list; build images from `uv.lock`/hash-pinned export.
- Verification: `cd bot && .venv/bin/pip-audit -r requirements.txt --progress-spinner off` exits 0 (or only
  documented ignores); CI job fails on a seeded vulnerable pin.
- Effort: M | Blast radius: med | Depends on: —

### BOT-P1-012 — Wallet mnemonics are stored in plaintext by default when no encryption key is provisioned
- Priority: P1 | Type: security | Area: persistence/credentials
- Evidence: bot/src/shared/credentials_cipher.py:166-174
  ```python
        logger.warning(
            "Credential encryption key is not provisioned; bot credentials will "
            "be stored in plain text. Set %s to enable encryption, or "
            "%s=true to refuse plaintext writes.",
  ```
  followed by `return b""` (plaintext passthrough). No compose file or Dockerfile in the repository sets
  `BOT_CREDENTIALS_ENCRYPTION_KEY*` or `BOT_CREDENTIALS_ENCRYPTION_REQUIRED` (grep over `*.yml`/`*.yaml` is empty).
- Impact: in the shipped stack `bot_instances.config` holds signing seeds in clear text; any DB read access, backup
  or SQL dump leaks them.
- Root cause: fail-open default chosen for backward compatibility.
- Fix: require encryption whenever the instance network is mainnet or the environment is not dev/test; provision the
  key in the compose/k8s manifests.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "credentials_cipher"` (new test: mainnet config +
  no key → `CredentialEncryptionError`).
- Effort: S | Blast radius: med (deployments without a key must provision one) | Depends on: —

---

## P2 — Medium

### BOT-P2-001 — Binary floats used for order size, price, P&L and money columns
- Priority: P2 | Type: data | Area: trading/arithmetic
- Evidence: bot/src/trading/position_manager.py:1105-1106
  ```python
                    base_quantity = 1 / base_price * USD_PER_TRADE
                    quote_quantity = 1 / quote_price * USD_PER_TRADE
  ```
  also `size=float(size), price=float(price)` (account_manager.py:407-408), float VWAP (bot_agent.py:342-350,
  position_manager.py:483-490), `1e-9`/`1e-12` tolerances (:306, :317), `Float` ORM columns for every price/size/P&L
  (bot/internal/domain/models.py:143-163). Only `format_size_down` uses `Decimal`.
- Impact: non-deterministic rounding at step/tick boundaries, tolerance hacks in flat-confirmation logic, and
  inexact stored financial records; violates the repository standard ("Decimal for money").
- Root cause: legacy float pipeline; SDK accepts floats.
- Fix: carry `Decimal` from indexer strings through sizing, VWAP and P&L; convert to float only at the SDK boundary;
  migrate columns to `Numeric(38, 18)` with an expand → backfill → contract migration.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "sizing or vwap or pnl"`; `.venv/bin/python -m mypy src`.
- Effort: L | Blast radius: high (schema) | Depends on: —

### BOT-P2-002 — No cross-worker coordination on entries; the lock service is an unimplemented stub
- Priority: P2 | Type: reliability | Area: concurrency
- Evidence: bot/src/infrastructure/cache_lock.py:61-66
  ```python
    def acquire_lock(self, key: str, token: str, *, ttl_seconds: int) -> bool:
        del key, token, ttl_seconds
        raise RuntimeError(
            "Valkey cache/lock service is not wired in Phase 1. "
  ```
  It is exported (`src/infrastructure/__init__.py:3`) but has no caller. The entry guard is check-then-act on an
  indexer snapshot (position_manager.py:940-948) with seconds of latency before the order lands.
- Impact: two instances on a shared subaccount can both see market X as "not open" and both enter it; the later
  scoped-close/attribution logic assumes that never happens. The stub is production-reachable dead code.
- Root cause: staged migration stopped at the interface.
- Fix: either implement a short-TTL per-(subaccount, market) lease (Valkey `SET NX PX` with token release) around
  entry, or document and enforce "one instance per subaccount" at instance creation; delete the stub until needed.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "entry_lock"` (new test with two concurrent
  `open_positions` calls against one fake subaccount → one entry).
- Effort: M | Blast radius: med | Depends on: —

### BOT-P2-003 — Stop-loss/timeout evaluation is gated on historical order look-ups
- Priority: P2 | Type: reliability | Area: trading/exits
- Evidence: bot/src/trading/position_manager.py:1456-1460
  ```python
            # Get order info m1 per exchange
            order_m1 = await get_order(client, position["order_id_m1"])
            order_market_m1 = order_m1["ticker"]
            order_size_m1 = order_m1["size"]
            order_side_m1 = order_m1["side"]
  ```
- Impact: any failure of `GET /v4/orders/{id}` for the entry orders (indexer error, record no longer served) raises
  into the per-position handler (:1961-1983): the position is kept, a CRITICAL Telegram is sent every 5-second cycle,
  and no exit rule — including stop-loss — is evaluated for that pair until the look-up works again. State is also
  persisted only once at the end of the pass (:1987), so a crash mid-pass replays closes as `external_close`.
- Root cause: identity re-validation against the entry order is performed before, and as a precondition of, risk exits.
- Fix: evaluate exits from tracked state + live exchange positions; make the order look-up advisory (warn, rate-limit
  the alert); persist state after each closed pair.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "manage_trade_exits"` (new test: `get_order`
  raises, stop-loss threshold breached → close orders still placed).
- Effort: M | Blast radius: low | Depends on: —

### BOT-P2-004 — API image runs as root, base image unpinned, no HEALTHCHECK; trading workers inherit the full API environment
- Priority: P2 | Type: security | Area: container
- Evidence: docker/Dockerfile.api:1 and :26-28 (no `USER` instruction anywhere in the file)
  ```dockerfile
  FROM python:3.12-slim
  ...
  EXPOSE 8889

  CMD ["python", "-m", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8889"]
  ```
  and bot/src/bot_instance_manager.py:1251 `bot_env = os.environ.copy()` for every spawned worker.
- Impact: the control plane — which holds decrypted mnemonics in memory and spawns the trading workers — runs as
  uid 0; workers receive `BOT_API_TOKEN`, DB, MinIO and ClickHouse credentials they do not need. `python:3.12-slim`
  floats, so rebuilds are not reproducible. (`Dockerfile.worker` already creates and uses an `app` user.)
- Root cause: API Dockerfile not updated when the worker image was hardened.
- Fix: mirror the worker's `app` user, pin the base by digest, add a `HEALTHCHECK` on `/health`, set `APP_ENV=prod`,
  and build the worker env from an allow-list.
- Verification: `docker build -f docker/Dockerfile.api -t bot-api:audit . && docker run --rm bot-api:audit id -u`
  prints a non-zero uid.
- Effort: S | Blast radius: med (volume ownership for `bot_states`) | Depends on: —

### BOT-P2-005 — Internal exception text is returned to API clients
- Priority: P2 | Type: security | Area: api/errors
- Evidence: bot/src/api/v1/bot_lifecycle.py:517-523 (pattern repeated in every handler of the module)
  ```python
    except Exception as exc:
        logger.error(f"Error deleting bot instance {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
  ```
  `get_current_user` likewise returns `detail=str(e)` for any auth failure (auth_middleware.py:244-248).
- Impact: SQL/driver errors, file paths and config validation messages (which can echo submitted credentials) reach
  the caller; f-string logging also bypasses structured fields and drops the traceback.
- Root cause: broad catch used as the error boundary.
- Fix: return a generic message with a correlation id; log with `logger.exception` and structured fields.
- Verification: `cd bot && .venv/bin/python -m pytest tests/test_bot_lifecycle_routes.py -q` (new test: manager raises
  `RuntimeError("secret-detail")` → body does not contain it).
- Effort: S | Blast radius: low | Depends on: —

### BOT-P2-006 — JWT signing key silently falls back to a per-process random value
- Priority: P2 | Type: reliability | Area: api/auth
- Evidence: bot/src/api/auth_utils.py:32
  ```python
  SECRET_KEY = str(config("SECRET_KEY", default=secrets.token_urlsafe(32)))
  ```
- Impact: with `SECRET_KEY` unset every restart invalidates all sessions and, with more than one uvicorn worker or
  replica, tokens issued by one process are rejected by the others (intermittent 401s) — with no log line.
- Root cause: convenience default instead of configuration validation.
- Fix: require `SECRET_KEY` outside dev/test (fail start-up), warn loudly in dev.
- Verification: `cd bot && .venv/bin/python -m pytest tests/ -q -k "secret_key"` (new test on the start-up validator).
- Effort: S | Blast radius: low | Depends on: —

---

## P3 — Low

### BOT-P3-001 — Naive datetimes remain in the DB pool monitor and DataFrame registry
- Priority: P3 | Type: tech-debt | Area: infrastructure
- Evidence: bot/src/infrastructure/database.py:282 (also :202, :224, :275, :310, :377; `datetime.now()` in
  bot/src/shared/dataframe_utils.py:54, :160, :229)
  ```python
                {"timestamp": datetime.utcnow(), "timeout": timeout_seconds}
  ```
- Impact: `DeprecationWarning` on Python 3.12 (seen in the test run), local-time arithmetic in the registry; values
  are in-memory only, so no stored data is affected. `bot_agents_state.py:90` also strips tzinfo before writing
  `tracked_positions.updated_at` (column is naive `DateTime`).
- Root cause: leftovers from before the UTC-aware convention.
- Fix: use `datetime.now(timezone.utc)` (there is already `src/shared/time_utils.py`).
- Verification: `cd bot && .venv/bin/python -W error::DeprecationWarning -m pytest tests/test_database_unit.py -q`.
- Effort: S | Blast radius: low | Depends on: —

---

## Needs verification

- NV-1 (relates to BOT-P1-011): what exactly GHSA-4f84-67cv-qrv3 covers for `dydx-v4-client` and whether the installed
  1.1.6 artefact is affected. pip-audit lists the fix version as 1.1.5, i.e. lower than the pin. A shallow read-only
  scan of the installed package found only dYdX/localhost URLs and no `exec`/`eval`/`subprocess`/`requests.post`, but
  that is not proof. Check: read the advisory (`https://github.com/advisories/GHSA-4f84-67cv-qrv3`), then
  `cd bot && .venv/bin/pip download dydx-v4-client==1.1.6 --no-deps -d /tmp/w && sha256sum /tmp/w/*` and compare with
  the hash in `uv.lock` and with a build of the upstream tag. Treat as P0 until cleared because this package handles
  the mnemonic.
- NV-2 (relates to BOT-P2-003): whether the dYdX indexer keeps serving `GET /v4/orders/{id}` for filled short-term
  orders for the full `POSITION_TIMEOUT_HOURS`. Check on testnet: place a minimal order, record the id, query it
  after 24 h/72 h. If records expire, BOT-P2-003 becomes P1 (exits permanently blocked for old pairs).
- NV-3 (relates to BOT-P0-001/002): network reachability of :8889 in the real deployment. `docker-compose.stack.yml:327-328`
  publishes `8889:8889` on all host interfaces with `BOT_API_TOKEN` defaulting to `local-dev-token` (:325); the k8s
  manifests under `deploy/` were not reviewed here. Check: `grep -rn "8889" deploy/` and confirm a NetworkPolicy /
  ClusterIP-only Service restricts ingress to the backend.
- NV-4 (relates to BOT-P1-004): behaviour of `_db_load_positions` when the driver returns the JSON column as `str`
  (e.g. a `JSON` column accessed through raw `text()` on a non-psycopg2 driver): the code would return `[]`
  (bot_agents_state.py:75) and the instance would believe it has no positions. Check: integration test against the
  production driver asserting `isinstance(result[0], list)`.

---

## Checks run

All commands executed from `bot/` with the existing virtualenv on 2026-09-19; nothing was installed.

| Command | Result |
| :--- | :--- |
| `.venv/bin/python -m mypy src` | `Success: no issues found in 98 source files` (exit 0) |
| `.venv/bin/python -m flake8 src tests --select=E9,F63,F7,F82` | no output (exit 0) |
| `.venv/bin/python -m bandit -r src -c pyproject.toml -ll` | exit 1 — 3 Medium, 0 High (44 Low not shown at `-ll`): B104 bind-all `src/api/server.py:1802`, B104 `src/api/start_api.py:30`, B608 `src/bot_instance_manager.py:363` (table/column names come from a constant tuple, value is bound → not injectable). 32 178 LOC scanned, 0 `#nosec`. |
| `.venv/bin/pip-audit -r requirements.txt --progress-spinner off` | exit 1 — `Found 3 known vulnerabilities in 2 packages`: `dydx-v4-client 1.1.6 GHSA-4f84-67cv-qrv3 (fix: 1.1.5)`, `ecdsa 0.19.2 PYSEC-2026-1325` (listed twice, no fix version) |
| `.venv/bin/python -m pytest tests/ --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py -q -x --timeout=600` | not runnable: `error: unrecognized arguments: --timeout=600` — `pytest-timeout` is not installed in the venv |
| same command without `--timeout` (plus `-p no:cacheprovider`) | `1424 passed, 13 skipped, 54 warnings in 33.60s` (exit 0). Warnings: `datetime.utcnow()` deprecations (database.py:282, :377; tests/test_database_unit.py:157) and two sync tests carrying `@pytest.mark.asyncio` (tests/test_nats_consumer_service.py:561, :753) |
| `app.openapi()` route enumeration (import only, server not started) | 105 operations; 6 without a security requirement: `POST /auth/{token,login,register}` and `POST /api/v1/auth/{token,login,register}`. `/health`, `/ready`, `/metrics`, `/api/v1/capabilities`, `/api/v1/markets/perpetuals` carry no auth dependency |
| Offline reproduction of `to_api_status()` with a dummy mnemonic | credentials, including the mnemonic, present in the payload (BOT-P0-001) |
| Offline reproduction of `get_order_fills` with a 250-fill in-memory fake | 0 of 10 target fills returned; cursors `[None, '…00:59:59.000Z', None, None, None]` (BOT-P1-005) |

Tools not available: `pytest-timeout`. Not run: isort/black checks, coverage gate, `make test-multiworker`,
`make test-integration` (need external services), any Docker build.
