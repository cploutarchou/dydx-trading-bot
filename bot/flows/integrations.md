# External Integrations

## Inventory

| Integration            | Purpose                                                     | Protocol/client                     | Configuration                                             | Failure behavior                                                       | Evidence                                                                                                           |
|------------------------|-------------------------------------------------------------|-------------------------------------|-----------------------------------------------------------|------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| dYdX v4 Indexer        | markets, candles, accounts, positions, orders/fills         | `dydx-v4-client` async Indexer APIs | network, Indexer URLs, address/subaccount                 | rate limit/circuit handling, stale cache where implemented, retry/fail | [`dydx_client.py`](../src/trading/dydx_client.py), [`market_data.py`](../src/trading/market_data.py)               |
| dYdX v4 Node           | signed order placement/cancel/close                         | `dydx-v4-client` Node/Wallet        | node URL, mnemonic/address, chain/network                 | paired emergency cleanup; critical alert on orphan                     | [`connect_dydx_runtime`](../src/trading/dydx_client.py), [`account_manager.py`](../src/trading/account_manager.py) |
| PostgreSQL             | primary persistence and auth                                | SQLAlchemy/psycopg2/Alembic         | shared/dedicated cutover env                              | API startup fatal; some runtime writes degrade to file/best effort     | [`DatabaseConfig`](../src/infrastructure/database.py)                                                              |
| Valkey / Redis         | Celery, caches, locks, pub-sub, rate limits                 | redis-py/Celery                     | `CELERY_*`, `REDIS_URL`, `VALKEY_*`, `REDIS_*`            | endpoint-specific fallback; Celery enqueue fails without broker        | [`celery_app.py`](../src/infrastructure/workers/celery_app.py)                                                     |
| NATS JetStream         | command/event transport contract                            | NATS clients when enabled           | `NATS_URL`, `NATS_MONITORING_URL`                         | currently configuration-first; runtime use is feature-gated            | `deploy/k8s-next/platform-config.yaml`, `docker-compose.stack.yml`                                                 |
| ClickHouse             | analytical backtest storage                                 | HTTP client                         | `CLICKHOUSE_URL`, `CLICKHOUSE_*`, `BACKTEST_CLICKHOUSE_*` | disabled/feature-gated paths fall back to no-op analytics              | [`repository_backtest.py`](../src/infrastructure/persistence/repository_backtest.py)                               |
| MinIO / S3             | artifact and large backtest output storage                  | MinIO SDK / S3-compatible client    | `MINIO_ENDPOINT`, `MINIO_*`, `S3_*`, `BACKTEST_MINIO_*`   | falls back to local artifact store when disabled/unavailable           | [`repository_backtest.py`](../src/infrastructure/persistence/repository_backtest.py)                               |
| Telegram Bot API       | lifecycle, account, trade, recovery and error notifications | HTTPS requests                      | token/chat ID, retries/dedupe                             | disabled when unconfigured; send failures return false/log             | [`TelegramMessenger`](../src/shared/notifications.py)                                                              |
| Grafana Loki           | optional centralized logs                                   | synchronous HTTP push               | URL/credentials/tenant/labels                             | skipped when disabled/misconfigured; failed sends swallowed            | [`logging_setup.py`](../src/shared/logging_setup.py)                                                               |
| HTTP/WebSocket callers | backend/dashboard/operator control and streaming            | FastAPI/Uvicorn WebSocket           | bearer JWT/service token                                  | route-specific auth and standard/error envelopes                       | [`src/api/server.py`](../src/api/server.py)                                                                        |

## Configuration and authentication matrix

| Integration     | Visible configuration variables                                                                                                                                                                                    | Authentication/identity                                                                                    |
|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------|
| dYdX            | `IS_TESTNET`, `DYDX_TESTNET_ADDRESS`, `DYDX_TESTNET_MNEMONIC`, `DYDX_TESTNET_NODE_URL`, mainnet equivalents/structured credential fields, `BOT_SUBACCOUNT_NUMBER`, rate/circuit/cache settings                     | Mnemonic-derived wallet for Node writes; address/subaccount for Indexer account reads; public market reads |
| PostgreSQL      | `BOT_DB_CUTOVER_MODE`, `BOT_DATABASE_URL`, `DATABASE_URL`, `BOT_DB_*`, `DB_*`, pool/timeouts, `SSL_MODE`                                                                                                           | Database username/password in URL or fields; TLS enforcement is **NEEDS VALIDATION**                       |
| Valkey/Celery   | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `REDIS_URL`, `VALKEY_URL`, `REDIS_HOST`, `REDIS_PORT`, `VALKEY_HOST`, `VALKEY_PORT`, `REDIS_DB`, `REDIS_PASSWORD`, `REDIS_SSL`, queue/task-limit/retry/lock settings | Redis-compatible URL/password; TLS when `rediss`/`REDIS_SSL` is used                                       |
| NATS            | `NATS_URL`, `NATS_MONITORING_URL`, stream/feature flags                                                                                                                                                            | server URL only; credentials/tokens are not yet active in checked-in runtime paths                         |
| ClickHouse      | `CLICKHOUSE_URL`, `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_DATABASE`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `BACKTEST_CLICKHOUSE_*`                                                                   | optional username/password; HTTP endpoint on port `8123`                                                   |
| MinIO / S3      | `MINIO_ENDPOINT`, `MINIO_CONSOLE_URL`, `MINIO_BUCKET`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `S3_ENDPOINT`, `S3_REGION`, `S3_FORCE_PATH_STYLE`, `BACKTEST_MINIO_*`                                               | access key / secret key; path-style S3 access for local MinIO                                              |
| Telegram        | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, retry/dedupe/category settings or per-instance DB config                                                                                                                 | Bot token in HTTPS API path; target chat ID                                                                |
| Loki            | `LOKI_ENABLED`, `LOKI_URL`, `LOKI_USERNAME`, `LOKI_PASSWORD`, `LOKI_TENANT_ID`, `LOKI_LABELS`                                                                                                                      | Optional HTTP basic auth and tenant header                                                                 |
| Bot API callers | `BOT_API_TOKEN`, `BOT_API_TOKEN_PREVIOUS`, `BOT_API_TOKENS`, JWT secret/expiry settings, `API_BYPASS_AUTH`, CORS/runtime host/port settings                                                                        | Rotating constant-time service-token match or user JWT; WebSockets also accept query token                 |

