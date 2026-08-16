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
| `max_drawdown_pct`       | `src/shared/live_risk_controls.py`, `src/api/server.py::runtime_preflight`, `src/api/server.py::create_bot_instance`, `src/bot_instance_manager.py`, `src/main_instance.py` | Rejected          | Rejected         | Yes                                    | REJECTED | Rejected because no live runtime drawdown monitor currently enforces it. Operators must set this to `0`.                             |
| `trailing_stop_pct`      | `src/shared/live_risk_controls.py`, `src/api/server.py::runtime_preflight`, `src/api/server.py::create_bot_instance`, `src/bot_instance_manager.py`, `src/main_instance.py` | Rejected          | Rejected         | Yes                                    | REJECTED | Rejected because trailing-stop logic is not implemented in the live runtime. Operators must set this to `0`.                         |
| `capital_allocation_usd` | `src/shared/live_risk_controls.py`, `src/api/server.py::runtime_preflight`, `src/api/server.py::create_bot_instance`, `src/bot_instance_manager.py`, `src/main_instance.py` | Rejected          | Rejected         | Yes                                    | REJECTED | Rejected because the live runtime does not enforce cumulative allocation limits at order-entry time. Operators must set this to `0`. |

## Account-Level (Portfolio) Controls — Phase A (2026-08-15)

Cross-instance controls evaluate the SHARED dYdX subaccount (equity, free collateral, open perpetual
markets) before any new entry, closing the "N instances each within per-instance limits while the account
is over-exposed" gap. The subaccount already reflects every instance's fills, so it is the authoritative
aggregate view with no cross-process state. Engine: `src/trading/portfolio_risk.py`; wired into
`position_manager.open_positions` after the per-instance `max_positions` check; every denial is
rejection-counted, warning-logged, and persisted as a `trade_entry_rejected_portfolio_risk` audit event.

**Phase A: opt-in — set `BOT_PORTFOLIO_RISK_ENABLED=true` to activate.** Any limit <= 0 disables that
check. Fail-closed for malformed account data (`portfolio_data_unavailable`); transport errors propagate
exactly like the existing free-collateral guards.

| Env Var                                    | Default | Check                                                                                                                                   | Denial reason                     | Test Exists |
|--------------------------------------------|---------|-----------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------|-------------|
| `BOT_PORTFOLIO_RISK_ENABLED`               | `false` | Master switch (off → guard short-circuits without exchange reads)                                                                        | —                                 | Yes         |
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
ACCOUNT-level control — the per-instance config field `max_drawdown_pct` remains REJECTED (bot-level
semantics, still unenforced by a per-bot drawdown monitor).

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
