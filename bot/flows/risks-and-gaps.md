# Risks and Gaps

## Prioritized findings

| Priority | Finding | Impact | Evidence | Required validation/remediation direction |
|---|---|---|---|---|
| Critical | Many backtest mutations/reads have no executable auth dependency although OpenAPI declares Bearer auth. | Untrusted callers may start, pause, cancel, restart, delete or inspect expensive/sensitive runs. | Backtest decorators/handler signatures in [`server.py`](../src/api/server.py); auth is dependency-based in [`auth_middleware.py`](../src/middleware/auth_middleware.py). | Confirm ingress enforcement immediately; add route-level/router-level auth if none exists. |
| Medium | WebSocket auth permits tokens in the `access_token` query string as well as the bearer header. | Query strings can be retained in proxy/access logs, exposing JWT or service-token material. | [`_authorize_websocket_connection`](../src/api/server.py). | Prefer header/subprotocol authentication where clients support it; redact query strings at every proxy/log layer. |
| High | API strategy CRUD is process-local despite durable strategy ORM tables. | Strategies disappear on restart and diverge across workers/replicas; backtests can resolve different snapshots. | [`InMemoryStrategyStore`](../src/api/server.py), [`Strategy`](../internal/domain/models.py). | Establish authoritative owner/store and migrate handlers or label facade explicitly. |
| High | Managed bot credentials/mnemonic are persisted in plain JSON fields in `bot_instances.config`. | DB readers/backups/logging mistakes can expose signing secrets. | create route and [`_runtime_contract_payload`](../src/bot_instance_manager.py); [`Bot.config`](../internal/domain/models.py). | Confirm application/DB encryption, access controls, key rotation, redaction and backup policy. |
| High | Realtime write service is not wired into any entrypoint; API reads realtime tables and sockets imply live updates. | Realtime endpoints may be empty/stale while appearing operational. | No caller found for [`start_realtime_service`](../src/trading/realtime_data_service.py); routes use realtime repositories. | Identify external starter or wire/supervise intentionally; expose freshness. |
| High | WebSocket registries/broadcasts, rate-limit fallback, runtime settings/metrics, manager handles and strategies are process-local. | Multiple Uvicorn workers or replicas yield nondeterministic control, auth throttling and event delivery. | [`ConnectionManager`](../src/api/websocket_server.py), API globals in [`server.py`](../src/api/server.py), `BOT_API_WORKERS`. | Enforce one API owner or add distributed ownership/fan-out/state. |
| High | Exit marks trade/position closed after close-order submission, without demonstrated fill confirmation. | DB/local state can say closed while exposure remains. | [`manage_trade_exits`](../src/trading/position_manager.py), [`persist_live_trade_closed`](../src/trading/trade_persistence.py). | Confirm fills/positions before closure; retain reconciliation state until flat. |
| High | Schema is shaped by `Base.metadata.create_all()` before Alembic, and realtime model/migration table names diverge. | Drift can be silently masked; environments may have parallel/unused tables and inconsistent constraints. | [`create_all_tables`](../src/infrastructure/database.py), [`models_realtime.py`](../internal/domain/models_realtime.py), migration `64bafb...`. | Compare clean migration-only vs startup-created schema; select canonical realtime schema. |
| High | Backtest Redis status pub-sub has a producer but no subscriber in this repository. | Cross-process progress push may be missing; clients rely on polling/stale DB. | [`_publish_backtest_status`](../src/infrastructure/workers/backtest_tasks.py); no subscribe call found. | Confirm external bridge or implement supervised subscriber/fan-out. |
| High | Live risk configuration contains `max_positions`, drawdown, stop-loss, take-profit, trailing-stop and timeout fields, but the traced live flow does not clearly enforce them. | Operators may believe controls exist when only fields/UI contracts exist. | [`TradingParameters`](../src/infrastructure/domain/bot_api_models.py), [`open_positions`, `manage_trade_exits`](../src/trading/position_manager.py). | Produce control-to-code matrix and test each claimed guard; mark unsupported fields. |
| Medium | Logout and logout-all are stubs; Redis token blacklist utilities are not wired. | Stolen JWTs remain valid until expiry; “logout all” is misleading. | [`logout`, `logout_all`](../src/api/v1/auth/__init__.py), [`TokenBlacklist`](../src/api/auth_utils.py). | Define revocation/refresh design and update contract. |
| Medium | 2FA is implemented but its router is not mounted; login does not enforce 2FA state. | Apparent security capability is unavailable and unenforced. | [`password_2fa.py`](../src/api/v1/auth/password_2fa.py), router includes in [`server.py`](../src/api/server.py). | Decide whether to complete or remove/document. |
| Medium | `backtests.aggregate_candles` is a compatibility stub returning `skipped`. | Operators may assume post-processing/cache acceleration that does not exist. | [`candle_aggregate_tasks.py`](../src/infrastructure/workers/candle_aggregate_tasks.py). | Rename/status surface or implement concrete aggregation. |
| Medium | DB/file dual writes for tracked positions and pairs are non-transactional and reads prefer any DB row. | A stale DB row can eclipse a newer recovery file; restart reconciliation can lose truth. | [`bot_agents_state.py`](../src/trading/bot_agents_state.py), [`cointegration_storage.py`](../src/infrastructure/domain/cointegration_storage.py). | Add versions/timestamps/conflict reconciliation and recovery runbook. |
| Medium | API startup migrations/recovery may execute concurrently on replicas. | Lock contention, duplicate recovery dispatch or inconsistent manager ownership. | [`lifespan`](../src/api/server.py); no leader lock found. | Validate deployment replica count; add migration/recovery leader election. |
| Medium | Synchronous DB and notification/log HTTP calls exist in async services. | Event-loop stalls and latency spikes under DB/network pressure. | sync SQLAlchemy throughout handlers; Telegram/Loki implementations. | Profile; move blocking I/O to threads/async clients or isolate processes. |
| Medium | CORS uses wildcard origins with credentials enabled. | Ambiguous/insecure browser posture and likely framework rejection of credentialed wildcard. | [`app.add_middleware`](../src/api/server.py). | Set explicit production origins and test browser behavior. |
| Medium | API bypass is forbidden only for environment string `production`; aliases such as `prod` are not rejected. | Misnamed production environment can disable all protected-route auth. | [`lifespan`](../src/api/server.py), [`get_current_user`](../src/middleware/auth_middleware.py). | Normalize production-like environment names and fail closed. |
| Medium | `src/api/server.py` and `service_backtest.py` are very large mixed-responsibility modules. | Changes have broad blast radius; route/domain/recovery behavior is hard to test independently. | 5,834 and 4,320 lines respectively. | Incrementally split routers, orchestration, domain simulation and adapters without contract changes. |
| Medium | Duplicate migration trees and duplicate realtime repositories lack an explicit ownership marker. | Fixes can land in inactive code; migration histories can drift. | [`migrations/versions`](../migrations/versions), [`migrations/mariadb`](../migrations/mariadb), two realtime repository modules. | Declare canonical paths; delete/archive only after usage validation. |
| Medium | Service-local Docker targets/manifests are incomplete and CI references parent/root files absent from this directory. | `make setup/dev/prod/build` or the Docker build job can fail when the expected monorepo files are unavailable; deployment provenance is unclear. | [`Makefile`](../Makefile), [`.github/workflows/ci.yml`](../.github/workflows/ci.yml); no local `docker/` or `Dockerfile`. | Validate from monorepo root, then remove or redirect stale service-local targets. Make Docker build depend on tests if that is the release gate. |
| Medium | CI ignores Black failures and the Docker build job depends on lint but not the test job. | Formatting regressions do not fail CI, and an image can build after tests fail. | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). | Decide intended gates; make required checks fail and add `test` to build dependencies. |
| Low | `high_priority` queue is configured but no current task routes there. | Operational noise/config complexity. | [`celery_app.py`](../src/infrastructure/workers/celery_app.py). | Validate planned use or remove from defaults. |
| Low | `system_metrics`, `daily_reports`, position-history snapshot flow and some diagnostics are placeholders/unused. | API/features may return empty data and increase maintenance surface. | initial migration; [`PositionSnapshotsRepository.get_position_history`](../src/infrastructure/persistence/repository_realtime.py). | Mark unsupported or implement end-to-end writers/readers. |

