# Valkey Plan

## Role of Valkey

Valkey is the Redis-compatible temporary coordination layer for:

- cache
- distributed locks with TTL
- rate limits
- deduplication windows
- worker leases
- short-lived active task state

Valkey must not be:

- the primary durable database
- the only queue for critical tasks
- the permanent task-state store
- the store for large result payloads

## Current Findings From Repository

- Backend accepts Redis/Valkey aliases in `backend/config/config.go`.
- Bot accepts Redis/Valkey aliases in `bot/config/config.py` and `bot/src/shared/redis_env.py`.
- Current active usage includes:
  - cache in `backend/internal/services/cache_service.go`
  - Redis pub/sub in `backend/internal/services/backtest_push_hub.go`
  - Celery broker/backend in `bot/src/infrastructure/workers/celery_app.py`
  - backtest lock and pub/sub in `bot/src/infrastructure/workers/backtest_tasks.py`
  - market data cache in `bot/src/trading/market_data.py`
  - Redis-backed rate limiting in `bot/src/api/server.py`
- Deployment already uses Valkey images in:
  - `docker-compose.infra.yml`
  - `docker-compose.stack.yml`
  - `deploy/k8s-next/valkey.yaml`

## Redis-to-Valkey Migration Notes

- Most repo code already uses Redis-compatible clients, so protocol compatibility should be straightforward.
- Config aliases for `REDIS_*` and `VALKEY_*` already exist.
- The main migration problem is not client compatibility; it is responsibility cleanup.

### Compatibility checks

- verify Lua lock scripts remain compatible
- verify Celery broker compatibility during transition if Celery remains temporarily
- verify client TLS/auth settings
- standardize on one canonical env naming scheme while keeping aliases for rollout

## Cache Strategy

Use Valkey for:

- API response cache
- hot dashboard summary cache
- market data short-lived cache
- expensive analytical summary cache with short TTL

Do not use it for:

- final task summaries as the only record
- full backtest results
- raw exchange payload archives

## Lock Strategy

Use TTL-bound locks only for coordination:

- bot active lock
- task execution claim lock
- export generation lock

Rules:

- every lock must include TTL
- every lock value must include an owner token
- every lock release must verify owner token
- lock presence alone does not prove task success; PostgreSQL remains authoritative

## Rate Limit Strategy

### Backend

- replace in-process limiter in `backend/internal/middleware/rate_limit.go`
- use Valkey-backed counters for distributed enforcement

### Bot API

- keep Redis/Valkey-backed limiter, remove in-process-only fallback where strict distributed behavior is required

Recommended approach:

- token bucket or sliding window keyed by user/service/client id
- short TTL windows
- metrics for hits and rejections

## Deduplication Strategy

Use short-lived dedupe keys for:

- event replay suppression
- export rerun suppression
- repeated button-click suppression before command row creation completes

Rules:

- dedupe keys are advisory
- authoritative idempotency remains in PostgreSQL command/task tables

## Worker Lease Strategy

Use Valkey for:

- ephemeral worker leases
- active consumer ownership hints
- heartbeat freshness shortcuts

Rules:

- lease key must expire automatically
- PostgreSQL still records last durable heartbeat and task state

## Key Naming Conventions

- `cache:api:{route}:{hash}`
- `cache:dashboard:{scope}:{hash}`
- `lock:bot:{bot_id}`
- `lock:task:{task_id}`
- `lock:export:{export_id}`
- `rate:user:{user_id}:{window}`
- `rate:ip:{ip}:{window}`
- `dedupe:event:{event_id}`
- `lease:worker:{worker_id}`
- `active:bot:{bot_id}`
- `active:task:{task_id}`

## TTL Rules

- cache keys: 15s to 300s depending on endpoint
- rate-limit counters: match window size plus small buffer
- lock keys: just above expected critical section duration
- dedupe keys: short replay window only
- lease keys: 2x to 3x heartbeat interval
- active state keys: short TTL, continuously refreshed

Non-negotiable:

- all temporary keys need TTL

## Memory / Eviction Recommendations

- prefer `allkeys-lru` or `volatile-lru` based on whether only TTL-managed keys are allowed
- avoid mixing unbounded non-TTL data with cache data
- alert on evictions, latency, and memory fragmentation

## Anti-Patterns To Remove

- Celery/Redis as the long-term durable queue substrate for critical task execution
- Redis pub/sub as the only progress event path
- result payload storage in Valkey
- permanent task state in Valkey
- missing TTLs on locks and active-state keys

## Mapping From Current Repo

### Keep and tighten

- `backend/internal/services/cache_service.go`
  - keep as cache-only
- Redis/Valkey env helpers in backend and bot
  - keep as compatibility layer
- lock token verification in `bot/src/infrastructure/workers/backtest_tasks.py`
  - keep the pattern, but pair it with PostgreSQL idempotency state

### Replace or reduce

- `bot/src/infrastructure/workers/celery_app.py`
  - stop using Valkey as the critical durable queue substrate
- `backend/internal/services/backtest_push_hub.go`
  - replace Redis pub/sub with JetStream-backed projection or backend-local fan-out fed from durable events
- `backend/internal/middleware/rate_limit.go`
  - replace in-process limiter with Valkey-backed distributed limiter

## Non-Negotiable Boundary

- all temporary keys need TTL
- no critical durable data lives only in Valkey
- no large result payloads in Valkey
- no permanent queues in Valkey for critical jobs
