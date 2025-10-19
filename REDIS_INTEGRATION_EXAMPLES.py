"""
Integration guide: Redis caching with backtest system.
Shows how Redis integrates with existing backtest functionality.
"""

# Example 1: Check for cached backtest result
# ============================================

from sqlalchemy.orm import Session

from backend.redis_service import get_redis_service
from backend.services import RedisSettingsService


async def get_or_create_backtest_result(
    db: Session,
    start_date: str,
    end_date: str,
    num_pairs: int,
    strategy_params: dict = None,
):
    """
    Example of cache-first pattern for backtests.

    Flow:
    1. Check Redis if enabled
    2. Look for cached result with identical parameters
    3. If found, return instantly
    4. If not found, run backtest
    5. Cache result before returning
    """

    redis_service = get_redis_service()
    redis_settings = RedisSettingsService.get_redis_settings(db)

    # Step 1: Check if caching is enabled
    if not redis_settings or not redis_settings.get("enabled"):
        # Redis disabled, run backtest normally
        return await run_backtest(start_date, end_date, num_pairs, strategy_params)

    # Step 2: Build cache key from parameters
    cache_key = f"backtest:{start_date}:{end_date}:{num_pairs}"
    if strategy_params:
        strategy_hash = hash(frozenset(strategy_params.items()))
        cache_key += f":{strategy_hash}"

    # Step 3: Check Redis cache
    if redis_service.enabled:
        cached_result = redis_service.get_json(cache_key)
        if cached_result:
            print(f"✓ Cache HIT for {cache_key}")
            # Update statistics
            RedisSettingsService.update_redis_settings(
                db, total_cache_hits=redis_settings.get("total_cache_hits", 0) + 1
            )
            return cached_result
        else:
            print(f"✗ Cache MISS for {cache_key}")

    # Step 4: Run backtest since not in cache
    result = await run_backtest(start_date, end_date, num_pairs, strategy_params)

    # Step 5: Cache the result
    if redis_service.enabled:
        ttl = redis_settings.get("cache_ttl_seconds", 86400)
        cached = redis_service.set_json(cache_key, result, ttl_seconds=ttl)
        if cached:
            print(f"✓ Cached result with TTL: {ttl}s")
        else:
            print("✗ Failed to cache result")

    return result


# Example 2: Cache market data
# =============================


async def get_candles_cached(
    client,
    market: str,
    resolution: str,
    from_iso: str,
    to_iso: str,
    db: Session = None,
):
    """
    Cache market data fetches to avoid repeated API calls.

    This reduces:
    - API calls to dYdX
    - Bandwidth usage
    - Analysis latency
    """

    redis_service = get_redis_service()

    # Build cache key
    cache_key = f"candles:{market}:{resolution}:{from_iso}:{to_iso}"

    # Try cache first
    if redis_service.enabled:
        cached = redis_service.get_json(cache_key)
        if cached:
            return cached

    # Fetch from API
    candles = await client.get_candles(market, resolution, from_iso, to_iso)

    # Cache result (shorter TTL for market data - 1 hour)
    if redis_service.enabled:
        redis_service.set_json(cache_key, candles, ttl_seconds=3600)

    return candles


# Example 3: Cache cointegration analysis results
# ================================================


async def analyze_pair_cached(
    base_market: str,
    quote_market: str,
    historical_prices_1: list,
    historical_prices_2: list,
    db: Session = None,
):
    """
    Cache expensive cointegration analysis results.

    Prevents re-computing for the same market pairs
    when only market prices have changed slightly.
    """

    from app.func_cointegration import test_cointegration

    redis_service = get_redis_service()

    # Build cache key (markets are same regardless of price data)
    cache_key = f"cointegration:{base_market}:{quote_market}"

    # Try cache first
    if redis_service.enabled:
        cached = redis_service.get_json(cache_key)
        if cached:
            # Use cached result but verify it's still valid
            # (optional: re-test if market data is too old)
            return cached

    # Perform analysis
    result = test_cointegration(
        base_market, quote_market, historical_prices_1, historical_prices_2
    )

    # Cache with longer TTL (analysis is stable for hours)
    if redis_service.enabled:
        redis_service.set_json(cache_key, result, ttl_seconds=43200)  # 12 hours

    return result


# Example 4: Monitor cache performance
# =====================================


