# NATS command/event contract

## Status Updates — 2026-06-28

- [x] DONE — Normalized PostgreSQL task tables for command idempotency foundation
  - Files: `backend/migrations/postgres/000063_create_task_commands.*`, `000064_create_task_runs.*`, `000065_create_task_attempts.*`, `000066_create_worker_heartbeats.*`, `backend/internal/models/models.go`, `backend/internal/repository/task_repository.go`, `backend/internal/repository/task_repository_test.go`
  - Check: `cd backend && go test ./internal/repository/... -run TestTaskRepository -v` → 13/13 PASS
  - Evidence: Four normalized task tables provide PostgreSQL backing for NATS command idempotency keys (`Msg-Id`) and durable state that both HTTP and NATS paths can reference. This unblocks safe NATS publisher wiring.
- [x] DONE — Backend publisher abstraction implements this contract's subject namespace and minimal payload shape
  - Files: `backend/internal/nats/publisher.go`, `backend/internal/nats/publisher_test.go`
  - Check: `cd backend && go test ./internal/nats/... -v` → 8/8 PASS (embedded JetStream server)
  - Evidence: `Subject(owner, kind, action)` produces the contract subjects (`bot.command.start`, `backtest.event.completed`, etc.); the `Envelope` carries the minimal payload fields (correlation id, actor/owner id, UTC `occurred_at`, schema version, reference-heavy payload); the publisher is fail-closed (`NATS_ENABLED=false` → nil) and connects lazily so HTTP control stays authoritative. Not yet wired behind a route.

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
  - DONE (first slice): `publisher.go` implements the fail-closed `Publisher`, `Envelope`, and `Subject`/`StreamFor` mapping for the contract namespace; `publisher_test.go` validates it end-to-end against an embedded JetStream server.
- `bot/src/infrastructure/nats/*` — PENDING (durable consumers)
- `backend/config/config.go` — already has `NATSSettings` (Phase 1); publisher reads `Enabled`/`URL`
- `bot/src/infrastructure/database.py` or service config only if NATS values are wired there later
- deployment manifests for JetStream, publisher, and subscriber wiring — PENDING
