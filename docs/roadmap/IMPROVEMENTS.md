# Improvements

Canonical index for project improvement planning and follow-up work.

## Incident Hardening Snapshot (2026-05-16)

- ✅ Bot execution safety hardened: order status handling now treats only confirmed `FILLED` as success; failed/cancelled variants are normalized and rejected.
- ✅ Backend websocket ownership guard enforced for `/api/v1/backtests/:run_id/push` and `/ws/backtests/:run_id`.
- ✅ Production fail-closed baseline added in backend startup: placeholder JWT secrets and missing CORS origin allowlists now block startup in production.
- ✅ Backtest push hub resilience improved: safe connection snapshots, stale socket pruning, websocket write deadlines, and Redis pub/sub reconnect with backoff.
- ✅ Candle cache warmup overwrite fixed: warm cache stores full market candle set per key instead of overwriting by page.
- ✅ Redis cache operational safety improved: timeout-bounded operations and SCAN-based pattern deletion replacing KEYS.
- ✅ Bot async-notification path improved: Telegram send/retry logic is offloaded when called from an active event loop.
- ✅ Bot schema compatibility test suite updated to current realtime compatibility columns.
- ✅ Backtests frontend push socket now uses backend websocket URL resolver and token strategy (no direct `window.location.host` assumption).
- ✅ Root Makefile `install`/`test` targets updated to service-oriented monorepo commands.

## Arbitrage Platform

- [Current Project Arbitrage Analysis](../current-project-arbitrage-analysis.md)
- [Project-Specific Arbitrage Improvement Plan](../project-specific-arbitrage-improvement-plan.md)
- [API Call Optimization Plan](../api-call-optimization-plan.md)
- [Pair Priority Engine Plan](../pair-priority-engine-plan.md)
- [Risk And Observability Plan](../risk-and-observability-plan.md)
- [Codex Final Report](../codex-final-report.md)

## Existing Planning References

- [Project Improvement Plan](PROJECT_IMPROVEMENT_PLAN.md)
- [Improvement Tasks](IMPROVEMENT_TASKS.md)
