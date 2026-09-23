# Bot Risk Control Matrix

| Config Field             | Current Code Path                                                                                                                                                           | Enforced On Entry | Enforced On Exit | Test Exists                            | Status   | Notes                                                                                                                                |
|--------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|------------------|----------------------------------------|----------|--------------------------------------------------------------------------------------------------------------------------------------|
| `max_positions`          | `src/trading/position_manager.py::open_positions`                                                                                                                           | Yes               | No               | Yes                                    | ENFORCED | Entry is rejected when tracked live positions already meet `MAX_POSITIONS`.                                                          |
| `usd_min_collateral`     | `src/trading/position_manager.py::open_positions`, `src/api/server.py::runtime_preflight`                                                                                   | Yes               | No               | Existing coverage + preflight checks   | ENFORCED | Entry blocks when free collateral is below configured minimum.                                                                       |
| `usd_per_trade`          | `src/trading/position_manager.py::open_positions`, `src/api/server.py::runtime_preflight`                                                                                   | Yes               | No               | Existing coverage + preflight checks   | ENFORCED | Order size is derived from `USD_PER_TRADE`; preflight blocks if collateral is below per-trade size.                                  |
| `stop_loss_pct`          | `src/trading/position_manager.py::_resolve_exit_reason`, `manage_trade_exits`                                                                                               | No                | Yes              | Yes                                    | ENFORCED | Live exits now trigger on realized PnL threshold evaluation from tracked entry prices and current market prices.                     |
| `take_profit_pct`        | `src/trading/position_manager.py::_resolve_exit_reason`, `manage_trade_exits`                                                                                               | No                | Yes              | Yes                                    | ENFORCED | Live exits now trigger when configured profit threshold is reached.                                                                  |
| `position_timeout_hours` | `src/trading/position_manager.py::_resolve_exit_reason`, `manage_trade_exits`                                                                                               | No                | Yes              | Yes                                    | ENFORCED | Live exits now trigger when tracked position age reaches the configured timeout.                                                     |
| `close_at_zscore_cross`  | `src/trading/position_manager.py::_resolve_exit_reason`, `manage_trade_exits`                                                                                               | No                | Yes              | Existing coverage + updated exit tests | ENFORCED | Existing z-score reversion exit remains active and now waits for exchange-flat confirmation before closure.                          |
| `max_drawdown_pct`       | `src/trading/drawdown_guard.py::check_entry_drawdown`, `src/trading/position_manager.py::open_positions`, `src/api/server.py::runtime_preflight` | Yes | No | Yes | ENFORCED | Halts new entries (durable entry halt, kind `max_drawdown`) once the subaccount's equity is this far below its peak. Open pairs are not closed. See below. |
| `trailing_stop_pct`      | `src/trading/position_manager.py::_resolve_exit_reason`, `manage_trade_exits`, `src/infrastructure/use_cases/service_backtest.py::_simulate_pair` | No | Yes | Yes | ENFORCED | Closes a pair that gave back this much of its best unrealized P&L, once that best level reached the same distance. Same rule in the backtest. See below. |
| `capital_allocation_usd` | `src/shared/live_risk_controls.py`, `src/api/server.py::runtime_preflight`, `src/api/server.py::create_bot_instance`, `src/bot_instance_manager.py`, `src/main_instance.py` | Rejected          | Rejected         | Yes                                    | REJECTED | Rejected because the live runtime does not enforce cumulative allocation limits at order-entry time. Operators must set this to `0`. |

### Strategy drawdown limit and trailing stop (2026-09-23)

Both used to be REJECTED like `capital_allocation_usd`. They are enforced now and accepted by
`src/shared/live_risk_controls.py`; both are off at `0`, which is also the default for a new strategy in the
backend and in the bot's own strategy API and model (both write `backtest_strategies`), and the backtest request
fallback when a strategy record lacks the field.

