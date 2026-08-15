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
