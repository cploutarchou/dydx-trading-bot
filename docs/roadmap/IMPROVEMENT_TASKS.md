# Improvement Tasks

Actionable development tasks derived from `PROJECT_IMPROVEMENT_PLAN.md`.  
Each task is self-contained and safe to implement without touching production trade logic.

## Incident Hotfix Completions (2026-05-16)

- [x] Enforced strict bot order status success criteria (`FILLED` only) and added regression coverage for failed/cancelled status variants.
- [x] Added backtest ownership checks before websocket push/proxy upgrade paths.
- [x] Added production startup security baseline checks (non-placeholder JWT secret + explicit CORS origin allowlist).
- [x] Fixed push hub broadcast race behavior and added reconnect resiliency.
- [x] Fixed candle warm-cache overwrite bug.
- [x] Replaced Redis `KEYS`-based deletion with `SCAN` and applied operation timeouts.
- [x] Updated schema compatibility tests to current realtime compatibility columns.
- [x] Updated frontend active-run push websocket URL construction to use backend resolver.

## Roadmap Verification Snapshot (2026-05-16)

Status below reflects code-level verification in this repository plus targeted test/lint/build checks.
Performance SLO numbers in individual tasks are considered implementation-complete but still require
environment-level benchmarking in deployed infra.

- [x] TASK-001 – Cache `get_markets()` result in-process (60s TTL)
- [x] TASK-002 – Cache `get_candles_recent()` per market (30s TTL)
- [x] TASK-003 – Remove duplicate `setInterval` polling from Dashboard
- [x] TASK-004 – Apply `queryConfigs.static` staleTime to settings/profile queries
- [x] TASK-005 – Add Redis TTL read-through cache for bot stats delegation
- [x] TASK-006 – Enable gzip response compression on Gin router
- [x] TASK-007 – Parallelize `construct_market_prices` candle fetches
- [x] TASK-008 – Complete `CandleCacheService` warm/prefetch implementation
- [x] TASK-009 – Consolidate Backtests page polling behavior
- [x] TASK-010 – Migrate StrategyManager server-state flows to React Query
- [x] TASK-011 – Add aggregate bot summary endpoint
- [x] TASK-012 – Add/align compound DB indexes for critical backtest/bot queries
- [x] TASK-013 – Move inline position/trade handlers to handler layer + tests
- [x] TASK-014 – Make API throttle configurable
- [x] TASK-015 – Celery completion events → Redis pub/sub → WebSocket push (WebSocket-first updates with 60s polling safety fallback)
- [x] TASK-016 – Shared market data background sync (producer + consumer path)
- [x] TASK-017 – Token-bucket rate limiting with fallback behavior
- [x] TASK-018 – Redis-backed API rate limiting with graceful fallback
- [x] TASK-019 – Circuit breaker + open-state Telegram alerting
- [x] TASK-020 – Pre-aggregation cache invalidation path on backtest delete
- [x] TASK-021 – Expose bot API stats in admin backend/frontend
- [x] TASK-022 – Structured cache logging fields for observability
- [x] TASK-023 – Trace ID logging in Python bot API request flow
- [x] TASK-024 – Candle fetch latency instrumentation

---

## Quick Wins (1–3 days)

---

### TASK-001 – Cache `get_markets()` result in-process (60s TTL)

**Priority**: P0 – High  
**Estimated Effort**: 0.5 day  
**Affected Modules**: `bot/src/trading/market_data.py`

**Description**  
`get_markets(client)` is called 3+ times per bot iteration cycle from `position_manager.py` (lines 216, 315, 719) with no caching. The dYdX perpetual markets list changes infrequently. Add a module-level dictionary cache with a 60-second TTL to return the cached value on all but the first call per minute.

**Implementation Notes**
- Add `_markets_cache = {"data": None, "expires": 0.0}` at module level in `market_data.py`
- In `get_markets()`, check `asyncio.get_event_loop().time() < _markets_cache["expires"]` before making the API call
- Use `MARKETS_CACHE_TTL = float(os.getenv("MARKETS_CACHE_TTL_SECONDS", "60"))`
- Per-instance mode: if multiple `BotInstance` objects share the same event loop, module-level cache is shared; this is acceptable since all instances use the same dYdX network

