# NATS command/event contract

## Purpose

Define the subject namespace for command and event transport while keeping the current HTTP control path active.

## Feature flags

- `NATS_ENABLED=false` by default
- `BOT_COMMAND_BUS_ENABLED=false` by default

## Subject map

### Bot command subjects

- `bot.command.start`
- `bot.command.stop`
- `bot.command.restart`
- `bot.command.execute_trade`

### Bot event subjects

- `bot.event.started`
- `bot.event.stopped`
- `bot.event.trade_opened`
- `bot.event.trade_closed`

### Backtest command subjects

- `backtest.command.start`
- `backtest.command.cancel`

### Backtest event subjects

- `backtest.event.completed`
- `backtest.event.failed`

## Expected ownership

- Backend remains the public API contract owner.
- Bot remains the runtime / exchange owner.
- NATS is a transport layer, not a source of truth.

## Operational rules

- Do not replace HTTP control paths until the NATS path is fully validated.
- Use JetStream durability for operational commands and important lifecycle events.
- Keep message payloads small and reference-heavy.
- Store durable results in PostgreSQL / ClickHouse / MinIO, not only in the bus.

## Minimal payload shape

The payloads should include:

- correlation / request id
- subject-specific action metadata
- actor / instance id
- timestamps in UTC
- reference identifiers instead of large result blobs

## Rollback plan

- If the bus path fails, disable `NATS_ENABLED` and keep HTTP control enabled.
- Do not couple app startup to bus availability.
- Do not make command bus support a hard dependency for local development.

## Files expected to change

- `backend/internal/nats/*`
- `bot/src/infrastructure/nats/*`
- `backend/config/config.go`
- `bot/src/infrastructure/database.py` or service config only if NATS values are wired there later
- deployment manifests for JetStream, publisher, and subscriber wiring
