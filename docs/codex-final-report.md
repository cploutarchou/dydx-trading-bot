# Codex Final Report

Date: 2026-05-11

## What Was Scanned

Scanned the monorepo structure and relevant implementation paths across:

- `bot/src/trading/*`
- `bot/src/infrastructure/use_cases/service_backtest.py`
- `bot/src/infrastructure/workers/*`
- `bot/src/api/server.py`
- `backend/internal/routes/bot_api_delegate_routes.go`
- `backend/internal/services/bot_api_client_extended.go`
- `backend/internal/app/health.go`
- `frontend/src/api.ts`
- `frontend/src/api/hooks.ts`
- `frontend/src/components/BotManager.tsx`
- `frontend/src/components/ArbitrageImprovementPanel.tsx`
- `frontend/src/components/BacktestRunner.tsx`
- `frontend/src/components/StrategyManager.tsx`
- root/service README, docs, Docker, config, and CI references

## Current Architecture Summary

The current platform boundary remains `frontend -> backend -> bot -> dYdX`. Arbitrage is implemented as statistical pairs trading on dYdX perpetuals. Cointegrated pairs are discovered from historical candles, stored in pair storage, and scanned live for z-score entry/exit conditions.

## Current Logic Preserved

No default business logic changed:

- z-score threshold behavior is unchanged;
- pair side selection is unchanged;
- hedge-ratio and sizing logic are unchanged;
- collateral and min-order checks are unchanged;
- two-leg execution and emergency cleanup are unchanged;
- exit trigger behavior is unchanged;
- all new execution-adjacent behavior is off by default.

## What Improved

- Added required feature flags with safe defaults.
- Added bot-local arbitrage metrics counters.
- Added `/metrics`, `/api/v1/arbitrage/improvement-metrics`, and `/api/v1/arbitrage/pair-priority` to the bot API.
- Added optional `/api/v1/arbitrage/opportunity/{id}/explain` diagnostics endpoint (bot + backend proxy + frontend client method).
- Added authenticated Go backend proxy routes for the new arbitrage diagnostics.
- Added a frontend arbitrage intelligence panel on the non-embedded bot manager surface.
- Added admin Settings controls that persist arbitrage runtime flags in `bot_settings` and sync them to the bot process.
- Added audit logging for admin arbitrage runtime setting updates.
- Added same-cycle recent-candle de-duplication behind `ARBITRAGE_IMPROVEMENTS_ENABLED`.
- Reused cached market metadata for order placement/cancellation behind `ARBITRAGE_IMPROVEMENTS_ENABLED`.
- Collapsed per-opportunity open-position checks into one account snapshot behind `ARBITRAGE_IMPROVEMENTS_ENABLED` (with safe fallback to legacy checks).
- Added API-call/provider-error metric coverage for account/order/subaccount-order indexer paths in `account_manager`.
- Added optional pair-priority scoring behind `PAIR_PRIORITY_ENGINE_ENABLED`.
- Added scan cycle IDs and rejection reason logs.
- Added centralized rejection-reason counters (`rejection_reasons`) in arbitrage metrics payloads.
- Surfaced top rejection reasons in `frontend/src/components/ArbitrageImprovementPanel.tsx` as additive operator diagnostics.
- Added UI action to fetch explainability details for a selected rejection reason via delegated endpoint.
- Locked backend delegated metrics contract to preserve `rejection_reasons` in `bot_api_delegate_control_plane_test`.
- Added backend proxy and integration assertion for delegated opportunity explain diagnostics.
- Added import-safe Celery hook modules for configured market sync and candle aggregation tasks.

## Files Changed

- `README.md`
- `IMPROVEMENTS.md`
- `env.example`
- `bot/src/constants.py`
- `bot/src/api/server.py`
- `bot/src/trading/arbitrage_observability.py`
- `bot/src/trading/arbitrage_runtime_config.py`
- `bot/src/trading/pair_priority.py`
- `bot/src/trading/market_data.py`
- `bot/src/trading/position_manager.py`
- `bot/src/trading/account_manager.py`
- `bot/src/infrastructure/workers/market_sync_tasks.py`
- `bot/src/infrastructure/workers/candle_aggregate_tasks.py`
- `backend/internal/services/bot_api_client_extended.go`
- `backend/internal/routes/arbitrage_settings_routes.go`
- `backend/internal/routes/arbitrage_settings_routes_test.go`
- `backend/internal/routes/bot_api_delegate_routes.go`
- `backend/internal/routes/bot_api_delegate_control_plane_test.go`
- `backend/internal/routes/bot_instance_contract_lock_test.go`
- `frontend/src/api.ts`
- `frontend/src/components/BotManager.tsx`
- `frontend/src/components/ArbitrageImprovementPanel.tsx`
- `frontend/src/components/ArbitrageRuntimeSettings.tsx`
- `frontend/src/pages/Settings.tsx`
- `bot/tests/test_pair_priority_engine.py`
- `bot/tests/test_arbitrage_cycle_cache.py`
- `bot/tests/test_account_manager_metrics.py`
- `docs/current-project-arbitrage-analysis.md`
- `docs/project-specific-arbitrage-improvement-plan.md`
- `docs/api-call-optimization-plan.md`
- `docs/pair-priority-engine-plan.md`
- `docs/risk-and-observability-plan.md`
- `docs/arbitrage-feature-flags-and-tests.md`

