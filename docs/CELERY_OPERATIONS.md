# Celery Operations

Celery is the durable background execution path for long-running bot work, especially backtests. The app boundary stays unchanged: frontend calls the Go backend, the backend enforces auth/admin checks, and the backend delegates to the Python bot API.

## Architecture

- Celery app: `bot/src/infrastructure/workers/celery_app.py`
- Celery app import path: `src.infrastructure.workers.celery_app:celery_app`
- Task module: `bot/src/infrastructure/workers/backtest_tasks.py`
- Current task name: `backtests.run`
- Default queue: `celery` via `CELERY_QUEUES`
- Broker: `CELERY_BROKER_URL` or Redis from `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
- Result backend: `CELERY_RESULT_BACKEND` or Redis DB offset `REDIS_DB + 1`
- Worker entrypoint: `bot/worker_entrypoint.py` with `WORKER_MODE=celery-backtest`

Backtest runs persist `worker_backend=celery` and `worker_task_id=<celery task id>` on the app-level backtest record. The monitoring API combines Celery inspect/result-backend data with persisted backtest rows so task IDs, progress, errors, and app-level run status stay linked.

Flower is the primary optional operator UI for Celery internals. The app-level APIs remain required because they provide sanitized, business-aware task status linked to backtest, strategy, and bot records.

## Admin APIs

All Celery endpoints are admin-only. Normal and anonymous users must receive `401` or `403`.

- `GET /api/v1/celery/tasks`
- `GET /api/v1/celery/tasks/{task_id}`
- `POST /api/v1/celery/tasks/{task_id}/revoke`
- `POST /api/v1/celery/tasks/{task_id}/retry`
- `GET /api/v1/celery/workers`
- `GET /api/v1/celery/queues`
- `GET /api/v1/celery/health`

The frontend admin page is `/admin/celery` in the backoffice portal only. Do not add Celery controls to the client portal.

## Security Notes

- Backend admin authorization is required before delegation to the bot API.
- Bot Celery endpoints also require `get_admin_user`.
- Task payloads are recursively redacted for sensitive keys such as passwords, tokens, secrets, API keys, private keys, broker URLs, and DSNs.
- Tracebacks are returned only through admin-only endpoints and UI.
- Flower is an internal/admin tool. Do not expose Flower publicly without VPN, firewall, and basic auth.
- Flower `/healthcheck` and `/metrics` behavior can differ from the main UI auth flow. If Flower is reachable through any shared network or reverse proxy, protect those paths at the network/proxy layer too.
- Celery tasks should pass IDs/references, not secrets. Current backtest tasks pass only `run_id` and load trusted data inside the worker process.

## Local Commands

```bash
make celery-worker
make celery-health
make celery-inspect
make celery-revoke TASK_ID=<task-id>
make celery-revoke TASK_ID=<task-id> TERMINATE=true
make celery-purge
```

Flower:

```bash
FLOWER_BASIC_AUTH='admin:change-me' make celery-flower
```

Then open `http://localhost:5555` from a trusted local/admin network only.

Direct command:

```bash
cd bot
.venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app flower --port="${FLOWER_PORT:-5555}" --basic_auth="${FLOWER_BASIC_AUTH}"
```

`FLOWER_BASIC_AUTH` is required by `scripts/celery-flower.sh`; the script exits before startup if it is missing. Set `VITE_FLOWER_URL` only for backoffice/admin builds when you want the `/admin/celery` page to show an external Flower link.

## Docker Compose

No active Docker Compose file for this stack is present in the repository at this time. The root Makefile references historical compose filenames, but those files are not available in the current checkout, so no Flower compose service was added. If compose is restored, add Flower as an opt-in local profile with:

- `127.0.0.1:${FLOWER_PORT:-5555}:5555` port binding for dev
- the same `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, or Redis env vars used by the worker
- required `FLOWER_BASIC_AUTH`
- no public production exposure by default

## Troubleshooting

- If `GET /api/v1/celery/health` reports broker failure, verify Redis host, port, password, SSL mode, and DB number.
- If workers are missing, run `make celery-health` and confirm `WORKER_MODE=celery-backtest` in container deployments.
- If Flower shows no task events, confirm workers are running with task events enabled. The Celery app enables `worker_send_task_events` and `task_send_sent_event`.
- If results are missing, verify `CELERY_RESULT_BACKEND` or Redis DB `REDIS_DB + 1`.
- If Flower refuses to start, set `FLOWER_BASIC_AUTH`.
- If a backtest is stuck, inspect `/admin/celery`, then compare `worker_task_id` with the backtest run status page.
- Prefer `revoke` first. Use `TERMINATE=true` only for admin/debug intervention when the task will not exit cooperatively.
- Retrying is intentionally limited to failed `backtests.run` tasks with persisted request payloads.
