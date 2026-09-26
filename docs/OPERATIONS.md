# Operations Guide

## Running the platform

- Local: `make stack-up-dev` (all services) or `make infra-up` (infra only).
- Background bot lifecycle: `make start` / `make stop` / `make status` / `make logs`.
- Bot API standalone: `cd bot && python -m uvicorn src.api.server:app --port 8889`.
- Worker standalone: `cd bot && python src/main_instance.py --instance-id "bot-1"`.

## Monitoring & alerting

- Runtime telemetry: Prometheus metrics (`arbitrage_observability`), structured
  logs (Loguru/Loki), Grafana dashboards (`make docker-up-logging`).
- Telegram alerts: critical execution failures, emergency cleanups, exit
  confirmations, risk-guard rejections.
- See [`.github/skills/defi-observability-metrics/SKILL.md`](../.github/skills/defi-observability-metrics/SKILL.md)
  for the metrics/alerting inventory.

## Emergency procedures

1. **Stop one instance** — dashboard or `POST /api/v1/bots/:id/stop`.
2. **Flatten everything (dangerous, shared subaccount!)** — instance flag
   `abortAllPositions`: cancels open orders and reduce-only closes ALL
   positions on the subaccount, then alerts.
3. **Credentials** — rotate on the exchange first, then re-encrypt the config
   profile (`make config-key-rotate`).
4. **Entry halt** — a bot stops opening pairs on its subaccount after a failed
   emergency close, or when the strategy's max drawdown is reached. Open
   positions keep their exits. Check the account on dYdX, then clear the halt
   from the strategy card (acknowledged and audit-logged). Clearing a drawdown
   halt starts a new drawdown measurement from the current equity.

## Operational cautions

- `abort_all_positions` acts on the whole shared subaccount — instances on the
  same subaccount will flatten each other's hedges.
- Migrations (`make migration-up`) are explicit; do not rely on startup
  schema changes. Seeded accounts (`admin`, `user`, `officer`, `ib`) must have
  their passwords rotated before any internet-facing deployment.
- Never run tests against production infra; the suite is hermetic for a reason.
- A strategy's max drawdown is measured on the equity of the subaccount the bot
  trades on: a withdrawal counts as drawdown, and anything else held on that
  subaccount moves its equity too. On a large account a small percentage is a
  large dollar amount; preflight states the amount before a start.
- Run the bot migration Job (up to `0008_drawdown_peaks`) before the new bot-api
  serves runtimes. A runtime with a drawdown limit opens no pairs while it
  cannot read its stored peak.
- The cost and funding entry gate (`COST_GATE_ENABLED`, default off) is enabled
  on live bots through the bot-api deployment environment plus a restart. The
  arbitrage runtime-settings page changes the bot API process only, and
  trading workers never see those overrides (true of every arbitrage runtime
  flag). With the gate on, a bot opens no pairs while the markets payload lacks
  `nextFundingRate`, or while the strategy's z-score exit
  (`close_at_zscore_cross`) is off: both are deliberate fail-closed states.
  Gate rejections are in the per-instance worker log (`opportunity_rejected
  ... reason=edge_lt_cost|funding_same_side|cost_inputs_invalid`); the
  dashboard's rejection panel shows the API process's counters, not the
  workers'. See [bot/README.md](../bot/README.md#cost-and-funding-entry-gate).
