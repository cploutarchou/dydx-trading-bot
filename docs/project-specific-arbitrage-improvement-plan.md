# Project-Specific Arbitrage Improvement Plan

Date: 2026-05-11

## 1. Improve Without Changing Logic

- Add observability counters and logs around existing scan cycles.
- Cache duplicate recent-candle fetches within one live scan cycle.
- Reuse existing cached market metadata for execution metadata lookup.
- Add import-safe Celery task hooks for configured worker schedules.
- Add optional diagnostics endpoints without changing existing response fields.

## 2. Keep Untouched

- `ZSCORE_THRESH`, side selection, hedge-ratio usage, size calculation, min order size checks, collateral checks, and z-score exit logic.
- `BotAgent.open_trades()` sequencing and emergency cleanup semantics.
- Frontend/backend existing endpoint paths and response fields.
- Database schema and migrations.
- Automatic execution behavior unless explicitly enabled later.

## 3. Add Behind Feature Flags

- `ARBITRAGE_IMPROVEMENTS_ENABLED=false`: enables live scan-cycle de-duplication and execution metadata cache reuse.
- `PAIR_PRIORITY_ENGINE_ENABLED=false`: enables live pair ranking.
- `POLYMARKET_SIGNALS_ENABLED=false`: reserved for future pair-priority signal input only.
- `DEFILLAMA_SIGNALS_ENABLED=false`: reserved for future pair-priority signal input only.
- `NEWS_SIGNALS_ENABLED=false`: reserved for future pair-priority signal input only.
- `AUTO_EXECUTION_CHANGES_ENABLED=false`: reserved; must remain false until explicitly reviewed.

## 4. Reduce API Calls

Implementation order:

1. Count current API/cache events in `bot/src/trading/market_data.py`.
2. Add scan-cycle candle cache in `bot/src/trading/position_manager.py`.
3. Route order metadata lookup through cached `get_markets()` in `bot/src/trading/account_manager.py` when improvements are enabled.
4. Later: collapse base/quote open-position checks into one account snapshot.

## 5. Improve Pair Prioritization

Add `bot/src/trading/pair_priority.py` and only invoke it in live trading when `PAIR_PRIORITY_ENGINE_ENABLED=true`.

Initial scoring uses existing internal data:

```text
final_pair_score =
    spread_potential_score
    + volume_score
    + liquidity_score
    + volatility_score
    + historical_opportunity_score
    - slippage_risk
    - stale_data_penalty
    - api_cost_penalty
```

No pair is removed unless `PAIR_PRIORITY_MAX_PAIRS` is explicitly set above zero.

## 6. Improve Caching

- Recent candle scan-cycle cache: one loop only, no cross-cycle execution-data staleness.
- Market metadata cache: use existing `MARKETS_CACHE_TTL_SECONDS`.
- External signals later: 30-300 second TTL and never direct execution impact.

## 7. Improve WebSocket Usage

Current frontend/backtest/runtime surfaces already use websocket plus HTTP recovery. dYdX market data does not currently use websocket streams in this codebase. Next phase should evaluate a dYdX websocket market-data adapter as a non-execution data source first.

## 8. Improve Risk Validation

Current hard checks remain. Safe additions:

- log rejection reasons with scan cycle ID;
- expose stale pair-analysis count;
- later: one-shot account snapshot before checking both legs;
- later: explicit stale-price guard before order placement behind `AUTO_EXECUTION_CHANGES_ENABLED`.

## 9. Improve Observability

Expose counters:

- `arbitrage_scan_cycles_total`
- `exchange_api_calls_total`
- `exchange_api_calls_saved_total`
- `duplicate_api_calls_avoided_total`
- `pair_candidates_total`
- `pair_candidates_skipped_total`
- `opportunities_detected_total`
- `opportunities_rejected_total`
- `opportunities_executed_total`
- `stale_data_detected_total`
- `provider_errors_total`
- `cache_hits_total`
- `cache_misses_total`
- `websocket_reconnects_total`

## 10. Exact Files To Modify

- `bot/src/constants.py`
- `bot/src/trading/arbitrage_observability.py`
- `bot/src/trading/pair_priority.py`
- `bot/src/trading/market_data.py`
- `bot/src/trading/position_manager.py`
- `bot/src/trading/account_manager.py`
- `bot/src/api/server.py`
- `bot/src/infrastructure/workers/market_sync_tasks.py`
- `bot/src/infrastructure/workers/candle_aggregate_tasks.py`
- `backend/internal/services/bot_api_client_extended.go`
- `backend/internal/routes/bot_api_delegate_routes.go`
- `backend/internal/routes/bot_api_delegate_control_plane_test.go`
- `frontend/src/api.ts`
- `frontend/src/components/BotManager.tsx`
- `frontend/src/components/ArbitrageImprovementPanel.tsx`
- `bot/tests/test_pair_priority_engine.py`
- `bot/tests/test_arbitrage_cycle_cache.py`
- root docs and config examples

## 11. Implementation Order

1. Document current flow and risks.
2. Add flags and metrics.
3. Add optional pair-priority scorer.
4. Add live scan-cycle cache.
5. Add cached metadata path for execution metadata.
6. Add bot metrics/diagnostic endpoints.
7. Proxy diagnostics through the backend without changing existing contracts.
8. Add the frontend diagnostics panel as an additive bot-manager surface.
9. Add tests and docs.

## 12. Rollback Plan

1. Set all new feature flags to `false`.
2. Set `PAIR_PRIORITY_MAX_PAIRS=0` or unset it.
3. If metrics endpoint causes operational issues, remove backend `/metrics` bot dependency expectation or revert `bot/src/api/server.py` changes.
4. Revert the small patch set touching `bot/src/trading/*`, `bot/src/api/server.py`, backend proxy routes, frontend API/panel files, and worker hook modules.
5. No database rollback is required because no schema changes are introduced.