## Feature Flags Added

- `ARBITRAGE_IMPROVEMENTS_ENABLED=false`
- `PAIR_PRIORITY_ENGINE_ENABLED=false`
- `POLYMARKET_SIGNALS_ENABLED=false`
- `DEFILLAMA_SIGNALS_ENABLED=false`
- `NEWS_SIGNALS_ENABLED=false`
- `AUTO_EXECUTION_CHANGES_ENABLED=false`

Optional tuning:

- `PAIR_PRIORITY_MAX_PAIRS=0`
- `PAIR_PRIORITY_STALE_SECONDS=86400`

## Tests Added

- Pair-priority scoring and stale-analysis detection.
- Same-cycle candle cache behavior enabled and disabled.
- Account-manager API metric increments (success + provider-error paths).
- Open-position snapshot optimization path and fallback path.
- Rejection reason aggregation and reset behavior in observability snapshot.
- Backend DB-backed arbitrage runtime setting persistence and bot payload mapping.
- Backend delegated arbitrage metrics proxy preservation of `rejection_reasons`.
- Backend delegated arbitrage opportunity explain proxy path and response passthrough.

## Verification

Passed in this session:

```bash
/home/chris/workspace/dydx-trading-bot/.venv/bin/python -m py_compile bot/src/trading/account_manager.py bot/src/trading/position_manager.py
/home/chris/workspace/dydx-trading-bot/.venv/bin/python -m pytest bot/tests/test_arbitrage_cycle_cache.py bot/tests/test_account_manager_metrics.py -q
# latest run: 8 passed
/home/chris/workspace/dydx-trading-bot/.venv/bin/python -m pytest bot/tests/test_arbitrage_cycle_cache.py bot/tests/test_account_manager_metrics.py bot/tests/test_arbitrage_observability.py -q
# latest run: 10 passed
cd /home/chris/workspace/dydx-trading-bot/backend && go test -tags integration ./internal/routes -run TestDelegateCapabilitiesAndRuntimeDBConfigRoutes -count=1
# latest run: ok
```

Not rerun in this session:

- backend Go test matrix
- frontend build/lint matrix

## Expected API Call Reduction

With `ARBITRAGE_IMPROVEMENTS_ENABLED=true`:

- repeated recent-candle lookups for the same market in a single live scan are avoided;
- execution metadata calls can reuse the existing cached market metadata payload;
- counters expose saved calls via `exchange_api_calls_saved_total` and `duplicate_api_calls_avoided_total`.

Actual reduction depends on pair overlap. A pair universe with shared high-liquidity anchors like BTC/ETH/SOL should see the largest same-cycle savings.

## Risks

- Pair-priority ranking changes scan order when explicitly enabled.
- `PAIR_PRIORITY_MAX_PAIRS > 0` intentionally skips lower-ranked pairs and should be tested in paper/testnet first.
- External signal flags are reserved only; providers are not implemented in this patch.
- Admin DB settings sync to the running bot process; if the bot API is unreachable, DB values are saved and sync status reports `bot_unreachable`.
- Runtime settings intentionally store only non-secret flags/tuning values; secrets remain in encrypted credential/key tables.
- The Celery hook tasks are import-safe compatibility hooks, not full Redis market-sync/aggregation implementations.

## Rollback Steps

1. Set all new feature flags to `false`.
2. Unset `PAIR_PRIORITY_MAX_PAIRS` or set it to `0`.
3. Use `Settings -> Arbitrage Runtime` to save and sync the disabled values, or update `bot_settings` section `arbitrage` directly.
4. Revert the backend proxy/settings and frontend panel/settings patch if user-facing controls should be hidden.
5. Revert the bot code patch if passive metrics/endpoints are not wanted.
6. No DB migration rollback is required.

## Recommended Next Phase

1. Add a real Redis market-candle sync task if operators want shared candle snapshots.
2. Add stale-price and abnormal-spread guards behind `AUTO_EXECUTION_CHANGES_ENABLED` after a testnet dry run.
3. Add real external signal providers behind their reserved feature flags.
