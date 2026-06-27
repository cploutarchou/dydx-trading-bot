# Data Storage Matrix

| Data Type | Producer Service | Consumer Service | Target Storage | Retention | Query Pattern | Reason | Migration Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| user account | backend API | backend API, frontend | PostgreSQL | long-lived | point lookup, auth joins | transactional identity data | keep in PostgreSQL |
| bot config | backend API, bot API | bot API, bot workers, backend API | PostgreSQL | long-lived | point lookup by bot id | authoritative configuration | migrate oversized TEXT/JSON fields in `backend/migrations/postgres/000022_create_bot_instances.up.sql` to bounded config storage |
| strategy config | backend API | backend API, bot API, backtest workers | PostgreSQL | long-lived | point lookup, version lookup | transactional configuration | keep snapshots bounded; large research artifacts move to MinIO |
| task status | backend API, bot workers, backtest workers | backend API, frontend | PostgreSQL | 90 to 365 days | point lookup, status list | authoritative lifecycle state | replace Celery-only task state with normalized task tables |
| task progress | backtest workers, bot workers | backend API, frontend | PostgreSQL | active + short history | point lookup, recent updates | authoritative progress for UI | stop relying on Redis pub/sub as only progress signal |
| task retry count | workers | backend API, ops | PostgreSQL | task lifetime + audit window | point lookup | authoritative retry audit | persist independently of Celery retry memory |
| worker heartbeat | bot workers, backtest workers | backend API, ops | PostgreSQL + Valkey lease | 7 to 30 days in PostgreSQL, minutes in Valkey | recent heartbeat lookup | durable liveness plus fast lease checks | current heartbeat concepts in `service_backtest.py` should map here |
| task command | backend API | workers, audit | PostgreSQL + NATS JetStream | 30 to 180 days | command lookup, replay audit | immutable intent + durable dispatch | backend must publish to JetStream; current publisher NOT FOUND |
| task event | workers, backend projectors | backend API, ops, analytics | NATS JetStream + ClickHouse projector | 30 to 180 days | time-series and state projection | durable event stream + analytics | replace Redis pub/sub status events |
| bot command | backend API | bot workers, bot runtime | PostgreSQL + NATS JetStream | 30 to 180 days | lookup by bot/run/idempotency | durable command execution | current bot command bus implementation NOT FOUND |
| bot event | bot runtime, bot workers | backend API, frontend, analytics | NATS JetStream + ClickHouse | 90 to 180 days | event timeline, aggregates | fan-out + analytics | current structured bot event bus NOT FOUND |
| bot active lock | bot workers/runtime | bot workers/runtime | Valkey | minutes | point lookup by bot id | short-lived coordination | replace file/process-local ownership assumptions |
| API rate limit counter | backend API, bot API | backend API, bot API | Valkey | seconds to minutes | counter increment | distributed rate limiting | replace `backend/internal/middleware/rate_limit.go` in-process limiter |
| cache entry | backend API, bot API | backend API, bot API | Valkey | seconds to minutes | key lookup | fast cache, not source of truth | keep TTL-bound |
| trade event | bot workers | backend API, analytics | ClickHouse | 180 to 365 days | time-series, aggregates | high-volume analytical row | current target path largely NOT FOUND outside backtests |
| order event | bot workers | backend API, analytics | ClickHouse | 180 to 365 days | time-series, aggregates | high-volume analytical row | implement alongside trade events |
| fill event | bot workers | backend API, analytics | ClickHouse | 180 to 365 days | time-series, aggregates | high-volume analytical row | implement alongside trade events |
| position snapshot | bot workers | backend API, analytics | ClickHouse | 90 to 180 days | latest + trend queries | append-friendly state history | migrate away from JSON/file snapshot paths |
| bot execution metric | bot runtime, bot workers | ops, backend API | ClickHouse | 90 to 180 days | aggregate dashboards | high-cardinality metrics | current durable storage NOT FOUND |
| raw exchange request | bot runtime, bot workers | ops, debug workflows | MinIO | 14 to 30 days | fetch by run/task/time | bulky payload, low-frequency retrieval | never store in PostgreSQL JSON/TEXT |
| raw exchange response | bot runtime, bot workers | ops, debug workflows | MinIO | 14 to 30 days | fetch by run/task/time | bulky payload, low-frequency retrieval | never store in PostgreSQL JSON/TEXT |
| backtest run metadata | backend API, bot API, backtest workers | backend API, frontend | PostgreSQL | 180 to 365 days | point lookup, recent list | transactional run ownership and summary | current rows stay, but large JSON columns must be removed |
| backtest progress | backtest workers | backend API, frontend | PostgreSQL + NATS JetStream event | task lifetime + short history | point lookup + live updates | authoritative progress plus push fan-out | current Redis pub/sub path becomes JetStream event + backend projection |
| backtest summary metrics | backtest workers | backend API, frontend | PostgreSQL + ClickHouse | 180 to 365 days | summary lookup + comparisons | small summary in PostgreSQL, deeper analytics in ClickHouse | keep PostgreSQL summary narrow |
| backtest full result JSON | backtest workers | backend API, frontend download, debug tooling | MinIO | 180 to 365 days | download by run id | large structured artifact | replace `trades_json`, `daily_pnl_json`, local JSON sidecars |
| backtest trades | backtest workers | backend API, analytics | ClickHouse | 365 days | list, aggregate, compare | high-volume query rows | migrate from `trades_json` and optional sidecar path |
| backtest position snapshots | backtest workers | backend API, analytics | ClickHouse | 180 to 365 days | chart/trend queries | high-volume query rows | migrate from `position_snapshots_json` |
| backtest daily PnL | backtest workers | backend API, analytics | ClickHouse | 365 days | time-series chart, comparison | analytical row model | migrate from `daily_pnl_json` |
| backtest equity curve | backtest workers | backend API, analytics | ClickHouse | 365 days | chart queries | analytical row model | dedicated schema currently NOT FOUND |
| strategy metrics | backtest workers, bot workers | backend API, analytics | ClickHouse + PostgreSQL summary refs | 180 to 365 days | aggregate queries | analytics-heavy | move off JSON summaries and local files |
| CSV export | backend API or worker jobs | frontend users | MinIO | 30 to 90 days | download by export id | file artifact | replace local CSV generation for server-side exports |
| generated report | backtest workers, backend API export jobs | frontend users | MinIO | 90 to 180 days | download by report id | file artifact | backend returns signed URL |
| chart/image artifact | backtest workers | frontend users | MinIO | 90 to 180 days | fetch by run/report id | binary artifact | backend returns signed URL |
| debug bundle | workers, backend export jobs | ops, engineering | MinIO | 14 to 30 days | fetch by task/run id | bulky structured artifact | keep out of PostgreSQL and Valkey |
| application logs | all services | observability stack | log backend / object archive, optional MinIO archive | 14 to 90 days hot, longer archive | search and incident review | operational telemetry | current checked-in logging stack manifests NOT FOUND |
| audit trail | backend API, workers | backend API, ops, compliance | PostgreSQL + JetStream `SYSTEM_AUDIT` | 180 days to long-lived | point lookup + append review | low-volume transactional audit | keep row sizes small |
| dashboard summary | backend projectors | frontend | PostgreSQL summary + Valkey cache + ClickHouse source | minutes in cache, long-lived summary in PostgreSQL | read-heavy dashboards | fast read path from durable summaries | backend should own summary projection, not frontend polling alone |

## Boundary Summary

- PostgreSQL stores state, metadata, summaries, and references.
- Valkey stores temporary coordination and cache only.
- NATS JetStream carries durable async commands and events.
- ClickHouse stores high-volume analytical rows.
- MinIO stores large artifacts and raw payloads.