**Acceptance Criteria**
- `get_markets()` makes at most 1 HTTP call per 60-second window per Python process
- On cache hit, the function returns in < 1ms
- Cache can be disabled by setting `MARKETS_CACHE_TTL_SECONDS=0`
- Existing unit tests in `bot/tests/` pass unchanged

---

### TASK-002 – Cache `get_candles_recent()` per market (30s TTL)

**Priority**: P0 – High  
**Estimated Effort**: 0.5 day  
**Affected Modules**: `bot/src/trading/market_data.py`, `bot/src/trading/position_manager.py`

**Description**  
`get_candles_recent(client, market)` is called twice per open position pair in `position_manager.py` (lines 343–344 and 713–715). With 10 open pairs, that is 20 API calls that could be served from a 30-second in-memory cache. The recent candles data (last ~100 candles) does not change meaningfully within a single iteration cycle.

**Implementation Notes**
- Add an `asyncio`-safe LRU cache (max 200 entries) in `market_data.py`
- Cache key: `f"{market}:{effective_resolution}"`
- TTL: `CANDLES_RECENT_CACHE_TTL_SECONDS` env var, default 30
- Do not cache if `resolution` is explicitly overridden (non-default resolution)
- Use `functools.lru_cache` is not safe with async; use a plain dict with timestamp-based expiry

**Acceptance Criteria**
- Within a single iteration cycle, `get_candles_recent` for the same market makes at most 1 HTTP call
- Cache invalidation works correctly when TTL expires
- Cache size is bounded (max 200 entries) and does not grow unboundedly

---

### TASK-003 – Remove duplicate `setInterval` polling from Dashboard

**Priority**: P1 – Medium  
**Estimated Effort**: 0.5 day  
**Affected Modules**: `frontend/src/pages/Dashboard.tsx`

**Description**  
`Dashboard.tsx` has both a manual `setInterval(() => void computeStats(), 10000)` at line 431 AND a `useQuery` with `refetchInterval: 30_000` at line 505. Both fire independently, creating duplicate backend requests for overlapping data. Remove the manual `setInterval` block and rely solely on React Query's built-in `refetchInterval`.

**Implementation Notes**
- Remove `pollRef.current = setInterval(...)` at line 431 and the corresponding `clearInterval` in the cleanup
- Adjust the `useQuery` `refetchInterval` on the stats query to `10_000` if that frequency is needed
- Ensure `computeStats()` logic is incorporated into the `useQuery` `select` transform or `onSuccess` callback

**Acceptance Criteria**
- Dashboard makes at most 1 poll per configured interval, not 2
- No console errors on unmount (no dangling `setInterval`)
- Dashboard still updates every ~10 seconds when active

---

### TASK-004 – Apply `queryConfigs.static` staleTime to settings and profile queries

**Priority**: P1 – Medium  
**Estimated Effort**: 0.5 day  
**Affected Modules**: `frontend/src/api/hooks.ts`, `frontend/src/api/queryClient.ts`

**Description**  
`queryConfigs.static` (30-minute `staleTime`, 1-hour `gcTime`) is defined in `queryClient.ts` but not applied to queries for strategy configurations, Telegram settings, user profile, and system settings. These are fetched fresh on every window focus. Apply the static preset to avoid unnecessary refetches for data that changes only when the user explicitly saves.

**Implementation Notes**
- In `hooks.ts`, add `...queryConfigs.static` to `useQuery` options for:
  - `getCurrentUser` / `getProfile`
  - `getTelegramStatus` (both scopes)
  - `getSettings` / system settings
  - `getBotCapabilities`
- Do NOT apply to backtest list or bot status queries

**Acceptance Criteria**
- Settings page makes at most 1 API call per 30 minutes (absent explicit user save)
- Window focus does not trigger a refetch if data is < 30 minutes old
- A user-triggered save still invalidates and refetches immediately

---

### TASK-005 – Add Redis TTL read-through cache for bot stats delegation

**Priority**: P0 – High  
**Estimated Effort**: 1 day  
**Affected Modules**: `backend/internal/routes/bot_api_delegate_routes.go`, `backend/internal/services/cache_service.go`, `backend/internal/services/bot_api_client_extended.go`

