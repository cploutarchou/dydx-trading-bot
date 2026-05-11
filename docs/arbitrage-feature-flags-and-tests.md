# Feature Flags and Test Coverage for Arbitrage Improvements

Date: 2026-05-11

## Required Feature Flags

All new/improved behaviors must be guarded by feature flags (default: false):

- `ARBITRAGE_IMPROVEMENTS_ENABLED=false`  
  Enables live scan-cycle candle de-duplication and cached market metadata for order placement/cancellation.
- `PAIR_PRIORITY_ENGINE_ENABLED=false`  
  Enables live pair-priority scoring and ranking.
- `POLYMARKET_SIGNALS_ENABLED=false`  
  Enables Polymarket-based external signal provider for pair ranking.
- `DEFILLAMA_SIGNALS_ENABLED=false`  
  Enables DefiLlama-based external signal provider for pair ranking.
- `NEWS_SIGNALS_ENABLED=false`  
  Enables news-based external signal provider for pair ranking.
- `AUTO_EXECUTION_CHANGES_ENABLED=false`  
  Enables any changes to execution logic (must remain false by default).
- `PAIR_PRIORITY_MAX_PAIRS=0`  
  (Optional) Limits number of pairs considered in live trading when pair-priority engine is enabled.

## Test Coverage Requirements

### Existing Tests to Run
- All current bot, backend, and frontend tests (unit, integration, end-to-end)
- Backtest and live trading result equivalence when feature flags are false
- API compatibility and schema stability

### New/Extended Tests to Add
- Feature flag toggling: verify new logic is only active when enabled
- Scan-cycle candle cache: verify duplicate API calls are avoided in a single scan
- Market metadata cache: verify order placement/cancellation uses cache when enabled
- Pair-priority engine: verify pair ranking, scoring, and explanations
- External signal providers: verify signals only affect pair ranking, not execution
- Observability: verify all new metrics/counters/logs are emitted as expected
- Risk validation: verify all rejection reasons are logged and surfaced
- Stale data detection: verify stale data is detected and logged
- Provider failure handling: verify circuit breaker/backoff logic
- API endpoints: verify new endpoints are additive and backward-compatible

### Test Files to Update or Add
- `bot/tests/test_pair_priority_engine.py`
- `bot/tests/test_arbitrage_cycle_cache.py`
- `bot/tests/test_arbitrage_observability.py`
- `bot/tests/test_feature_flags.py`
- `backend/internal/routes/arbitrage_settings_routes_test.go`
- `backend/internal/routes/bot_api_delegate_control_plane_test.go`
- `frontend/src/components/ArbitrageImprovementPanel.test.tsx`

## Manual Verification
- Run all tests with feature flags off (default) and on (individually)
- Confirm no breaking changes to API, UI, or trading logic by default
- Confirm all new metrics, logs, and endpoints are visible when enabled

---

This document should be updated as new features or tests are added during implementation.