## Failure-mode gaps

### Exchange/local divergence

The strongest current protection is explicit one-leg cleanup and orphaned-exit recovery ([`bot_agent.py`](../src/trading/bot_agent.py), [`position_manager.py`](../src/trading/position_manager.py)). Remaining gaps are confirmed-fill closure, best-effort DB writes, and no demonstrated periodic full account reconciliation beyond tracked positions. If local and exchange state disagree in an unrecognized way, the worker raises and asks for manual intervention; that is fail-safe for new work but leaves exposure management to operators.

### Restart/recovery

Bot manager startup is DB-first and can verify an external persisted PID, mark missing workers error, or auto-restart under flags ([`bot_instance_manager.py`](../src/bot_instance_manager.py)). Tracked positions are independently DB/file-backed. A safe restart therefore requires all three sources—exchange, `bot_instances`, and tracked position state—to agree. No single reconciliation transaction spans them.

### Backtest recovery

Persist-before-dispatch and heartbeat/restart logic are strong. Risks remain around duplicate startup actors, Redis lock expiry, control latency during long external calls, and JSON-heavy row rewrites. Default fail-safe recovery limits accidental duplicate execution but sacrifices automatic continuation.

## Missing or incomplete flows

- No mounted 2FA or refresh-token route.
- No real logout/token revocation flow.
- No durable strategy CRUD in current API handlers.
- No implemented candle aggregation despite registered task.
- No confirmed realtime service startup or Redis backtest status subscriber.
- No position-history snapshot writer/read flow in current repository implementation.
- No clear live enforcement found for several configured risk limits.
- No explicit API audit event for auth/login/registration/admin Celery actions.
- No deployment/Beat manifests in the inspected directory.

## Manual validation plan

1. Security: enumerate routes from live OpenAPI and send unauthenticated requests to every HTTP/WebSocket mutation/read; compare with this document.
2. Data: apply Alembic to an empty MariaDB without app startup, capture schema, then start API and diff; inspect production `alembic current` and both realtime table families.
3. Safety: on testnet execute entry leg-2 failure, exit leg-2 failure, worker crash/restart and exchange/local mismatch scenarios; verify actual exposure and state.
4. Distribution: run two API workers/replicas and validate bot ownership, strategy CRUD, rate limiting, `/ws/strategies`, bot sockets and backtest progress.
5. Jobs: run worker loss/redelivery, lock-expiry, pause during history fetch, broker outage, Beat sync and stale recovery tests.

## Rollback/operational notes

This package changes no runtime behavior. For future fixes, preserve the current response aliases and DB-first bot configuration. Security fixes may intentionally break unauthenticated callers; coordinate the backend before enforcement. Schema consolidation requires a data inventory and reversible migration rather than dropping either realtime table family blindly.

## Overall assessment

The repository has meaningful safety mechanisms—process isolation, DB-first managed config, paired cleanup, reduce-only recovery, persist-before-dispatch, heartbeat/recovery and operator logs. The primary architectural weaknesses are contract/auth mismatch, process-local control-plane state, ambiguous realtime/schema ownership, and configured capabilities that are incomplete or not wired. These are production correctness issues, not merely code-style concerns.
