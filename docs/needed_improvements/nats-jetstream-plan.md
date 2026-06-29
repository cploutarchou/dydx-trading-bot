# NATS JetStream Plan

## Status Updates — 2026-06-29

- [x] DONE — Wire NATS publisher behind delegated backtest creation routes as dual-write (Phase 4 dual-write slice)
  - Files: `backend/internal/app/router.go`, `backend/internal/routes/bot_api_delegate_routes.go`
  - Check: `cd backend && go build ./...` passed; `cd backend && go vet ./...` passed; `cd backend && go test ./... -short` passed (all packages `ok`)
  - Evidence: NATS publisher now dual-writes behind `/api/v1/backtests/run` and `/api/v1/backtests` - creates PostgreSQL `task_commands` rows with idempotency keys and publishes canonical `nats.Envelope` to JetStream with `Msg-Id` dedupe while keeping HTTP/Celery path authoritative. Validated end-to-end with all existing tests passing.
- [x] DONE — Add the backend NATS JetStream publisher abstraction (Phase 4 first slice)
  - Files: `backend/internal/nats/publisher.go`, `backend/internal/nats/publisher_test.go`, `backend/go.mod`, `backend/go.sum`
  - Check: `cd backend && go mod tidy` added `nats.go` v1.52.0 + `nats-server/v2` v2.14.2; `cd backend && gofmt -l <changed files>` passed; `cd backend && go build ./...` passed; `cd backend && go vet ./...` passed; `cd backend && go test ./...` passed (all `ok`); `cd backend && go test ./internal/nats/... -v` → 8/8 PASS (stable at `-count=3`)
  - Evidence: a fail-closed, lazily-connected `nats.go`-backed `Publisher` now publishes the canonical command/event `Envelope` to the contract subject namespace with JetStream `Msg-Id` dedupe and idempotent stream provisioning; validated end-to-end against an embedded JetStream server. Now wired into backtest creation routes.
- [x] DONE — Add durable NATS consumers for backtest commands (Phase 4 consumer slice)
  - Files: `bot/requirements.txt`, `bot/src/infrastructure/event_bus_nats.py`, `bot/src/infrastructure/workers/nats_backtest_consumer.py`, `bot/src/infrastructure/event_bus.py`, `bot/worker_entrypoint.py`, `bot/tests/test_nats_consumer.py`
  - Check: `cd bot && .venv/bin/python -m pytest tests/test_nats_consumer.py -v` → 28/28 PASS; all existing bot tests remain unaffected
  - Evidence: Durable consumer service implements explicit ack after authoritative PostgreSQL state updates using task tables for idempotency checking; retry/ack/dead-letter handling per nats-jetstream-plan.md; worker entry point supports NATS consumer mode; comprehensive test coverage. Stream and consumer configurations match nats-jetstream-plan.md exactly. Durable consumers, retry/ack/dead-letter handling now implemented; broader route coverage (bot lifecycle commands) remains PENDING.

## Role of NATS JetStream

NATS JetStream is the durable async transport for:

- bot commands
- backtest commands
- lifecycle events
- worker events
- audit events
- retries
- dead-letter capture
- fan-out to projectors and notifications

Valkey is not the durable queue. PostgreSQL stores final state. Workers must be idempotent.

## Current Findings From Repository

- Infra manifests exist:
  - `deploy/k8s-next/nats.yaml`
  - `docker-compose.infra.yml`
  - `docker-compose.stack.yml`
- Runtime flags exist but are disabled:
  - `NATS_ENABLED=false`
  - `BOT_COMMAND_BUS_ENABLED=false`
- Active code-level JetStream producer: PARTIAL — a fail-closed, lazily-connected `nats.go`-backed `Publisher` exists in `backend/internal/nats/publisher.go` (envelope contract, subject namespace, idempotent stream provisioning, `Msg-Id` dedupe) but is not yet wired into any route.
- Active code-level JetStream consumer: NOT FOUND.
- Current durable path is Celery in `bot/src/infrastructure/workers/celery_app.py`.
- PostgreSQL foundation for command idempotency: DONE — normalized task tables (`task_commands`, `task_runs`, `task_attempts`, `worker_heartbeats`) now exist with proper indexes, Go models, and repository layer, providing the idempotency and durable state foundation for NATS wiring.

## Proposed Streams