| Control | Measured on | Fires when | Action | Survives restart | Fails |
|---|---|---|---|---|---|
| `trailing_stop_pct` | The pair's unrealized P&L as % of its entry notional (same number as the stop loss) | Best P&L since entry has reached the distance, and P&L is now that distance below it | Closes the pair (exit reason `trailing_stop`, stop-loss accept band) | Best level stored on the tracked position (`peak_unrealized_pnl_pct`) | A cycle whose P&L cannot be computed neither moves the best level nor judges the trail |
| `max_drawdown_pct` | Equity of the subaccount the runtime trades on, from the highest equity since the measurement began | Equity is the limit or more below that peak | Sets the durable entry halt (kind `max_drawdown`); open pairs keep their exits | Peak in `drawdown_peaks` (migration `0008_drawdown_peaks`), per runtime and subaccount | Unreadable equity or peak: no entries that cycle (fail closed) |

- The trailing stop never exits below break-even and never tightens the stop loss: until the best level reaches
  the distance, only the stop loss governs the downside. Ladder order: stop loss, take profit, trailing stop,
  timeout, z-score reversion. The backtest applies the same rule at bar closes, so it does not see a peak inside a
  bar.
- The drawdown measurement begins when the runtime first observes the subaccount. Clearing a drawdown halt deletes
  the subaccount's stored peaks before the halt is cleared (a failed reset leaves the halt), so the next cycle
  measures from the current equity. A peak marked as tripped with no active halt sets the halt again. Preflight
  states the limit in dollars and warns when the recorded peak is already at or past it.
- Known limits: a withdrawal counts as drawdown, a deposit raises the peak, and anything else on the subaccount moves
  its equity. The backtest reports drawdown as a result metric but does not stop entries at the limit, because its
  equity base is the strategy's starting balance plus realized P&L, not the subaccount's equity. This control is
  separate from the deployment-wide `BOT_PORTFOLIO_MAX_DRAWDOWN_PCT` below.

Coverage: `tests/test_trailing_stop.py`, `tests/test_drawdown_guard.py`, `tests/test_backtest_live_parity.py`,
`tests/test_live_risk_controls.py`, `tests/test_entry_halt_routes.py`, `tests/test_api_server_unit.py`.

### How an operator resolves a REJECTED control (2026-09-21)

Only `capital_allocation_usd` is still rejected; `max_drawdown_pct` and `trailing_stop_pct` are enforced since
2026-09-23 (above), so readiness no longer reports them and the UI no longer offers to turn them off. The notes
below describe how a rejection is reported and resolved.

- `POST /api/v1/runtime/preflight` still answers 422 `UNSUPPORTED_RISK_CONTROL`; its `data` now also lists
  `unsupported_fields: [{field, value, message}]` (`describe_unsupported_live_risk_controls`). The list
  describes the rejection and never relaxes it.
- The backend's `GET /api/v1/strategies/:id/start-readiness` reports that refusal as `ready: false` with one
  blocker per control and an `unenforced_risk_controls` list. Starting stays refused.
- `max_drawdown_pct` and `trailing_stop_pct` are operator-set. They are turned off only by an explicit,
  acknowledged action (`POST /api/v1/strategies/:id/unenforced-risk-controls/disable`, or saving the strategy
  with the value `0`), which stores `0` on the strategy and writes a
  `strategy.risk_controls.disable_unenforced` audit-log entry with the previous values. There is no bypass
  flag: a non-zero value never reaches the instance config or the worker environment.
- `capital_allocation_usd` was never operator-set on a strategy. The backend used to derive it from the
  backtest's starting capital (`initial_amount`), which made every strategy unstartable. The backend now sends
  `0` to the live runtime and shows the backtest capital as information only, with a readiness warning that it
  is not a live limit.
- The backtest engine does not apply `capital_allocation_usd` or `max_drawdown_pct`. It applies
  `trailing_stop_pct` with the live rule.

### Execution data integrity (2026-09-21)

Added after the first live strategy runtimes on staging raised a critical "leg may be open" alert for a
position that never existed: the public dYdX testnet indexer was 19 hours behind the chain, so the runtime
could not find the order it had just placed.

| Control | Code path | Behaviour | Test Exists |
|---|---|---|---|
| Indexer freshness (`BOT_INDEXER_MAX_LAG_SECONDS`, default `120`, `0` = off) | `src/trading/indexer_freshness.py`, `position_manager.open_positions`, `server.runtime_preflight` | Entries are skipped for the cycle while the indexer's latest block is older than the limit, or its height cannot be read (fail closed). Not a latch; exits unaffected; preflight reports it as a blocker; operator alert rate-limited by `BOT_INDEXER_STALE_ALERT_SECONDS` (default `1800`). | Yes |
| Chain-verified "nothing to close" | `account_manager.verify_flat_on_chain`, `bot_agent._emergency_close_leg` | Only when all close attempts were refused by the node with code 2001, the chain has passed the entry order's last valid block, and the validator node's subaccount state shows no position in that market. The indexer is not consulted. Any other outcome escalates as before (entry latch + critical alert). | Yes |