**Description**  
`GET /api/v1/bots/:id/stats` is polled by the frontend every ~10 seconds. The Go backend forwards this directly to the Python bot API with no caching. Add a Redis read-through cache with a 30-second TTL. On write operations (start/stop/restart), invalidate the stats cache entry.

**Implementation Notes**
- In the delegated stats handler, before forwarding to the bot API:
  1. Check Redis: `GET bot:stats:{instance_id}`
  2. On hit: return cached JSON
  3. On miss: forward to bot API, cache the response, return
- Inject `CacheService` into the route registration (or middleware)
- Invalidate `bot:stats:{instance_id}` in the `/start`, `/stop`, `/restart` handlers
- Cache TTL: `BOT_STATS_CACHE_TTL_SECONDS` env var, default 30

**Acceptance Criteria**
- Cache hit rate > 90% under normal 10s polling
- Stats response latency drops from ~50–200ms to < 5ms on cache hit
- Start/stop/restart operations immediately invalidate the cache so next poll is fresh
- If Redis is unavailable, fall back to direct bot API call (no error surfaced to user)

---

### TASK-006 – Enable gzip response compression on Gin router

**Priority**: P2 – Low  
**Estimated Effort**: 0.25 day  
**Affected Modules**: `backend/cmd/server/`

**Description**  
The Go Gin backend does not apply response compression. Large backtest result payloads (candles, trades lists) can be 100–500KB. Adding `gin-contrib/gzip` middleware at the router level would reduce these payloads by 60–80%.

**Implementation Notes**
- Add `github.com/gin-contrib/gzip` to `backend/go.mod`
- Register `router.Use(gzip.Gzip(gzip.DefaultCompression))` before route registration
- Exclude health check and WebSocket upgrade routes from compression
- Verify frontend sends `Accept-Encoding: gzip` (standard browser behavior)

**Acceptance Criteria**
- Backtest results endpoint payload size reduced by > 50% for payloads > 1KB
- Health check (`/health`, `/ready`) endpoints still return uncompressed responses
- WebSocket upgrades are unaffected

---

## Medium Improvements (1–2 weeks)

---

### TASK-007 – Parallelize `construct_market_prices` candle fetches

**Priority**: P0 – High  
**Estimated Effort**: 2 days  
**Affected Modules**: `bot/src/trading/market_data.py`

**Description**  
`construct_market_prices` fetches candle data for each market in a sequential `for` loop (lines 183–210). With 50+ active markets and 3 timeframes each, this is 150+ sequential API calls. Replace the sequential loop with `asyncio.gather()` bounded by a semaphore to stay within rate limits. This does not reduce the number of API calls but dramatically reduces wall-clock time.

**Implementation Notes**
- Use `asyncio.Semaphore(int(os.getenv("CANDLE_FETCH_CONCURRENCY", "10")))` to bound concurrent calls
- Create an `async def fetch_market(sem, client, market, resolution)` helper
- Use `asyncio.gather(*[fetch_market(sem, client, m, resolution) for m in tradeable_markets])`
- The existing per-call `asyncio.sleep(0.2)` can be removed if the semaphore + dYdX rate limit is sufficient, OR moved inside the semaphore context
- Preserve the sequential fallback behavior under an env flag `CANDLE_FETCH_SEQUENTIAL=true` for debugging

**Acceptance Criteria**
- `construct_market_prices` for 50 markets completes in < 10 seconds (vs current 30+ seconds)
- No dYdX rate limit errors at semaphore size 10 (validate in testnet)
- If concurrency is set to 1, behavior is identical to current sequential implementation
- All existing tests pass

---

### TASK-008 – Complete `CandleCacheService` stubs in Go backend

**Priority**: P1 – Medium  
**Estimated Effort**: 2 days  
**Affected Modules**: `backend/internal/services/candle_cache_service.go`, `backend/internal/repository/backtest_repo.go`

**Description**  
`CandleCacheService.WarmCache()` and `PrefetchCandlesForRun()` log a message but do nothing. Implement them to:
1. `PrefetchCandlesForRun(runID int, ttlSeconds int)`: fetch all candles for a completed run from `backtest_candles` table and store in Redis
2. `WarmCache(runID int, markets []string, durationHours int)`: batch-fetch candles for multiple markets and cache them

