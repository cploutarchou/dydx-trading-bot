---
name: multi-worker-broadcast-test
description: Run and extend the dYdX bot's multi-worker integration test for the cross-worker WebSocket broadcast bus. Use whenever the user mentions multi-worker tests, cross-worker websocket fan-out, WS_BROADCAST_ENABLED, the broadcast bus (src/infrastructure/broadcast/), split websocket registries, broadcast-bus Phase 2, "test-multiworker", or wants to verify websocket broadcasts reach clients on other uvicorn workers.
---

# Multi-worker broadcast-bus test

`tests/test_multi_worker_broadcast.py` is the only test that exercises the real
cross-worker topology: two API worker processes, one Redis/Valkey, one ephemeral
PostgreSQL, `WS_BROADCAST_ENABLED=true`. It is **opt-in** — it skips unless
`MULTIWORKER_TEST=1` is set — because the app lifespan fail-safes without a live
Postgres (SQLite is not a supported dialect).

## Running it

```bash
cd bot
make test-multiworker        # starts shared infra (make -C .. infra-up), then runs the suite
# or manually:
docker compose -f ../docker-compose.infra.yml up -d postgresql valkey
MULTIWORKER_TEST=1 .venv/bin/python -m pytest tests/test_multi_worker_broadcast.py -s -vv
```

Docker Desktop must be running. The harness auto-skips with actionable messages
when Redis or Postgres is unreachable — read the skip reason, don't "fix" the test.

## What it asserts (and why each matters)

1. Both workers report a healthy, listening bus with **distinct `worker_id`**s —
   distinct identities are what make origin-tagged self-suppression work.
2. The headline property: a publish on worker A reaches a WebSocket client on
   worker B **exactly once**, the local client on A gets one copy, both
   directions work, and a quiet window proves no loop-back echo.
3. Health now includes `subscribed` (the *actual* subscription state) — a
   running listener task can briefly be between subscriptions.

## Invariants to preserve when editing

- The bus subscriber must use a **dedicated connection with `socket_timeout=None`**.
  Inheriting the command timeout (1 s) makes idle `listen()` raise every second,
  flapping the subscription and silently dropping messages while `health()` still
  says healthy — this was a real Phase-1 bug this harness caught
  (`src/infrastructure/broadcast/bus.py`, `_ensure_listener_client`).
- Workers boot **staggered** (A migrates the empty ephemeral schema; B joins after
  A is `/ready`) or the two Alembic migrations race on the fresh database.
- The ephemeral DB is `dydx_bot_mwtest_<pid>` on the local compose Postgres; it is
  dropped (`WITH (FORCE)`) on teardown. Set `MULTIWORKER_DATABASE_URL` to point
  workers at your own scratch DB instead (never the dev DB — workers run
  migrations against it).
- Workers launch via `src.api/start_api.py` with `APP_RUN_CONFIG_FILE` pointing at
  a metadata-only profile + `APP_CONFIG_PRESERVE_PROCESS_ENV=1`, so repo profile
  values cannot leak into the test configuration.
- The trigger is `POST /api/v1/monitoring/ws-broadcast/publish` (auth required;
  validated channel; fixed server-built `broadcast_test` payload; returns a
  correlatable `test_id`). Don't add payload injection to it.

## Known sharp edge

On a database built purely by Alembic migrations, Postgres enums reject the ORM's
labels (`positionstatusenum` vs `'OPEN'`, `jobstatusenum` vs `'PENDING'`), so
bot-channel websocket `initial_state` queries fail. That's why the harness uses a
`backtest-*` channel (its initial frame avoids the positions query). Fixing the
enum drift belongs to the migration-safety process, not this test.

## When touching the bus in production code

Run, in order: `tests/test_broadcast_bus.py` (unit, always),
`tests/test_monitoring_routes.py` (endpoint contract), then this harness (listener
or publish-path changes). Unit fakes cannot catch socket-level timeout bugs —
that is the point of the harness.