Coverage: `tests/test_indexer_freshness_and_chain_state.py`, `tests/test_bot_agent_emergency_cleanup.py`.

The entry latch is durable and scoped to the subaccount (`entry_halts` table, migration `0007_entry_halts`, plus a
per-instance file as the write-first fallback); it is shown and cleared, with an acknowledgement and an audit
record, through `/api/v1/bots/{instance_id}/entry-halt`. Two runtimes on one subaccount would share netted
positions and the order history each of them searches, so start and preflight refuse a second active runtime on
the same `(network, address, subaccount)`. Coverage: `tests/test_entry_halt_durable.py`,
`tests/test_entry_halt_routes.py`, `tests/test_bot_instance_manager.py`.

Known limits: the one-runtime-per-subaccount check covers the runtimes of one bot-api process; a standalone run
or a second bot-api deployment on the same wallet is not seen.

## Account-Level (Portfolio) Controls — Phase A (2026-08-15)

Cross-instance controls evaluate the SHARED dYdX subaccount (equity, free collateral, open perpetual
markets) before any new entry, closing the "N instances each within per-instance limits while the account
is over-exposed" gap. The subaccount already reflects every instance's fills, so it is the authoritative
aggregate view with no cross-process state. Engine: `src/trading/portfolio_risk.py`; wired into
`position_manager.open_positions` after the per-instance `max_positions` check; every denial is
rejection-counted, warning-logged, and persisted as a `trade_entry_rejected_portfolio_risk` audit event.

**Default ON since the Phase B flip (2026-08-17)** — set `BOT_PORTFOLIO_RISK_ENABLED=false` to
deactivate. Any limit <= 0 disables that check. Fail-closed for malformed account data
(`portfolio_data_unavailable`); transport errors propagate exactly like the existing free-collateral
guards.

| Env Var                                    | Default | Check                                                                                                                                   | Denial reason                     | Test Exists |
|--------------------------------------------|---------|-----------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------|-------------|
| `BOT_PORTFOLIO_RISK_ENABLED`               | `true`  | Master switch (off → guard short-circuits without exchange reads); default ON since Phase B (2026-08-17)                                  | —                                 | Yes         |
| `BOT_PORTFOLIO_MAX_OPEN_MARKETS`           | `20`    | Aggregate open perpetual markets on the subaccount (pair entries occupy two) — at-limit denies new entries                                | `portfolio_max_open_markets`      | Yes         |
| `BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT` | `60.0`  | `(equity − freeCollateral) / equity` — at-limit denies new entries                                                                       | `portfolio_margin_utilization`    | Yes         |
| `BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD`    | `0.0`   | Projected free collateral after the incremental notional (≈ 2 × `usd_per_trade`, 1x-leverage approximation) must stay above the floor    | `portfolio_free_collateral_floor` | Yes         |

Coverage: `tests/test_portfolio_risk.py` (13 cases — pure-core decisions incl. boundary equality and
fail-closed paths, wrapper short-circuit/deny/propagation, and the `open_positions` wiring proving a
denial rejects with an audit event and zero orders).

**Operator visibility**: `GET /api/v1/monitoring/portfolio-risk` (auth required) reports the guard's live
configuration plus the last 24h of denial audit events across all instances (instance, reasons, equity,
free collateral, open markets) — the burn-in surface for Phase A.

**Slice 3 — account-wide drawdown (2026-08-15)**: `BOT_PORTFOLIO_MAX_DRAWDOWN_PCT` (default `0` = off) denies
new entries when equity has fallen at/after the cap from the ratcheted all-time peak. The peak is stored per
wallet address in Redis/Valkey (`bot:portfolio:peak_equity:<address>`, key = `max(stored, observed)` so
concurrent workers race benignly; reset with `redis-cli DEL`). Redis is auxiliary coordination here, NOT a
trading dependency: if Redis is unavailable the drawdown check skips itself (peak=None) while the
exchange-read controls (markets / utilization / collateral floor) still fail closed. NOTE: this is the
deployment-wide control. The per-strategy `max_drawdown_pct` is enforced separately by
`src/trading/drawdown_guard.py` (durable peak, latches the entry halt, fails closed).