**Implementation Notes**
- `PrefetchCandlesForRun` needs access to the DB; inject `*BacktestRepository` into `CandleCacheService` or pass as parameter
- Trigger `PrefetchCandlesForRun` from the backtest completion handler so the first chart render is always fast
- Use Redis key pattern `backtest:candles:{run_id}:{market}` with 24h TTL
- `WarmCache` should batch candles in pages of 1000 to avoid large single-query memory spikes

**Acceptance Criteria**
- After a backtest completes, the first chart load for that run is served entirely from Redis cache
- `GetCachedCandles` returns data for a warm run without touching PostgreSQL
- Cache miss falls back to DB query gracefully (existing behavior preserved)

---

### TASK-009 – Consolidate Backtests page polling into single interval

**Priority**: P1 – Medium  
**Estimated Effort**: 1 day  
**Affected Modules**: `frontend/src/pages/Backtests.tsx`

**Description**  
`Backtests.tsx` has four `useQuery` hooks with refetch intervals of 7s, 10s, 12s, and a conditional dynamic interval. All poll overlapping backtest data. Consolidate these into:
- A single `refetchInterval` of 10s when `activeRunCountForPolling > 0`
- A single `refetchInterval` of 60s when no active runs exist
- Share state between queries using React Query key invalidation rather than independent polls

**Implementation Notes**
- Identify data overlap between the four polling queries (lines 322, 339, 432, 454)
- Merge into 2 queries maximum: `backtestList` and `activeRunStatuses`
- Use `queryClient.invalidateQueries` for targeted invalidation after user actions (run new backtest, cancel)
- Set `refetchIntervalInBackground: false` to avoid background tab polling

**Acceptance Criteria**
- At most 2 polling queries active at any time on the Backtests page
- Active runs still update within 15 seconds
- No polling occurs when no backtests are active (use 60s interval or suspend)
- Background tabs do not poll

---

### TASK-010 – Migrate StrategyManager to React Query

**Priority**: P1 – Medium  
**Estimated Effort**: 2 days  
**Affected Modules**: `frontend/src/components/StrategyManager.tsx`, `frontend/src/api/hooks.ts`

**Description**  
`StrategyManager.tsx` uses `useState` + `useEffect` + direct `api.ts` axios calls for strategy list and status. This bypasses the React Query cache, causing duplicate network requests when the same data is needed in other components. Migrate to `useQuery` / `useMutation` patterns from `frontend/src/api/hooks.ts`.

**Implementation Notes**
- Strategy list: use existing `useQuery(queryKeys.bots(params), ...)` or add `useStrategies()` hook in `hooks.ts`
- Strategy runtime status: use `useQuery(queryKeys.botStats(instanceId), ..., { staleTime: 15_000 })` (already exists)
- Strategy start/stop/restart: use `useMutation` with `onSuccess: () => cacheUtils.invalidateBotQueries(instanceId)`
- Keep internal UI state (`isModalOpen`, `selectedStrategy`) as local `useState` — only server data moves to React Query
- The `StrategyStartReadiness` check should use `useQuery` with `staleTime: 30_000` and enabled only when the modal is open

**Acceptance Criteria**
- No direct `api.ts` calls remain in the component for server state (list, status, start/stop)
- Navigating away and back to the Strategy page does not re-fetch if data is < 5 minutes old
- Start/stop mutations correctly invalidate and refetch the strategy status

---

### TASK-011 – Add aggregate bot summary endpoint

**Priority**: P1 – Medium  
**Estimated Effort**: 1 day  
**Affected Modules**: `backend/internal/handlers/bot_instance_handler.go`, `backend/internal/routes/bot_instance_routes.go`, `frontend/src/api/enhancedClient.ts`, `frontend/src/api/hooks.ts`

**Description**  
On the bot dashboard page, the frontend makes 4 separate API calls: `GET /bots`, `GET /bots/:id/stats`, `GET /bots/:id/positions`, `GET /bots/:id/trades`. Add `GET /api/v1/bots/:id/summary` that returns all four in a single response. Cache the stats sub-component in Redis (30s TTL).

**Implementation Notes**
- Go handler: call `GetBotInstanceStats`, `ListBotPositionsByInstanceID`, and `ListBotTradesByInstanceID` within one request, compose into a single JSON response
- Add query params `?include=stats,positions,trades` to allow partial responses if needed
- Frontend: add `getBotSummary(instanceId)` to `enhancedClient.ts` and a `useBotSummary(instanceId)` hook
- Migrate the bot dashboard page to use the new hook