## dYdX flows

### Client selection

[`connect_dydx`](../src/trading/dydx_client.py) builds a market-data client from shared runtime network configuration; [
`connect_dydx_runtime`](../src/trading/dydx_client.py) accepts per-instance credentials for managed live trading.
`_sanitize_node_url` strips schemes expected not to be present by the client. Placeholder credential checks prevent a
signing wallet when values are empty/template-like; exact read-only behavior should be validated against client version
`1.1.6` in [`requirements.txt`](../requirements.txt).

### Read flows

- Market listing: public API and market sync call `indexer.markets.get_perpetual_markets`.
- Recent candles: live entry/exit calls [`get_candles_recent`](../src/trading/market_data.py), which applies throttling,
  circuit breaking and Redis cache.
- Historical candles: backtest service calls its `_fetch_market_history` path with deadlines/retry summaries.
- Account/orders/positions/fills: [`account_manager.py`](../src/trading/account_manager.py) wraps Indexer calls and
  normalizes payloads.

### Write flows

[`place_market_order`](../src/trading/account_manager.py) submits signed orders. Entry uses two non-reduce-only legs;
emergency and exit operations use reduce-only orders. The application’s atomicity is compensating, not transactional:
the exchange cannot commit both legs together ([`BotAgent.open_trades`](../src/trading/bot_agent.py)).

### Integration risks

- Payload field/status assumptions are coupled to the client/Indexer response shapes.
- Market data can be cached/stale; live order/account truth is fetched directly.
- Exit persistence occurs after submission rather than confirmed fill.
- Network/rate-limit resilience differs between live and backtest paths.

## PostgreSQL flows

[`DatabaseConfig`](../src/infrastructure/database.py) supports `shared`, `dedicated`, and
`dedicated_with_shared_fallback`. Dedicated mode rejects a target identical to configured shared DB. PostgreSQL URLs are
required. The global manager uses a synchronous `QueuePool`, so database calls inside async handlers/workers can block
their event loops.

Startup performs health check, metadata `create_all`, compatibility SQL, Alembic upgrade and required-table checks. Pool
settings and sanitized target are logged. Runtime code uses ORM repositories plus raw SQL for tracked positions/pairs
and compatibility recovery.

**NEEDS VALIDATION:** TLS is represented by `SSL_MODE` diagnostics but [
`get_engine_kwargs`](../src/infrastructure/database.py) does not visibly add SSL connection parameters; verify transport
encryption in the deployed URL/driver configuration.

## Valkey and Celery flows

Redis-compatible URL precedence differs slightly by module but generally prefers `CELERY_BROKER_URL`, then `REDIS_URL` /
`VALKEY_URL`, then host/port defaults. Celery result backend defaults to a separate DB index. Rate limiting fails open
to an in-process limit, market cache misses fall back to live calls, and token blacklist initialization fails closed
only inside that unused helper. Backtest ownership uses Valkey/Redis; if lock acquisition cannot initialize the cache
client, inspect [`_acquire_backtest_lock`](../src/infrastructure/workers/backtest_tasks.py) before assuming safe
degradation.

No code was found that subscribes to Celery’s backtest Valkey/Redis status channel. Current WebSocket reliability
therefore depends on DB polling/in-process broadcasts, not proven cross-process pub-sub delivery.

## Telegram flows

`TelegramMessenger` formats HTML messages, retries blocking requests through its request wrapper, deduplicates error
categories in process memory and returns false when disabled/failing ([
`notifications.py`](../src/shared/notifications.py)). It is called from API lifecycle routes, managed-worker
startup/setup, market circuit handling, entries/exits and emergency recovery.

Notification delivery is not durable. A worker/API restart clears dedupe state; failures do not enqueue a retry job.
This is appropriate as a secondary alert, not a source of truth.

## Loki flows

Loguru bridges standard logs, emits console output, and optionally invokes a synchronous `requests.post` for every log
record through an enqueued Loguru sink ([`send_to_loki_directly`](../src/shared/logging_setup.py)). Production without
Loki credentials skips the sink. Delivery failure is only debug-logged and no buffering/dead-letter storage exists.

## Caller/backend contract

The parent workspace instructions describe `frontend → Go backend → Python bot API`, but this repository contains only
the Python endpoint, service-token support and normalized aliases. That topology is contextual, not independently
provable from bot source. The bot API accepts both JWT and rotating service tokens on protected dependencies. **NEEDS
VALIDATION:** which routes the backend actually calls, whether it authenticates backtest and WebSocket endpoints, and
how trace IDs propagate across services.

## Validation checklist

- Testnet: market list, account read, one safe paired order/cleanup path.
- PostgreSQL: `alembic current`, required-table verification, dedicated cutover guardrail and TLS inspection.
- Valkey: broker/result ping, duplicate backtest lock, candle key TTL and failure fallback.
- Telegram/Loki: non-production test message/log with secret redaction.
- WebSocket: authenticated/unauthenticated matrix for all five paths and multi-API-worker delivery.
