# Database and Redis Configuration Guide

## Overview

The dYdX Trading Bot supports both YAML-based configuration (via `config.yaml`) and environment variables for database and Redis settings. Configuration is loaded with the following priority:

1. **config.yaml** - Primary source (if section exists)
2. **Environment variables** - Override or provide config
3. **Built-in defaults** - Last resort fallback

## Database Configuration

### YAML Configuration (app/config.yaml)

```yaml
database:
  type: sqlite              # sqlite or postgresql
  name: dydx_backtest.db   # Database name/file
  user: postgres           # DB username (PostgreSQL only)
  password: ""             # DB password (PostgreSQL only)
  host: localhost          # Database host
  port: "5432"             # Database port
  pool_size: 5             # Connection pool size
  max_overflow: 10         # Max overflow connections
  timeout: 30              # Query timeout in seconds
```

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DB_TYPE` | string | sqlite | Database type: `sqlite` or `postgresql` |
| `DB_NAME` | string | dydx_backtest.db | Database name or SQLite filename |
| `DB_USER` | string | postgres | PostgreSQL username |
| `DB_PASSWORD` | string | (empty) | PostgreSQL password |
| `DB_HOST` | string | localhost | Database host address |
| `DB_PORT` | string | 5432 | Database port |
| `DB_POOL_SIZE` | int | 5 | Connection pool size |
| `DB_MAX_OVERFLOW` | int | 10 | Max overflow connections |
| `DB_TIMEOUT` | int | 30 | Query timeout in seconds |
| `SQL_ECHO` | string | false | Log all SQL queries (true/false) |

### Setup Examples

#### SQLite (Development)

```yaml
database:
  type: sqlite
  name: dydx_backtest.db
  pool_size: 5
```

Or via environment:

```bash
export DB_TYPE=sqlite
export DB_NAME=dydx_backtest.db
```

#### PostgreSQL (Production)

```yaml
database:
  type: postgresql
  name: dydx_trading_bot
  user: postgres
  password: secure_password
  host: db.example.com
  port: "5432"
  pool_size: 10
  max_overflow: 20
```

Or via environment:

```bash
export DB_TYPE=postgresql
export DB_NAME=dydx_trading_bot
export DB_USER=postgres
export DB_PASSWORD=secure_password
export DB_HOST=db.example.com
export DB_PORT=5432
export DB_POOL_SIZE=10
export DB_MAX_OVERFLOW=20
```

## Redis Configuration

### YAML Configuration (app/config.yaml)

```yaml
redis:
  enabled: true              # Enable/disable Redis
  host: localhost            # Redis hostname
  port: 6379                 # Redis port
  db: 0                      # Redis database number
  password: null             # Redis password (if required)
  ssl: false                 # Use SSL connection
  timeout: 5                 # Connection timeout in seconds
  cache_ttl_seconds: 86400   # Cache TTL (24 hours)
  max_connections: 10        # Max connections in pool
```

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_ENABLED` | bool | true | Enable Redis caching |
| `REDIS_HOST` | string | localhost | Redis hostname |
| `REDIS_PORT` | int | 6379 | Redis port |
| `REDIS_DB` | int | 0 | Redis database number (0-15) |
| `REDIS_PASSWORD` | string | (empty) | Redis password (if AUTH enabled) |
| `REDIS_SSL` | bool | false | Use SSL/TLS connection |
| `REDIS_TIMEOUT` | int | 5 | Connection timeout in seconds |
| `REDIS_CACHE_TTL` | int | 86400 | Cache TTL in seconds (24 hours) |
| `REDIS_MAX_CONNECTIONS` | int | 10 | Max connections in connection pool |

### Setup Examples

#### Local Development

```yaml
redis:
  enabled: true
  host: localhost
  port: 6379
  db: 0
  password: null
```

Or via environment:

```bash
export REDIS_ENABLED=true
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
```

#### Production with Auth

```yaml
redis:
  enabled: true
  host: redis.example.com
  port: 6380
  db: 0
  password: secure_redis_password
  ssl: true
  timeout: 10
  cache_ttl_seconds: 3600  # 1 hour cache
  max_connections: 20
```

Or via environment:

```bash
export REDIS_ENABLED=true
export REDIS_HOST=redis.example.com
export REDIS_PORT=6380
export REDIS_PASSWORD=secure_redis_password
export REDIS_SSL=true
export REDIS_TIMEOUT=10
export REDIS_CACHE_TTL=3600
export REDIS_MAX_CONNECTIONS=20
```