async def get_cache_health_report(db: Session):
    """
    Get comprehensive cache performance report.
    Use for monitoring and optimization.
    """

    redis_service = get_redis_service()

    if not redis_service.enabled:
        return {"status": "Redis not enabled"}

    stats = redis_service.get_cache_stats()
    connection = redis_service.check_connection()

    # Calculate cache health
    total_requests = stats.get("hits", 0) + stats.get("misses", 0)
    hit_rate = stats.get("hit_rate", 0)

    # Assess health
    if hit_rate > 0.8:
        health = "EXCELLENT"
    elif hit_rate > 0.6:
        health = "GOOD"
    elif hit_rate > 0.3:
        health = "FAIR"
    else:
        health = "POOR"

    return {
        "connection": {
            "connected": connection.get("connected"),
            "status": connection.get("last_connection_status"),
        },
        "performance": {
            "total_requests": total_requests,
            "cache_hits": stats.get("hits", 0),
            "cache_misses": stats.get("misses", 0),
            "hit_rate_percent": hit_rate * 100,
            "health_status": health,
        },
        "resources": {
            "memory_used_mb": stats.get("memory_used_mb", 0),
            "total_keys": stats.get("total_keys", 0),
            "evictions": stats.get("evictions", 0),
        },
        "recommendations": _get_cache_recommendations(stats, health),
    }


def _get_cache_recommendations(stats: dict, health: str):
    """Generate optimization recommendations."""

    recommendations = []

    if health == "POOR":
        recommendations.append(
            "Hit rate is low. Consider increasing cache TTL or adjusting strategy parameters."
        )

    if stats.get("evictions", 0) > 0:
        recommendations.append(
            "Cache evictions detected. Increase Redis maxmemory setting or reduce TTL."
        )

    if stats.get("memory_used_mb", 0) > 100:
        recommendations.append(
            "Memory usage is high. Monitor for memory leaks or reduce cache size."
        )

    if health in ["EXCELLENT", "GOOD"]:
        recommendations.append("Cache is performing well. No action needed.")

    return recommendations


# Example 5: Configuration via UI
# ================================

"""
The RedisSettings UI component in frontend/src/components/RedisSettings.tsx
provides a user-friendly interface to:

1. View Connection Status
   - Redis version
   - Uptime
   - Connected clients
   - Memory usage

2. Modify Settings
   - Host/Port/Database
   - Password
   - Timeout
   - Max connections

3. Configure Caching
   - Enable/disable overall
   - Toggle individual features (backtest, market data, analysis)
   - Set cache TTL

4. Monitor Performance
   - Cache hit/miss rates
   - Memory consumption
   - Evictions
   - Performance graphs

5. Manage Cache
   - Test connection
   - Flush entire cache
   - View statistics

All changes are persisted to database via RedisSettingsService.
"""

# Example 6: Environment variable configuration
# ================================================

"""
For automated deployments, configure via environment variables:

export REDIS_ENABLED=true
export REDIS_HOST=redis.production.local
export REDIS_PORT=6379
export REDIS_PASSWORD=your_secure_password
export REDIS_DB=0
export REDIS_SSL=true
export REDIS_TIMEOUT=10
export REDIS_MAX_CONNECTIONS=50

These override config.yaml settings and are applied at application startup.
"""

# Example 7: Docker deployment
# =============================

"""
In docker-compose.yml, Redis is configured with:

services:
  redis:
    image: redis:7-alpine
    container_name: dydx-redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --requirepass redis_password
    networks:
      - dydx-network
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis_password", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

To start:
  docker-compose up redis

To test:
  docker exec dydx-redis redis-cli -a redis_password ping
  # Should return: PONG
"""

# Example 8: Production checklist
# ================================

PRODUCTION_CHECKLIST = """
Before deploying to production:

[ ] Security
    [ ] Change Redis password from default
    [ ] Enable SSL/TLS in docker-compose.yml
    [ ] Restrict network access to Redis
    [ ] Use strong password (32+ characters, random)
    [ ] Store password in secrets manager

[ ] Performance
    [ ] Set maxmemory and eviction policy
    [ ] Configure appropriate TTLs for your use case
    [ ] Monitor cache hit rates
    [ ] Set max_connections based on expected load

[ ] Reliability
    [ ] Enable AOF (Append-Only File) persistence
    [ ] Configure backup strategy
    [ ] Set up monitoring and alerting
    [ ] Test failover procedure
    [ ] Document recovery procedures

[ ] Operations
    [ ] Document Redis configuration
    [ ] Create monitoring dashboards
    [ ] Set up log aggregation
    [ ] Train ops team on Redis administration
    [ ] Plan capacity for growth

[ ] Testing
    [ ] Test under production load
    [ ] Verify cache invalidation works
    [ ] Test failover scenarios
    [ ] Benchmark performance improvements
"""
