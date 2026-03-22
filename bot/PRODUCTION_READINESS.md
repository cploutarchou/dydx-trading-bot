# dYdX Bot Production Readiness Playbook

This playbook is a practical checklist to harden the bot for production while validating behavior on testnet with production-like assumptions.

Related runbooks and references:

- `docs/OPERATIONS_RUNBOOK.md`
- `docs/FAILURE_MODES.md`
- `docs/MULTI_INSTANCE_ARCHITECTURE.md`
- `docs/FEATURE_STATUS.md`
- `docs/CONFIG_MATRIX.md`

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

4. **Reliability testing**
   - chaos-style tests for API timeouts, partial failures, and restart recovery

## 5) Go/No-Go criteria

Deploy only when all are true:

- preflight passes (strict mode for RCs)
- no unresolved execution-safety blockers
- testnet behavior stable for agreed burn-in window
- rollback and emergency-close procedures are verified