**Acceptance Criteria**
- Bot dashboard page load requires exactly 2 API calls: list bots + 1 summary per bot
- Response time for `/summary` < 200ms (stats from cache + DB queries for positions/trades)
- Existing individual endpoints remain functional for backward compatibility

---

### TASK-012 – Add compound DB indexes for performance-critical queries

**Priority**: P1 – Medium  
**Estimated Effort**: 1 day  
**Affected Modules**: `backend/migrations/postgres/`

**Description**  
Add a migration with the following indexes, verified against the actual query patterns in the repository layer.

**Indexes to add**:

```sql
-- Backtest list (most common query pattern)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtest_runs_user_status_created
    ON backtest_runs (user_id, status, created_at DESC);

-- Active backtests partial index (small set, frequently queried)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backtest_runs_active
    ON backtest_runs (user_id, created_at DESC)
    WHERE status IN ('running', 'pending', 'started');

-- Bot instances list per user
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bot_instances_user_status
    ON bot_instances (user_id, status);

-- Bot trades per instance ordered by time
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bot_trades_instance_created
    ON bot_trades (bot_instance_id, created_at DESC);
```

**Implementation Notes**
- Use `CREATE INDEX CONCURRENTLY` in migration SQL to avoid table locks
- Do NOT use `CONCURRENTLY` in startup migration flow — wrap in a separate migration executed via `psql` or deployment script if the table is large (per existing convention in repo)
- Verify migration 000047 and 000051 do not already cover these patterns before creating duplicates

**Acceptance Criteria**
- `EXPLAIN ANALYZE` on backtest list query for a user with 1000+ runs shows index scan, not sequential scan
- Migration runs without locking errors in the test environment
- Existing tests in `backend/internal/repository/backtest_repo_*.go` pass

---

### TASK-013 – Move inline position/trade handlers to handler layer

**Priority**: P2 – Low (architecture)  
**Estimated Effort**: 1 day  
**Affected Modules**: `backend/internal/routes/bot_instance_routes.go`, `backend/internal/handlers/bot_instance_handler.go`

**Description**  
`bot_instance_routes.go` lines 56–165 define `GET /:instance_id/positions` and `GET /:instance_id/trades/:trade_id` as anonymous inline functions. This pattern bypasses the handler layer and makes unit testing impossible without spinning up a full router. Move to `BotInstanceHandler` methods following the pattern established in `handlers/bot_instance_handler.go`.

**Implementation Notes**
- Add `GetBotPositions(c *gin.Context)` method to `BotInstanceHandler`
- Add `GetBotTrade(c *gin.Context)` method to `BotInstanceHandler`
- Update route registration to use `botInstanceHandler.GetBotPositions` etc.
- Inject `BotPositionRepository` and `BotTradeRepository` through `BotInstanceHandler` constructor
- Add pagination parameters (`page`, `page_size`) to both handlers (see TASK-016)

**Acceptance Criteria**
- No inline anonymous handler functions remain in `bot_instance_routes.go`
- Both endpoints are covered by handler-level unit tests
- Behavior is unchanged from the user's perspective

---

### TASK-014 – Make `asyncio.sleep` throttle configurable

**Priority**: P2 – Low  
**Estimated Effort**: 0.5 day  
**Affected Modules**: `bot/src/trading/market_data.py`, `bot/src/trading/account_manager.py`

**Description**  
Hard-coded `asyncio.sleep(0.2)` throttle calls in `market_data.py` (lines 72, 114) and `account_manager.py` (lines 142, 499) add artificial latency even when the rate limit has not been reached. Make the throttle duration configurable via environment variable `DYDX_API_THROTTLE_MS` (default 200 ms) so it can be tuned per environment without code changes.

**Implementation Notes**
- Add to `bot/src/constants.py`: `DYDX_API_THROTTLE_SECONDS = float(os.getenv("DYDX_API_THROTTLE_MS", "200")) / 1000`
- Replace all `asyncio.sleep(0.2)` occurrences with `asyncio.sleep(DYDX_API_THROTTLE_SECONDS)`
- For backtest workloads where rate limits are not a concern, operators can set `DYDX_API_THROTTLE_MS=50`