**Slice 4 — multi-account aggregation (2026-08-16)**: deployment-wide caps across EVERY distinct wallet address
configured in `bot_instances` (per network). Engine: `src/trading/portfolio_accounts.py` (enumeration +
public exposure reads) and `evaluate_aggregate_entry` in `src/trading/portfolio_risk.py`. Enumeration decrypts
each `bot_instances.config` best-effort (undecryptable rows are skipped, never fatal), dedupes on
`(network, address)`, and caches the address list per process for `BOT_PORTFOLIO_ACCOUNTS_CACHE_TTL_SECONDS`
(default 60 s). dYdX v4 indexer account reads are PUBLIC per address, so foreign subaccounts are read without
their signing credentials; reads run concurrently through the `dydx_indexer` breaker. A 404 is a definitive
"no subaccount" answer and counts as complete zero exposure; malformed payloads are excluded from the
equity sums (counted as `incomplete_accounts`); any other read error propagates — the entry decision fails
exactly like the worker's own account reads. Aggregate checks run only when a limit is > 0 (both default 0 =
off) AND the master switch is on; with both off the guard performs zero enumeration and zero extra exchange
reads. There is deliberately no aggregate free-collateral floor (margin is isolated per subaccount on dYdX v4
— the floor stays a per-account check). All statuses are included in enumeration because a stopped bot's
positions still exist on-chain.

| Env Var                                            | Default | Check                                                                                                        | Denial reason                          | Test Exists |
|----------------------------------------------------|---------|--------------------------------------------------------------------------------------------------------------|----------------------------------------|-------------|
| `BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS`         | `0`     | Total open perpetual markets across all same-network subaccounts — at-limit denies new entries               | `portfolio_aggregate_max_open_markets` | Yes         |
| `BOT_PORTFOLIO_AGGREGATE_MAX_MARGIN_UTILIZATION_PCT` | `0.0` | `Σ(equity − freeCollateral) / Σ(equity)` over complete same-network accounts — at-limit denies new entries   | `portfolio_aggregate_margin_utilization` | Yes        |
| `BOT_PORTFOLIO_AGGREGATE_MAX_ACCOUNTS`             | `25`    | Cap on distinct subaccounts considered (deterministic truncation + warning when exceeded)                     | —                                      | Yes         |
| `BOT_PORTFOLIO_ACCOUNTS_CACHE_TTL_SECONDS`         | `60`    | Per-process TTL for the decrypted address list                                                               | —                                      | Yes         |
| `BOT_PORTFOLIO_ACCOUNTS_HTTP_TIMEOUT_SECONDS`      | `5.0`   | Per-request timeout for the monitoring route's direct public indexer reads                                   | —                                      | Yes         |

**Operator visibility (extended)**: `GET /api/v1/monitoring/portfolio-risk` now also reports
`accounts` (per-address exposure: equity, free collateral, open markets, `complete` flag, per-account
`error`) and `aggregate_by_network` (per-network totals incl. `margin_utilization_pct` and
`incomplete_accounts`) via best-effort direct public indexer reads — one unreachable account degrades to an
incomplete entry instead of failing the dashboard. Denial audit events carry an `aggregate` detail block
(totals + incomplete count). Coverage: `tests/test_portfolio_accounts.py` (22 cases), aggregate cases in
`tests/test_portfolio_risk.py`, and the route shape in `tests/test_monitoring_routes.py`.

## Phase B — Burn-in & Default Flip (2026-08-17)

The master switch was flipped **default ON** after a recorded live burn-in, following the same
evidence-then-flip protocol as the broadcast-bus Phase 2 flip. Operators keep full control:
`BOT_PORTFOLIO_RISK_ENABLED=false` restores the pre-guard behavior; every individual limit stays
independently disable-able at `0`/empty.

**Upgrade note**: with the default ON, the two default-active limits now apply out of the box —
20 open perpetual markets and 60% margin utilization per subaccount. A deployment already running
hotter than those must either raise the limits (`BOT_PORTFOLIO_MAX_OPEN_MARKETS` /
`BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT`) or opt out; entries above the limits are denied with the
standard `portfolio_*` reason codes and show up in `/api/v1/monitoring/portfolio-risk`.

