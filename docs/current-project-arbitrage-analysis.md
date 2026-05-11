# Current Project Arbitrage Analysis

Date: 2026-05-11

## Current Architecture Summary

This monorepo runs a three-service trading platform:

- `frontend/`: React/Vite operator UI. It does not talk to exchanges directly.
- `backend/`: Go/Gin public API, auth, RBAC, backtest sync, and bot API proxy.
- `bot/`: Python FastAPI control plane, Celery backtest worker, dYdX client, live strategy subprocesses, pair storage, and execution logic.

The runtime boundary is `frontend -> backend -> bot -> dYdX`. Live trading logic is concentrated in `bot/src/trading/*`. Backtest pair routing and pair ranking are concentrated in `bot/src/infrastructure/use_cases/service_backtest.py`.

## Current Arbitrage Flow

The existing “arbitrage” implementation is dYdX statistical pairs trading:

1. A bot instance starts through `bot/src/main_instance.py`.
2. If `findCointegratedPairs` is enabled, `construct_market_prices()` in `bot/src/trading/market_data.py` fetches dYdX perpetual markets and historical candles.
3. `store_cointegration_results()` in `bot/src/trading/analysis/cointegration.py` tests market combinations and stores qualifying pairs through `pair_storage`.
4. The live loop runs every 5 seconds.
5. `open_positions()` in `bot/src/trading/position_manager.py` loads stored pairs, fetches recent candles, calculates the current spread z-score, and opens a two-leg trade when `abs(z_score) >= ZSCORE_THRESH`.
6. `BotAgent.open_trades()` in `bot/src/trading/bot_agent.py` places leg 1, confirms fill, then places leg 2. If leg 2 fails after leg 1 fills, it attempts emergency reduce-only cleanup of leg 1.
7. `manage_trade_exits()` closes tracked pairs when the z-score crosses back according to the existing `CLOSE_AT_ZSCORE_CROSS` rule.

## Current Pair-Selection Flow

Live trading uses stored cointegrated pairs from `bot/src/infrastructure/domain/cointegration_storage.py`. Pair order is whatever was persisted by the cointegration scan.

Backtests already have richer pair-selection support in `BacktestService`:

- `input`: preserve requested order.
- `liquidity`: rank by dYdX metadata volume/liquidity fields.
- `volatility`: rank by fetched historical return volatility.
- `cointegration`: rank using statistical cointegration and stationarity checks when dependencies are available.

Frontend pair selection is exposed in `frontend/src/components/BacktestRunner.tsx`, with backend request normalization in `backend/internal/routes/bot_api_delegate_routes.go`.

## Current API-Call Flow

- Market metadata: `bot/src/trading/market_data.py:get_markets()` has an in-process TTL cache controlled by `MARKETS_CACHE_TTL_SECONDS`.
- Recent candles: `get_candles_recent()` has an in-process TTL cache and tries Redis keys written by the intended market sync path.
- Historical candles: `get_candles_historical()` fetches multiple windows per market with bounded concurrency in `construct_market_prices()`.
- Live entries: `open_positions()` fetches recent candles for both markets in every candidate pair.
- Execution: `place_market_order()` and `cancel_order()` previously fetched per-market metadata directly, bypassing the cached `get_markets()` path.
- Backend markets endpoint: `/api/v1/markets/perpetuals` has a fresh/stale cache in `bot/src/api/server.py` and is proxied by the Go backend.

## Current Execution/Risk Flow

Existing live execution safety includes:

- two-leg entry sequencing with emergency cleanup if the second leg fails;
- reduce-only close retries in exit management;
- orphaned leg detection and recovery;
- minimum collateral and collateral-buffer checks before entry;
- min order size checks using dYdX market metadata;
- dYdX precision formatting via `format_number()`;
- entry failure backoff per pair.

These rules are preserved. No entry threshold, side selection, sizing rule, or exit trigger is changed by default.

## Current Frontend/Bot Flow

The frontend uses backend APIs only. Important surfaces:

- Backtest runner and selected-market flow: `frontend/src/components/BacktestRunner.tsx`
- Strategy runtime operator view: `frontend/src/components/StrategyManager.tsx`
- API client and websocket helpers: `frontend/src/api.ts`, `frontend/src/api/hooks.ts`
- Backend delegated bot/backtest routes: `backend/internal/routes/bot_api_delegate_routes.go`
- Bot FastAPI routes and websocket channels: `bot/src/api/server.py`

## Bottlenecks

- Live `open_positions()` can request the same market’s recent candles multiple times in one scan when pairs share a market.
- Execution metadata fetches in `place_market_order()` and `cancel_order()` bypassed the cached market metadata path.
- `is_open_positions()` checks base and quote separately, causing repeated account calls per detected opportunity.
- Live pair order did not have an optional prioritization step; backtests had ranking, but live trading did not.
- Bot service had no `/metrics` endpoint even though backend `/metrics` probes `BOT_API_URL/metrics`.
- Celery included `market_sync_tasks` and `candle_aggregate_tasks`, but those modules were absent, making scheduler/worker startup brittle.

## Duplicated API Calls

- Recent candle fetches across pairs with common markets.
- Per-order market metadata fetches during order placement/cancellation.
- Base/quote open-position checks after a z-score trigger.
- Backtest history fetches are already cached per market in a run; live trading needed the same-cycle equivalent.

## Missing Cache Opportunities

- Scan-cycle candle cache for live entry loops.
- Cached market metadata reuse during order placement.
- Optional pair-priority cache if ranking later uses expensive external signals.
- External signal snapshots must be cached if enabled later.

## Missing Observability

- No bot-local `/metrics` payload for backend dependency probing.
- No counters for API calls saved, duplicate calls avoided, opportunities rejected, stale pair analysis, or cache hits/misses.
- Logs did not consistently include scan cycle ID and rejection reason in live entry decisions.

## Safe Improvement Opportunities

- Add required feature flags with defaults off.
- Add in-process counters and bot metrics endpoints.
- Add same-cycle candle de-duplication behind `ARBITRAGE_IMPROVEMENTS_ENABLED`.
- Reuse cached market metadata for order placement behind `ARBITRAGE_IMPROVEMENTS_ENABLED`.
- Add optional live pair-priority ranking behind `PAIR_PRIORITY_ENGINE_ENABLED`.
- Add import-safe Celery task hooks for configured scheduler names.

## Files/Functions Needing Attention

- `bot/src/trading/position_manager.py`: live entry loop, rejection logs, cycle cache.
- `bot/src/trading/account_manager.py`: execution metadata calls.
- `bot/src/trading/market_data.py`: API/cache counters.
- `bot/src/trading/pair_priority.py`: optional pair scoring.
- `bot/src/trading/arbitrage_observability.py`: counters.
- `bot/src/api/server.py`: `/metrics` and optional arbitrage diagnostics.
- `bot/src/infrastructure/workers/celery_app.py`: scheduler imports.
- `backend/internal/routes/bot_api_delegate_routes.go`: future proxy for new arbitrage endpoints if the frontend consumes them.
- `frontend/src/components/StrategyManager.tsx`: future display target for priority explanations/metrics.
