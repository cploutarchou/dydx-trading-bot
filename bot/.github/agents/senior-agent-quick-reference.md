# Senior Bot Project Manager - Quick Reference

## 🚀 Immediate Commands

### Start the System
```bash
# Development environment
make setup                    # Install dependencies
make dev                      # Start API with hot-reload

# Production-style
make local-api                # Start canonical API server (port 8889)
make local-worker             # Start Celery worker for backtests
make local-bot                # Start bot instance runtime
make local-flower             # Start Celery Flower UI (port 5555)
```

### Testing & Validation
```bash
make test                       # Full test suite
make test-execution-safety      # Order/position safety tests
make preflight-testnet          # Standard preflight checks
make preflight-testnet-strict   # Release-grade validation
```

## 📁 Project Structure

```
bot/
├── src/
│   ├── api/                          # FastAPI server & endpoints
│   │   ├── server.py                 # Canonical API app
│   │   ├── start_api.py              # API launcher
│   │   ├── websocket_server.py      # Real-time WebSocket
│   │   └── v1/                       # API routers
│   │       ├── auth/                 # Authentication
│   │       ├── monitoring.py         # Health & metrics
│   │       ├── strategies.py         # Strategy CRUD
│   │       └── celery_admin.py       # Worker management
│   │
│   ├── trading/                     # Trading core
│   │   ├── bot_agent.py             # Main trading agent
│   │   ├── account_manager.py       # Position & account mgmt
│   │   ├── dydx_client.py           # Exchange integration
│   │   ├── market_data.py           # Price data & analysis
│   │   ├── position_manager.py      # Trade execution
│   │   ├── arbitrage_observability.py # Decision audit trail
│   │   ├── pair_priority.py         # Pair ranking engine
│   │   ├── realtime_data_service.py # Real-time feeds
│   │   └── trade_persistence.py     # Live trade records
│   │
│   ├── infrastructure/              # Backend infrastructure
│   │   ├── database.py              # PostgreSQL connection
│   │   ├── event_bus.py             # Event publishing
│   │   ├── cache_lock.py            # Distributed locking
│   │   ├── persistence/             # Repository patterns
│   │   ├── workers/                 # Celery tasks
│   │   └── storage/                 # ClickHouse, MinIO adapters
│   │
│   └── shared/                      # Shared utilities
│       ├── env_loader.py            # Environment loading
│       ├── credentials_cipher.py   # AES-256 encryption
│       └── logging_setup.py        # Logging configuration
│
├── config/                          # Configuration files
│   └── config.py                    # Main config loader
│
├── migrations/                     # Database migrations
│   └── postgres/                    # Alembic migrations
│
├── tests/                          # Test suite
│   ├── test_auth_*.py              # Authentication tests
│   ├── test_bot_instance_manager.py # Lifecycle tests
│   ├── test_execution_safety.py    # Trading safety tests
│   └── ...
│
├── .github/                        # GitHub configuration
│   ├── agents/                     # AI agent definitions
│   │   └── senior-bot-project-manager.agent.md  # ← This agent
│   └── instructions/              # Task-specific instructions
│
├── main.py                         # Legacy entrypoint
├── worker_entrypoint.py            # Container worker entry
├── bot_instance_manager.py        # Process lifecycle manager
├── main_instance.py                # Worker runtime
├── openapi.json                    # API schema
├── README.md                       # Main documentation
└── tasks.md                        # Task workflows
```

## 🎯 Critical Safety Rules

### ❌ NEVER Do
- Use `time.sleep()` in async workflows (use `asyncio.sleep()`)
- Call `sys.exit()` in library code (raise exceptions instead)
- Import config before `load_repo_env(__file__)`
- Use direct subprocess management (use `BotInstanceManager`)
- Commit real secrets or credentials

### ✅ ALWAYS Do
- Call `load_repo_env(__file__)` first in entry points
- Use `BotInstanceManager` for lifecycle operations
- Preserve `api_response(...)` envelope format
- Maintain service token overlap support
- Update documentation with code changes

