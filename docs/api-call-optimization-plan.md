# API Call Optimization Plan

## Current Calls

- dYdX market metadata via `get_markets()` and direct `get_perpetual_markets(ticker)`.
- Recent candles via `get_candles_recent()`.
- Historical candles via `get_candles_historical()` and `BacktestService._fetch_market_history()`.
- Account/order calls via `account_manager.py`.

## Implemented Safe Optimizations

- Counters for API calls, cache hits/misses, provider errors, and saved calls.
- Same-cycle candle cache in live entry scanning behind `ARBITRAGE_IMPROVEMENTS_ENABLED`.
- Cached market metadata reuse during `place_market_order()` and `cancel_order()` behind `ARBITRAGE_IMPROVEMENTS_ENABLED`.
- Import-safe Celery scheduler task modules so configured worker schedules do not fail at import.

## TTL Guidance

- Recent candle snapshot: existing `CANDLES_RECENT_CACHE_TTL_SECONDS`, default 30 seconds.
- Market metadata: existing `MARKETS_CACHE_TTL_SECONDS`, default 60 seconds.
- Backend market endpoint stale fallback: existing `MARKETS_STALE_TTL_SECONDS`, default 300 seconds.
- External signals later: 30-300 seconds.

## Next API Reductions

- Add dYdX websocket market-data adapter as read-only input.
- Add Redis-backed recent-candle sync only after the missing task has a concrete implementation and operational owner.

## Completed Since Initial Plan

- Replaced two `is_open_positions()` calls per detected opportunity with one
	`get_open_positions()` snapshot behind `ARBITRAGE_IMPROVEMENTS_ENABLED`,
	with safe fallback to legacy checks if snapshot retrieval fails.
- Added account/order/subaccount-order API call instrumentation so API-call
	reductions are measurable (`exchange_api_calls_total`,
	`exchange_api_calls_saved_total`, `duplicate_api_calls_avoided_total`).
