# dYdX Bot Production Readiness Playbook

This playbook is a practical checklist to harden the bot for production while validating behavior on testnet with production-like assumptions.

Related runbooks and references:

- `API_CONTRACT.md`
- `LOCAL_SETUP.md`
- `openapi.json`
- `tasks.md`
- `../README.md`

## 1) Immediate gate (before every deployment)

From `bot/` run:

- `make preflight-testnet`
- `make preflight-testnet-strict` (for release candidates)
- `make health` (if Docker stack is running)

The preflight validates:

- environment/config load
- testnet mode (`IS_TESTNET=true`)
- indexer endpoint reachability
- wallet/mnemonic placeholder detection
- basic trade safety flag coherence
- production-like simulation parameter sanity (fee/slippage/risk-free)

## 2) Testnet environment baseline

Required:

- `IS_TESTNET=true`
- valid testnet wallet + mnemonic
- sufficient testnet collateral
- telemetry configured (at minimum stdout logs, ideally Loki/Grafana)

Recommended safety defaults for staging:

- `BOT_PLACE_TRADES=false` initially
- `BOT_MANAGE_EXITS=true`
- `BOT_USD_PER_TRADE` low (e.g. 5–20)

## 3) Production-like simulation on testnet

Use production-like assumptions in config/env while staying on testnet endpoints:

- transaction fee representative of live maker/taker behavior
- slippage assumptions reflecting expected position size
- realistic risk-free / benchmark assumptions for analytics

Then run backtesting/API flows and compare:

- fill quality assumptions
- expected PnL distribution
- drawdown behavior
- cleanup/orphan prevention behavior

## 4) Hardening roadmap (next milestones)

1. **Execution safety**
   - enforce atomic pair execution path tests
   - add explicit regression tests for cleanup on second-leg failure

2. **Operational controls**
   - kill-switch + circuit-breaker policy
   - deploy-time reduced exposure mode

3. **Observability**
   - standardized structured events for open/close/failure/cleanup
   - alerting for repeated cleanup events and loop stalls
   - verify `/ws/strategies` emits startup/stop/crash transitions and that per-instance log files are collected by operators

4. **Reliability testing**
   - chaos-style tests for API timeouts, partial failures, and restart recovery
   - validate dead-process monitor catches crashed workers without requiring manual status polling

## 5) Go/No-Go criteria

Deploy only when all are true:

- preflight passes (strict mode for RCs)
- no unresolved execution-safety blockers
- testnet behavior stable for agreed burn-in window
- rollback and emergency-close procedures are verified

## 6) Runtime visibility baseline

For API-controlled strategy runtimes, require all of the following before calling an environment production-ready:

- per-instance subprocess logs are persisted under `bot_states/bot_<instance_id>.log`
- dead-process cleanup runs continuously, not only on startup or manual status requests
- `/ws/strategies` provides a snapshot on connect and lifecycle updates on create/start/stop/error paths
- backend and frontend can both recover from missed websocket events by reconciling against HTTP runtime state
- `/ready` returns `200` only when the bot manager is initialized, so orchestration can distinguish liveness from actual traffic readiness
- request-scoped `X-Trace-Id` values survive backend delegation and websocket proxying for operator triage
- `/api/v1/capabilities` reports expected HTTP and websocket control surfaces consumed by backend integrations
- bot runtime persistence is pointed at a dedicated PostgreSQL target via `BOT_DATABASE_URL` or `BOT_DB_*` settings
- DB migration rollout uses explicit cutover mode progression (`shared` -> `dedicated_with_shared_fallback` -> `dedicated`) with rollback by reverting to `shared`
