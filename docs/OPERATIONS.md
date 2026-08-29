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

## Operational cautions

- `abort_all_positions` acts on the whole shared subaccount — instances on the
  same subaccount will flatten each other's hedges.
- Migrations (`make migration-up`) are explicit; do not rely on startup
  schema changes. Seeded accounts (`admin`, `user`, `officer`, `ib`) must have
  their passwords rotated before any internet-facing deployment.
- Never run tests against production infra; the suite is hermetic for a reason.