## 🔐 Environment Variables

### Database
- `BOT_DATABASE_URL` / `DATABASE_URL` / `POSTGRES_*`
- `BOT_DB_CUTOVER_MODE=dedicated` (preferred)

### Cache & Messaging
- `CELERY_BROKER_URL` / `REDIS_URL` / `VALKEY_URL`
- `CELERY_RESULT_BACKEND`
- `NATS_URL` / `NATS_MONITORING_URL`

### Authentication
- `BOT_API_TOKEN` / `BOT_API_TOKEN_PREVIOUS` / `BOT_API_TOKENS`
- `API_BYPASS_AUTH=true` (dev only)

### Encryption
- `BOT_CREDENTIALS_ENCRYPTION_KEY` (base64, 32 bytes)
- `BOT_CREDENTIALS_ENCRYPTION_KEY_FILE` (file path)
- `BOT_CREDENTIALS_ENCRYPTION_REQUIRED=true` (enforce encryption)

### Analytics & Storage
- `CLICKHOUSE_URL` / `CLICKHOUSE_HOST` / `CLICKHOUSE_PORT`
- `BACKTEST_CLICKHOUSE_WRITES_ENABLED=false`
- `MINIO_ENDPOINT` / `MINIO_BUCKET` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`
- `BACKTEST_MINIO_ARTIFACTS_ENABLED=false`

## 🏗️ Key Components

### API Layer
- **FastAPI** on port `8889`
- **WebSocket** real-time updates
- **REST endpoints** for bot/backtest management
- **Authentication** via JWT and service tokens

### Bot Manager
- Process lifecycle: create/start/stop/status/delete
- Instance isolation and management
- State persistence to PostgreSQL
- Subprocess monitoring and cleanup

### Trading Engine
- **Arbitrage detection** via cointegration analysis
- **Position management** with risk controls
- **Order execution** with dYdX v4 API
- **Market data** real-time and historical
- **Strategy runtime** with configurable parameters

### Backtest System
- **Celery-backed** asynchronous execution
- **Multi-queue** support (backtests, default, high_priority, scheduled)
- **Progress tracking** with throttled DB writes
- **Artifact storage** via MinIO/S3 (optional)
- **Analytics writes** to ClickHouse (optional)

## 📊 Monitoring & Health

### Health Endpoints
- `GET /health` - Basic health check
- `GET /ready` - Readiness (200 only when bot manager available)
- `GET /api/v1/monitoring/health` - Detailed health metrics

### Key Metrics
- **Strategy resolution drift**: `/api/v1/runtime/strategy-resolution-metrics`
- **Backtest sync health**: `/api/v1/backtests/sync-health`
- **Celery monitoring**: `/api/v1/celery/tasks` and Flower UI
- **Worker metrics**: ClickHouse `worker_metrics` table (when enabled)

### Logging
- **Application logs**: Structured logging via Loguru
- **Instance logs**: `bot_states/bot_<instance_id>.log`
- **Backtest logs**: `bot_states/backtest_<run_id>.log`
- **Telegram alerts**: Critical errors and startup/shutdown events

## 🔄 Common Workflows

### 1. Add New Trading Strategy
```bash
# Create strategy file
# → src/trading/strategies/my_strategy.py

# Add to domain models
# → src/infrastructure/domain/bot_api_models.py

# Create tests
# → tests/test_my_strategy.py

# Run validation
make test-execution-safety
make preflight-testnet
```

### 2. Create New API Endpoint
```bash
# Add route to appropriate router
# → src/api/v1/strategies.py (or new router)

# Add Pydantic models
# → src/infrastructure/domain/bot_api_models.py

# Add OpenAPI docs
# → Update openapi.json

# Test endpoint
make test-auth
pytest tests/test_new_endpoint.py -v
```

### 3. Database Migration
```bash
# Create migration
alembic revision --autogenerate -m "add_new_table"

# Review migration
# → migrations/versions/add_new_table.py

