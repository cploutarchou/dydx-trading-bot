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
4. **Burst/load scenario** (`test_burst_publish_cross_worker_delivery_under_load`,
   added 2026-08-16): a rapid burst (default 150 messages across 3 channels,
   round-robin) where each channel has ONE publisher worker but channels
   alternate between A and B — so both cross-worker directions carry load
   while per-channel Redis ordering stays deterministic. One WebSocket client
   per channel per worker must receive exactly its channel's messages, in
   publish order, with no foreign frames; a quiet window proves no
   duplicates/echoes; and the bus metrics deltas must show the expected
   `published` counts with **zero** `publish_errors`/`decode_errors`/
   `dispatch_errors`/`dispatch_timeouts` and **zero `reconnects`** (a listener
   flap silently drops messages — the bug class this harness already caught
   once).

## Burst scenario knobs (flakiness triage without code changes)

- `MULTIWORKER_BURST_MESSAGES` — total messages (default 150; `0` skips the
  scenario entirely).
- `MULTIWORKER_BURST_CHANNELS` — channels to spread the burst over (default 3).

## CI status

The suite runs in the `bot-multiworker` job of `.github/workflows/bot-quality.yml`
(Postgres 15.18 + Valkey 7.2 service containers). Promoted to a **blocking
quality gate 2026-08-16**. Gotcha learned during promotion: with
`continue-on-error`, the JOB conclusion reads `success` even when the pytest
step fails — always read the step logs, not the job conclusion, when judging
phase-1-style non-blocking jobs. The job writes a hermetic
`APP_RUN_CONFIG_FILE` (`.ci-run.json`, mirroring `bot-tests`) because pytest's
`load_repo_env` otherwise tries to decrypt `config/profiles/*.config.enc.json`
and fails on the missing `.configkey.bin`. If it flakes on a shared runner,
shrink `MULTIWORKER_BURST_MESSAGES` in the job env to triage; don't un-promote
the job.

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

## Known sharp edge (resolved)

On a database built purely by Alembic migrations, Postgres enums used to reject
the ORM's labels (`positionstatusenum` vs `'OPEN'`, `jobstatusenum` vs
`'PENDING'`), which is why the harness uses a `backtest-*` channel (its initial
frame avoids the positions query). This was fixed by migration
`0006_reconcile_enum_labels` (expand-only NAME-label addition + row flip);
legacy `create_all_tables` databases are no-ops. Bot-channel websockets now
work on fresh databases too, but the harness keeps the backtest channel to stay
DB-light.

## When touching the bus in production code

Run, in order: `tests/test_broadcast_bus.py` (unit, always),
`tests/test_monitoring_routes.py` (endpoint contract), then this harness (listener
or publish-path changes). Unit fakes cannot catch socket-level timeout bugs —
that is the point of the harness.