#### Disable Redis

```yaml
redis:
  enabled: false
```

Or via environment:

```bash
export REDIS_ENABLED=false
```

## Configuration Priority & Loading

### How Config is Loaded

1. **Application Startup**
   - `ConfigurationLoader` singleton initialized
   - Attempts to load `config.yaml` from `app/` directory
   - Falls back to environment variables if YAML parsing fails

2. **Database Initialization**
   - `get_database_url()` called by `backend/database.py`
   - Checks `config.yaml` database section first
   - Falls back to `DB_*` environment variables
   - Uses built-in defaults if neither available

3. **Redis Service**
   - `get_redis_service()` called by backend on startup
   - Checks `config.yaml` redis section first
   - Falls back to `REDIS_*` environment variables
   - Uses built-in defaults if neither available

### Override Examples

```bash
# Override YAML config with environment
export DB_TYPE=postgresql
export DB_HOST=prod-db.example.com

# OR use all environment variables (skip config.yaml)
export DB_TYPE=sqlite
export REDIS_ENABLED=false
```

## Monitoring Configuration

### Check Active Configuration

Backend logs on startup will show which configuration source is active:

```
INFO backend.database: Using database: sqlite - sqlite:////path/to/dydx_backtest.db
INFO backend.redis_service: Redis connected successfully: localhost:6379/0
```

### Troubleshooting

**PostgreSQL Connection Failed**

- Check `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` are correct
- Ensure PostgreSQL server is running and accessible
- Verify firewall allows connection to DB_PORT

**Redis Connection Failed**

- Check `REDIS_HOST`, `REDIS_PORT` are correct
- Ensure Redis server is running
- If AUTH enabled, verify `REDIS_PASSWORD` is correct
- Try disabling Redis: `REDIS_ENABLED=false`

**Database Schema Not Created**

- Backend automatically creates tables via `init_db()`
- Check file permissions for SQLite database directory
- Verify PostgreSQL user has CREATE TABLE permissions

## Performance Tuning

### Database Connection Pool

For production deployments:

```yaml
database:
  pool_size: 20           # Increase for high concurrency
  max_overflow: 30        # Allow temporary overflow
  timeout: 60             # Longer timeout for slow queries
```

### Redis Caching

For backtest result caching:

```yaml
redis:
  cache_ttl_seconds: 3600  # 1 hour for frequently-run backtests
  max_connections: 20      # Increase for parallel backtests
```

## Code Examples

### Using Configuration in Python

```python
# In backend code
from backend.config_loader import get_config_loader

loader = get_config_loader()
db_config = loader.get_database_config()
redis_config = loader.get_redis_config()

print(f"Using {db_config['type']} database at {db_config['host']}")
print(f"Redis {'enabled' if redis_config['enabled'] else 'disabled'}")
```

### Using Redis in Backend

```python
from backend.redis_service import get_redis_service

redis = get_redis_service()
if redis.enabled:
    # Cache backtest results
    redis.set_cache(f"backtest:{run_id}", results, ttl=3600)
    
    # Retrieve from cache
    cached = redis.get_cache(f"backtest:{run_id}")
```

## Docker Deployment

### Using Docker Compose

```yaml
services:
  backend:
    image: dydx-trading-bot:latest
    environment:
      DB_TYPE: postgresql
      DB_HOST: postgres
      DB_NAME: dydx_trading_bot
      DB_USER: dydx_user
      DB_PASSWORD: ${DB_PASSWORD}
      REDIS_HOST: redis
      REDIS_ENABLED: "true"
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: dydx_trading_bot
      POSTGRES_USER: dydx_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  redis:
    image: redis:7
    command: redis-server --requirepass ${REDIS_PASSWORD}
```

## Security Considerations

1. **Database Passwords**
   - Never commit `DB_PASSWORD` to version control
   - Use environment variables for production
   - Rotate passwords regularly

2. **Redis Password**
   - Use `REDIS_PASSWORD` for production Redis
   - Enable Redis SSL if available
   - Use network isolation/VPC

3. **SQLite Database**
   - Limit file permissions: `chmod 600 dydx_backtest.db`
   - Backup regularly
   - Use PostgreSQL for production

## Testing Configuration

```bash
# Test database connection
python -c "from backend.database import DATABASE_URL; print(DATABASE_URL)"

# Test Redis connection
python -c "from backend.redis_service import get_redis_service; redis = get_redis_service(); print('Redis OK' if redis.enabled else 'Redis disabled')"
```