**Burn-in harness**: `make portfolio-burn-in` (engine: `scripts/portfolio_risk_burn_in.py`, guidance in
the `portfolio-risk-burn-in` skill) runs repeated live evaluations of the guard's pure core against every
`bot_instances` subaccount via the same public indexer reads the monitoring endpoint uses (no signing
credentials). It FAILS on cycle errors and `portfolio_data_unavailable` observations — the
false-denial classes — while genuine limit denials (including `portfolio_non_positive_equity` on a
genuinely empty account) are reported as correct behavior. `--json-out` writes the full per-cycle log as
evidence. Re-run it before changing any default limit.

**Flip evidence (2026-08-17, live infra + public testnet indexer)**: 20 cycles × 3 s, PASS (exit 0) —
a real funded testnet subaccount (equity ≈ 845k USDC, 5 open perpetual markets, $214,400 notional parsed
from live position payloads, zero unparsed) was ALLOWED on all 20 cycles with zero read errors, zero
data-unavailable observations, and zero decision changes; a never-traded address exercised the
404 → complete-zero-exposure branch and was denied `portfolio_non_positive_equity` (fail-closed by
design); the Redis peak ratchet ran live and held the running max across cycles. Test isolation: the
suite stays hermetic under the new default via an autouse conftest fixture that pins the guard OFF
(module-constant patch); the shipped default is pinned by `test_guard_enabled_by_default`.

## Advanced Portfolio Controls (2026-08-16)

Notional-concentration, correlation-bucket, and daily-loss entry checks layered onto the Phase A guard
(same engine, same `BOT_PORTFOLIO_RISK_ENABLED` master switch, same audit-event pipeline). All individually
opt-in (0 / empty disables). Per-market notional is the booked-exposure approximation `|size| × entryPrice`
per open perpetual — deterministic, needs no extra exchange reads (derived from the same
`get_open_positions` call the market-count check uses). Each pair entry projects `usd_per_trade` into each
of its two leg markets.

| Env Var                                    | Default | Check                                                                                                        | Denial reason                            | Test Exists |
|--------------------------------------------|---------|--------------------------------------------------------------------------------------------------------------|------------------------------------------|-------------|
| `BOT_PORTFOLIO_MAX_NOTIONAL_PER_MARKET_USD` | `0.0`   | Projected notional in either entry-leg market (existing + `usd_per_trade`) at/after cap                      | `portfolio_market_concentration`         | Yes         |
| `BOT_PORTFOLIO_MAX_TOTAL_NOTIONAL_PCT`      | `0.0`   | Projected gross notional (all markets + both legs) as % of equity — effective leverage ceiling                | `portfolio_gross_notional`               | Yes         |
| `BOT_PORTFOLIO_MAX_DAILY_LOSS_PCT`          | `0.0`   | Equity drop from the UTC-day peak (dated Redis key `bot:portfolio:daily_peak_equity:<address>:<YYYY-MM-DD>`, 48 h TTL — self-heals at UTC midnight, unlike the permanent all-time drawdown) at/after cap | `portfolio_daily_loss` | Yes |
| `BOT_PORTFOLIO_CORRELATION_BUCKETS`         | `""`    | `NAME:m1,m2,...:max_pct_of_equity` entries joined by `;` — projected bucket notional (members + member legs) vs cap. Malformed entries are skipped with a warning (fail-open parsing, first duplicate name wins) | `portfolio_bucket_concentration:<name>` | Yes |

Failure semantics: the notional controls are exchange-read-derived and **fail closed** — if any open
position's `size`/`entryPrice` cannot be parsed while a notional control is active, entries are denied with
`portfolio_notional_data_incomplete` instead of under-counting exposure. The daily-loss control is
Redis-backed auxiliary state and **fails open** (peak unavailable → check skips), identical to the all-time
drawdown slice. Coverage: advanced-control cases in `tests/test_portfolio_risk.py` (evaluator boundaries
and projections, bucket parser, dated-key store with TTL, wrapper daily-peak gating, per-market denial
through the real wrapper, `open_positions` leg-market wiring), plus config surfacing in
`tests/test_monitoring_routes.py`.