# Test migration
alembic upgrade head
alembic downgrade -1

# Verify with tests
make test
```

### 4. Incident Response
```bash
# Check system status
curl http://localhost:8889/ready
curl http://localhost:8889/health

# Check logs
tail -f bot_states/bot_*.log
tail -f bot_states/backtest_*.log

# Check Celery
docker exec <container> celery -A src.infrastructure.workers.celery_app inspect active

# Check PostgreSQL
psql $BOT_DATABASE_URL -c "SELECT * FROM bot_instances.config;"
```

## 🧪 Testing Matrix

### Unit Tests
- Trading logic and calculations
- API request/response handling
- Database models and queries
- Utility functions and helpers

### Integration Tests
- API endpoint contracts
- Authentication and authorization
- Bot lifecycle management
- Database interactions
- Celery task execution

### Safety Tests
- Order execution safety
- Position management
- Risk controls validation
- Emergency cleanup procedures
- Exception handling quality

### Preflight Tests
- Testnet compatibility
- Production readiness
- Configuration validation
- Environment checks

## 🚨 Emergency Procedures

### Stop All Trading
```bash
# Stop bot instances via API
curl -X POST http://localhost:8889/api/v1/bots/stop-all \
  -H "Authorization: Bearer $BOT_API_TOKEN"

# Or kill processes directly
pkill -f main_instance.py
pkill -f bot_instance_manager.py
```

### Rollback Database
```bash
# Check current migration
alembic current

# Downgrade one migration
alembic downgrade -1

# Restore from backup
psql $BOT_DATABASE_URL < backup.sql
```

### Credential Rotation
```bash
# Generate new encryption key
make credentials-keygen

# Set new key (backup old key first!)
export BOT_CREDENTIALS_ENCRYPTION_KEY="<new-base64-key>"

# Re-encrypt existing credentials
make encrypt-bot-credentials

# Rotate service tokens
# Update BOT_API_TOKEN, BOT_API_TOKEN_PREVIOUS, BOT_API_TOKENS
```

## 📚 Key Documentation

- **Architecture**: `docs/OPERATIONS.md`
- **API Contract**: `openapi.json`
- **Development**: `README.md`
- **Task Workflows**: `tasks.md`
- **Safety Rules**: `AGENTS.md`
- **Trading Flows**: `docs/BOT_FLOWS.md`

## 🎓 Decision Framework

### When in Doubt...
1. **Safety First**: Does this protect against trading losses?
2. **Data Integrity**: Could this corrupt or lose data?
3. **Reliability**: Could this cause system downtime?
4. **Documentation**: Is this properly documented?
5. **Testing**: Are there comprehensive tests?

### Risk Levels
- **🔴 CRITICAL**: Trading losses, data loss, security breach → **STOP, REVIEW, APPROVE**
- **🟡 HIGH**: System downtime, performance issues → **THOROUGH TESTING REQUIRED**
- **🟢 MEDIUM**: Bug fixes, minor features → **STANDARD REVIEW**
- **🔵 LOW**: Documentation, cosmetic changes → **FAST TRACK**

## 🔗 Important Links

- **API Server**: `http://localhost:8889`
- **Flower UI**: `http://localhost:5555`
- **Swagger Docs**: `http://localhost:8889/docs`
- **Redoc**: `http://localhost:8889/redoc`
- **Health Check**: `http://localhost:8889/health`
- **Readiness**: `http://localhost:8889/ready`

## 💡 Pro Tips

1. **Always start Celery worker before API** for backtest functionality
2. **Use `make local-api`** instead of direct `uvicorn` for proper config loading
3. **Check `AGENTS.md`** for project-specific constraints and patterns
4. **Run preflight tests** before any production deployment
5. **Monitor strategy resolution drift** via `/runtime/strategy-resolution-metrics`
6. **Use DB-first approach** - config comes from `bot_instances.config` table
7. **Leverage existing patterns** - don't reinvent the wheel

---

**Remember**: Every change is live-trading-facing. Default to caution.