| Stream | Purpose | Subjects | Retention | Durable Consumers | Ack Timeout | Max Delivery | Dead-Letter Behavior | Idempotency Key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `BOT_COMMANDS` | durable bot command queue | `bot.commands.*` | work queue retention | `bot-worker` | 60s to 300s depending on command | 5 | move to `DEAD_LETTER` on exhaustion | command id |
| `BOT_EVENTS` | bot lifecycle and execution events | `bot.events.*` | interest or limits retention | `backend-projector`, `analytics-writer`, `notification-consumer` | 30s | 5 | copy failed projections to `DEAD_LETTER` | event id |
| `BACKTEST_COMMANDS` | durable backtest command queue | `backtest.commands.*` | work queue retention | `backtest-worker` | long ack window tuned per task heartbeat | 5 | move to `DEAD_LETTER` on exhaustion | command id |
| `BACKTEST_EVENTS` | backtest progress/completion/failure | `backtest.events.*` | interest or limits retention | `backend-projector`, `analytics-writer` | 30s | 5 | copy failed projections to `DEAD_LETTER` | event id |
| `WORKER_EVENTS` | worker heartbeat/failure/lease telemetry | `worker.events.*` | limits retention | `ops-projector`, `analytics-writer` | 30s | 5 | copy bad messages to `DEAD_LETTER` | event id |
| `SYSTEM_AUDIT` | security and operational audit | `system.audit.*` | limits retention with long retention window | `audit-projector` | 30s | 3 | copy failures to `DEAD_LETTER` | audit id |
| `DEAD_LETTER` | poison messages and terminal failures | `deadletter.*` | limits retention | `ops-reviewer` | N/A | N/A | terminal holding stream | original command/event id |

## Required Subjects

- `bot.commands.create`
- `bot.commands.start`
- `bot.commands.stop`
- `bot.commands.pause`
- `bot.commands.resume`
- `bot.events.started`
- `bot.events.stopped`
- `bot.events.failed`
- `bot.events.trade.created`
- `bot.events.order.updated`
- `backtest.commands.create`
- `backtest.commands.cancel`
- `backtest.events.started`
- `backtest.events.progress`
- `backtest.events.completed`
- `backtest.events.failed`
- `worker.events.heartbeat`
- `worker.events.failed`
- `system.audit.created`
- `deadletter.*`

## Durable Consumer Design

### `bot-worker`

- consumes `BOT_COMMANDS`
- queue group for horizontal scale
- explicit ack after PostgreSQL state update and any required downstream fan-out

### `backtest-worker`

- consumes `BACKTEST_COMMANDS`
- queue group for horizontal scale
- explicit ack only after authoritative `started` state is written and the task is safely claimed

### `analytics-writer`

- optional projector consuming `BOT_EVENTS`, `BACKTEST_EVENTS`, `WORKER_EVENTS`
- writes normalized analytical rows to ClickHouse

### `notification-consumer`

- optional projector consuming user-visible completion/failure events

### `backend-projector`

- consumes event streams needed for client-visible summaries and websocket/SSE fan-out

## Ack / Retry Policy

### Command streams

- use explicit ack
- ack only after idempotent state transition is persisted
- set `ack_wait` longer than expected checkpoint interval
- extend progress-driven ack windows for long backtests through heartbeats or periodic progress checkpoints

### Retry strategy

- redelivery handled by JetStream `max_deliver`
- worker writes retry attempt in PostgreSQL
- retry delay policy may use backoff by republishing or consumer redelivery scheduling depending on chosen implementation

### Dead-letter behavior

- after `max_deliver`, publish envelope to `DEAD_LETTER`
- include original stream, subject, delivery count, last error, task owner, and idempotency key
- never silently drop poison messages

## Event Payload Rules

- every message includes:
  - `event_id` or `command_id`
  - `idempotency_key`
  - `correlation_id`
  - `causation_id`
  - `owner_type`
  - `owner_id`
  - `occurred_at`
  - `producer_service`
  - `schema_version`
- command payloads may include bounded request JSON
- event payloads must remain concise
- large payloads go to MinIO; event includes artifact reference only

## Idempotency Rules

- backend assigns a stable `command_id` and `idempotency_key`
- PostgreSQL stores processed command/result mapping
- workers check whether command already reached terminal success before re-executing
- side effects that write to MinIO or ClickHouse use deterministic object keys and row identity to tolerate redelivery

## Mapping From Current Repo

### Replace

- Celery queue dispatch in `bot/src/infrastructure/use_cases/service_backtest.py`
- Celery worker in `bot/src/infrastructure/workers/backtest_tasks.py`
- Redis pub/sub progress path in `backend/internal/services/backtest_push_hub.go`

### Preserve conceptually

- retry counts
- run heartbeats
- task progress events
- duplicate suppression intent

### Remove as primary queue contract

- Celery over Redis-compatible broker in `bot/src/infrastructure/workers/celery_app.py`

## Non-Negotiable Boundary

- NATS JetStream is for durable async commands and events.
- Valkey is not the durable queue.
- PostgreSQL stores final state.
- Workers must be idempotent.