**Acceptance Criteria**
- `DYDX_API_THROTTLE_MS=0` disables all throttle sleeps
- `DYDX_API_THROTTLE_MS=200` (default) produces identical behavior to current
- The constant is importable from `src.constants` in any module that needs it

---

## Larger Refactoring (3–6 weeks)

---

### TASK-015 – Celery task completion events → Redis pub/sub → WebSocket push

**Priority**: P0 – High (long-term)  
**Estimated Effort**: 2 weeks  
**Affected Modules**: `bot/src/infrastructure/workers/backtest_tasks.py`, `backend/internal/` (new Redis subscriber), `frontend/src/api/websocket.ts`, `frontend/src/pages/Backtests.tsx`

**Description**  
Replace the 7s frontend polling for backtest status with server-push events. When a backtest task transitions state (started → running → completed/failed), publish to a Redis pub/sub channel. The Go backend subscribes and forwards messages to connected WebSocket clients.

**Implementation Notes**

*Python bot (publisher)*:
- After `repository.save_run(data)` status changes, call:
  ```python
  redis_client.publish(f"backtest:{run_id}:status", json.dumps({"status": new_status, "progress": pct}))
  ```
- Add a `_redis_pubsub_client` singleton in `celery_app.py` using the same `REDIS_URL`

*Go backend (subscriber)*:
- Create a goroutine in startup that subscribes to `backtest:*:status` pattern
- On message received, look up connected WebSocket clients for the owning user and push the event
- Integrate with the existing `websocketUpgrader` in `bot_api_delegate_routes.go`

*Frontend*:
- In `Backtests.tsx`, open a WebSocket subscription when active runs exist
- On status push: call `queryClient.invalidateQueries(['backtests', runId])` to trigger a single refresh
- Remove the 7s `refetchInterval` for active run status; keep the 60s fallback poll as a safety net

**Acceptance Criteria**
- Backtest status updates appear in the frontend within 2 seconds of the Celery task state change
- No polling occurs during an active run (except the 60s safety fallback)
- Disconnected frontend clients automatically fall back to polling
- WebSocket disconnection/reconnection is handled gracefully (existing `useManagedWebSocket` hook)

---

### TASK-016 – Shared market data background sync (Celery Beat)

**Priority**: P0 – High (long-term)  
**Estimated Effort**: 1 week  
**Affected Modules**: `bot/src/trading/realtime_data_service.py`, `bot/src/infrastructure/workers/celery_app.py`, `bot/src/trading/market_data.py`

**Description**  
Currently each active bot instance fetches its own market data from dYdX independently via `_update_market_data` in `RealTimeDataService`. If 5 bot instances are running, dYdX receives 5× as many candle requests for the same markets. Move market data fetching to a single Celery Beat periodic task that fetches all active markets once, stores results in Redis, and broadcasts to the WebSocket server. Individual bot instances read from the shared Redis cache.

**Implementation Notes**
- Add a Celery Beat schedule entry in `celery_app.py`:
  ```python
  celery_app.conf.beat_schedule = {
      "sync-market-data": {
          "task": "bot.sync_market_data",
          "schedule": 10.0,  # seconds
      }
  }
  ```
- New task `sync_market_data`: fetch all active markets' recent candles, store in `Redis` keys `market:candles:{market}:{resolution}` with 30s TTL
- Modify `get_candles_recent()` in `market_data.py` to check Redis first, fall back to dYdX API on miss
- Modify `RealTimeDataService._update_market_data` to read from Redis cache instead of calling dYdX

**Acceptance Criteria**
- With 5 bot instances running, dYdX receives 1 candle fetch per market per cycle (not 5)
- Redis key for each market is updated every 10 seconds
- Individual bot instances continue to function correctly when reading from cache
- If the Beat task fails, instances fall back to direct dYdX calls (no silent data staleness)

---

### TASK-017 – Token-bucket rate limiter replacing fixed sleep throttles

**Priority**: P1 – Medium (long-term)  
**Estimated Effort**: 1 week  
**Affected Modules**: `bot/src/trading/market_data.py`, `bot/src/trading/account_manager.py`

**Description**  
The current `asyncio.sleep(0.2)` throttle adds 0.2s of latency per API call regardless of actual rate limit state. Replace with an async token-bucket rate limiter that only blocks when the configured rate window is full. This allows bursting when requests are below the limit while still protecting against rate-limit errors.

**Implementation Notes**
- Add `aiolimiter` to `bot/requirements.txt`
- Create a module-level `AsyncLimiter(max_rate=10, time_period=2.0)` in `market_data.py` (10 req/2s = 5 req/s, matching dYdX's approximate public rate limit)
- Wrap each API call with `async with rate_limiter:` instead of `asyncio.sleep(...)`
- Configure `DYDX_RATE_LIMIT_RPS` and `DYDX_RATE_LIMIT_WINDOW` env vars for tuning

**Acceptance Criteria**
- At < 10 req/2s, calls are not throttled (latency improvement vs. current)
- At 10+ req/2s, subsequent calls wait only as long as needed (not a fixed 0.2s)
- dYdX 429 responses drop to near-zero after tuning
- Falls back to 200ms sleep if `aiolimiter` is not installed (import error handled gracefully)

---

### TASK-018 – Redis-backed rate limiter for bot API (multi-worker safe)

**Priority**: P2 – Medium (long-term)  
**Estimated Effort**: 1 week  
**Affected Modules**: `bot/src/api/server.py` (`_SlidingWindowRateLimiter` class)

**Description**  
The sliding-window rate limiter in `server.py` stores state in a Python dict (`self._buckets`). This is reset on process restart and does not share state across workers. For multi-worker deployments (`uvicorn --workers N`), the effective rate limit is `max_requests × N`. Replace with a Redis-based implementation using sorted sets (standard sliding-window Redis pattern).

**Implementation Notes**
- Use `redis-py` (already a transitive dependency via Celery) to store rate limit windows
- Key pattern: `ratelimit:{endpoint}:{caller_ip}` as a Redis sorted set
- `ZADD key time time` + `ZREMRANGEBYSCORE key -inf (now - window)` + `ZCARD key` in a pipeline
- Wrap in try/except: if Redis is unavailable, fall back to in-process limiter (no outage on Redis failure)
- Configurable via existing `BACKTEST_RATE_LIMIT_*` env vars

**Acceptance Criteria**
- Rate limit is consistent across all uvicorn workers sharing the same Redis instance
- Rate limit state persists across process restarts (sliding window continues from last request)
- Redis failure causes graceful fallback to in-process limiter with a warning log
- Existing rate limit tests pass with the new implementation

---

### TASK-019 – Circuit breaker around dYdX API calls

**Priority**: P1 – Medium (long-term)  
**Estimated Effort**: 1 week  
**Affected Modules**: `bot/src/trading/market_data.py`, `bot/src/trading/account_manager.py`, `bot/src/trading/bot_agent.py`

**Description**  
Currently the only protection against dYdX API failures is `asyncio.wait_for` with a 15s timeout. During a dYdX outage, the bot will retry every cycle, consuming rate limit quota and producing noisy logs. Add a circuit breaker (open after 3 consecutive failures within 60s, half-open after 30s recovery period) to stop calling dYdX during known downtime.

**Implementation Notes**
- Add `pybreaker` to `bot/requirements.txt`
- Create a module-level `CircuitBreaker` instance in `market_data.py`
- Wrap `get_perpetual_market_candles`, `get_perpetual_markets`, and account indexer calls
- On circuit open: log a CRITICAL message and send a Telegram alert; return cached data if available
- On circuit recovery: log INFO and resume normal operation

**Acceptance Criteria**
- After 3 consecutive API failures, circuit opens and stops calling dYdX for 30 seconds
- Circuit-open state triggers a Telegram notification
- After 30s, one probe request is allowed (half-open); on success, circuit closes
- Circuit state is NOT shared between bot instances (each instance has its own breaker)

---

### TASK-020 – Pre-aggregate backtest candle data on completion

**Priority**: P2 – Medium (long-term)  
**Estimated Effort**: 2 weeks  
**Affected Modules**: `bot/src/infrastructure/workers/backtest_tasks.py` (new post-processing task), `backend/internal/services/candle_cache_service.go`, `backend/internal/handlers/` (chart endpoint)

**Description**  
When a user opens a completed backtest chart, the frontend fetches thousands of raw candle rows from PostgreSQL and renders them client-side. Pre-aggregate candle data into OHLCV chart buckets (per-minute, per-hour) immediately after a backtest completes. Cache the aggregated result in Redis. The chart endpoint returns pre-aggregated data from cache.

**Implementation Notes**

*Bot worker*:
- After `status = "completed"`, trigger a new Celery task `aggregate_backtest_candles.delay(run_id)`
- The new task reads raw candles from `backtest_candles`, aggregates into 1-min and 1-hour OHLCV, stores in Redis:
  - `backtest:chart:1min:{run_id}` TTL 24h
  - `backtest:chart:1hour:{run_id}` TTL 24h

*Go backend*:
- Modify `GET /api/v1/backtests/:run_id/candles` to check Redis cache before querying PostgreSQL
- Add `?resolution=1min|1hour` query param

*Frontend*:
- Pass `?resolution=1hour` for the overview chart and `?resolution=1min` for drill-down

**Acceptance Criteria**
- First chart render for a completed backtest loads in < 300ms (from Redis)
- Raw candle data remains available in PostgreSQL for data export
- Cache is invalidated when the backtest run is deleted
- Falls back to PostgreSQL if cache miss (first load or after cache eviction)

---

## Observability Tasks

---

### TASK-021 – Expose bot API stats endpoint in admin dashboard

**Priority**: P2 – Low  
**Estimated Effort**: 0.5 day  
**Affected Modules**: `backend/internal/routes/`, `frontend/src/pages/AdminHub.tsx`

**Description**  
`backend/internal/services/bot_api_client.go` tracks total requests, failures, latency, and timeouts in atomic counters via `BotAPIStats()`. This data is not exposed via any API endpoint. Add `GET /api/v1/admin/bot-api-stats` and display on `AdminHub.tsx`.

**Acceptance Criteria**
- Admin users can see bot API request count, error rate, and average latency from the admin UI
- Endpoint requires admin role (not accessible to regular users)
- Stats reset on Go backend restart (in-memory counters, no persistence required)

---

### TASK-022 – Structured logging for CacheService (replace `log.Printf`)

**Priority**: P2 – Low  
**Estimated Effort**: 0.5 day  
**Affected Modules**: `backend/internal/services/cache_service.go`

**Description**  
`cache_service.go` uses `log.Printf` for cache hit/miss logging. Replace with structured log calls (zerolog or whatever the rest of the backend uses) including fields: `key`, `ttl_seconds`, `hit` (bool), `latency_ms`. This enables building cache hit-rate dashboards in Loki/Grafana.

**Acceptance Criteria**
- Cache hits and misses produce structured log entries with consistent field names
- Log level: DEBUG for cache hits, INFO for cache misses, ERROR for Redis errors
- No change to external API behavior

---

### TASK-023 – Add trace ID logging to Python bot API request handler

**Priority**: P2 – Low  
**Estimated Effort**: 0.5 day  
**Affected Modules**: `bot/src/api/server.py`

**Description**  
The Go backend generates and forwards a `X-Trace-ID` header on all delegated requests to the Python bot API. The Python API does not log this header, breaking distributed trace correlation. Add FastAPI middleware to extract and bind the trace ID to the Loguru context on every request.

**Acceptance Criteria**
- Every Python bot API log line for a delegated request includes the originating `trace_id`
- The trace ID is visible in Loki logs alongside Go backend trace ID for end-to-end correlation
- If no trace header is present, a new UUID is generated (existing behavior preserved)

---

### TASK-024 – Add candle fetch latency metrics

**Priority**: P3 – Low  
**Estimated Effort**: 0.5 day  
**Affected Modules**: `bot/src/trading/market_data.py`

**Description**  
Add per-call timing around `get_candles_historical` and `get_candles_recent` and emit to Loki with labels `market`, `resolution`, `timeframe`, `latency_ms`. This surfaces which markets are consistently slowest to respond and informs parallel fetch tuning decisions.

**Acceptance Criteria**
- Each successful candle fetch emits a structured log entry with `latency_ms`
- Failed fetches emit a log entry with `error` and `latency_ms`
- Loki labels include `market` and `resolution` for filtering
- No impact on fetch performance (timing uses `time.monotonic()`)
