# dYdX Trading Bot - AI Coding Agent Instructions

**Quick Reference for AI Agents** - Essential patterns, workflows, and anti-patterns for this codebase.

## Recent Updates (Oct 21, 2025)

### Documentation Refresh for AI Coding Agents

- Reorganized for AI agent productivity: focus on **discoverable patterns** not aspirational practices
- Emphasize critical execution patterns that prevent runtime failures (atomic trades, state management, timezone handling)
- Call out workflow commands that aren't obvious from file inspection (`make backtest START=... PAIRS=ALL`)
- Include concrete anti-patterns (`config()` re-parsing, missing `await` keywords, naive timestamps)
- Frontend response structure gotchas (`response.data?.backtests` extraction)

### Backtesting Engine Improvements ✅

**Fixed Issues**:

1. **Timezone-aware datetime comparisons** - All `pd.Timestamp()` calls now use `tz='UTC'` parameter to match timezone-aware DataFrame indices. Fixes "Invalid comparison between datetime64[ns, UTC] and Timestamp" errors.
2. **Position attribute access polymorphism** - `_calculate_zscore()` now handles both `CointegrationResult` objects (dot-notation attributes) and position dictionaries (string keys) for flexible entry/exit signal processing.
3. **JWT token refresh on 401** - Frontend API client now automatically refreshes expired tokens on 401 errors, preventing unexpected redirects to login page after backtest submission.
4. **Cointegration data format** - Properly converts dictionary of Series to DataFrame before passing to `store_cointegration_results()`.

**Validation**: Backtest run successfully completed with 70 trades (52.86% win rate), confirming full trading simulation pipeline works end-to-end.

### Additional Enhancements

5. **Strategy Parameters Injection** - `BacktestEngine` accepts optional `strategy_params` dict to override config values for flexible strategy testing without modifying config.yaml
6. **Redis Caching Layer** - Backtesting results cached in Redis (configurable TTL, default 24h) to accelerate repeated analyses
7. **Database Flexibility** - Config supports SQLite (dev) and PostgreSQL (prod) with environment variable overrides (DB_TYPE, DB_HOST, etc.)

## Project Overview

Automated cointegration pairs trading bot for dYdX v4 decentralized exchange with full-stack support (Python backend, FastAPI API, React frontend).

**Key architecture facts**:

- **Paired trading bot**: All trades consist of TWO positions (base + quote markets) executed **atomically** via `BotAgent`
- **Atomic execution**: Single position failures trigger emergency cleanup to prevent orphaned positions
- **State-driven**: All persistent state stored in JSON files (`bot_agents.json`, `cointegrated_pairs.json`) - survives bot restarts
- **Configuration-first**: All bot behavior controlled via YAML flags (`app/config.yaml`) - no code changes needed for workflow variations
- **Full-stack**: Python trading engine (`app/`) + FastAPI backend (`backend/`) + React UI (`frontend/`) with PostgreSQL persistence

## How to Discover Things Quickly

### 🔍 **Finding Your Way Around**

| What you need                         | Where to look                                                                                                      | Why                                                                                |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **Understand "how pairs get traded"** | Read `app/main.py` (main loop) → `app/func_entry_pairs.py` → `app/func_bot_agent.py`                               | Discover atomic execution pattern                                                  |
| **Learn state persistence**           | Check `app/bot_agents.json` (structure) + `app/models/pair_storage.py` (code)                                      | Understand JSON-first design                                                       |
| **Add new config parameter**          | 1) Edit `app/config.yaml`, 2) Define in `app/config.py` (dataclass), 3) Export in `app/constants.py`               | Config layer separation is intentional                                             |
| **Debug: "Why no trades executed?"**  | Check Z-scores: `cat app/cointegrated_pairs.json \| jq '.pairs\[] \| {market: .base_market, zscore: .z_score}'`    | First validation before looking at code                                            |
| **Run backtest with all pairs**       | `python scripts/run_backtest.py --start 2024-09-01 --end 2024-10-01 --pairs ALL`                                   | Equivalent make command: `make backtest START=2024-09-01 END=2024-10-01 PAIRS=ALL` |
| **Test live vs backtest**             | Search for `IS_BACKTEST_MODE` in codebase - controls wallet skipping and API routing                               | Set via `--backtest` flag or env var                                               |
| **Understand API response format**    | Check `backend/main.py` response wrapper (search `"success": true`) + Frontend extraction in `frontend/src/api.ts` | All responses have nested `data` structure                                         |

### 🚨 **Common Discovery Mistakes**

```python
# ❌ WRONG: Each call reloads YAML from disk
from config import config
settings = config().botSettings.ZScoreThreshold
other_settings = config().botSettings.usdPerTrade  # SLOW: Re-parsed twice

# ✅ RIGHT: Import once at module startup
from constants import ZSCORE_THRESH, USD_PER_TRADE  # Parsed once in constants.py

# ❌ WRONG: Missing timezone breaks backtesting
trading_date = pd.Timestamp("2024-01-01")  # NAIVE timestamp
mask = df.index <= trading_date  # ERROR: tz-aware vs naive comparison

# ✅ RIGHT: Timezone-aware UTC
trading_date = pd.Timestamp("2024-01-01", tz="UTC")
mask = df.index <= trading_date  # Works! Matches DataFrame's UTC index

# ❌ WRONG: Missing await on async dYdX API
markets = get_markets(client)  # Missing await = returns coroutine object!

# ✅ RIGHT: Always await dYdX calls
markets = await get_markets(client)
```

## Common Task Patterns (When to Use What)

| Task                                  | Approach                                                                              | Key File                                    | Why                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------------------------------- |
| **Add new trading parameter**         | 1. Edit `config.yaml`, 2. Add to `config.py` dataclass, 3. Export from `constants.py` | `app/config.py`, `app/constants.py`         | Three-layer ensures type safety & no re-parsing                      |
| **Debug trades not executing**        | Check `cointegrated_pairs.json` Z-scores, verify config flags                         | `app/cointegrated_pairs.json`               | JSON state survives restarts, shows current signals                  |
| **Fix atomic execution bug**          | Review `BotAgent.open_trades()` emergency cleanup logic                               | `app/func_bot_agent.py`                     | Must handle market_2 failure without leaving orphaned market_1       |
| **Add Telegram notification**         | Use `TelegramMessenger` singleton (already initialized in main.py)                    | `app/func_messaging.py`                     | Critical errors auto-alert, non-critical logged to Loki              |
| **Optimize backtest performance**     | Adjust `statsWindow`, `ZScoreThreshold`, `maxHalfLife` in config                      | `app/config.yaml` backtesting block         | Parameter injection avoids re-running for A/B tests                  |
| **Debug API failures**                | Check rate limiting delays (0.2-0.5s between calls) and `format_number()` precision   | `app/func_private.py`, `app/func_public.py` | dYdX rejects wrong precision or too-fast API calls                   |
| **Frontend issue with API responses** | Extract `response.data` nested structure, check for 401 token refresh                 | `frontend/src/api.ts`                       | All backend responses wrapped: `{success, message, data, timestamp}` |

## Architecture & Data Flow

### Core Trading Loop (`app/main.py`)

```
setup_logging() → validate config → connect_dydx()
→ [FIND_COINTEGRATED_PAIRS] construct_market_prices() → store_cointegration_results()
→ MAIN LOOP:
    ├─ [MANAGE_EXITS] manage_trade_exits()      # Check bot_agents.json, close on Z-score cross
    └─ [PLACE_TRADES] open_positions()          # Load cointegrated_pairs.json, find Z-score triggers, create BotAgent
```

**Critical pattern**: All features are optional flags in `config.yaml` - control execution without code changes.

### Core Components (`app/`)

| File                     | Purpose                                                                          | Key Patterns                                                                                             |
| ------------------------ | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `func_cointegration.py`  | Statistical analysis (ADF, Johansen tests, Z-score calc)                         | Heavy libs (scipy/statsmodels) imported on-demand, saves to JSON via pair_storage                        |
| `func_entry_pairs.py`    | Load pairs, find Z-score triggers, spawn `BotAgent` instances                    | Read cointegrated_pairs.json, calculate current Z-scores, create BotAgent for atomic execution           |
| `func_exit_pairs.py`     | Monitor `bot_agents.json`, recalculate Z-scores, close on mean reversion         | Poll bot_agents.json for LIVE positions, check Z-score crosses zero, use reduce_only=True                |
| `func_bot_agent.py`      | Atomic paired order executor - **BOTH orders must succeed or entire pair fails** | `BotAgent.open_trades()` places market_1, then market_2; if m2 fails, emergency-close m1                 |
| `func_connections.py`    | dYdX client wrapper managing indexer/node/wallet lifecycle                       | Client has 4 components: indexer, indexer_account, node, wallet. Testnet wallet optional for backtesting |
| `func_private.py`        | Account queries, order placement, cancellations, position closure                | All functions use format_number() before placing orders. 0.2s API rate limiting delays                   |
| `func_public.py`         | Market data API (candles, markets list, prices). Always uses MAINNET indexer     | get_candles_recent() returns chronological price series. Rate limiting built-in                          |
| `models/pair_storage.py` | JSON-first persistence with CSV backward compatibility + timestamped backups     | Singleton pattern. Auto-creates pair_history/ dir. See CointegrationResult dataclass                     |
| `logging_setup.py`       | Custom logging with optional Loki integration. Direct HTTP (not logging_loki)    | Call setup_logging() FIRST in any new script. Auto-detects environment from config                       |
| `constants.py`           | Single source of truth for all config values extracted from config.yaml          | **Always import from here, never call config() in functions**. Parse once at module load                 |

### Full-Stack Architecture (Python + FastAPI + React)

**Three-layer system:**

1. **Trading Engine** (`app/`) - Python trading logic that runs independently
   - No requirement for backend to function
   - Standalone CLI: `make run` or `python app/main.py`
   - Outputs JSON state files for position tracking
2. **Backend API** (`backend/main.py`) - FastAPI server for backtest analysis & historical data
   - RESTful API: `GET /api/v1/backtests`, `POST /api/v1/backtests/run`
   - WebSocket: `ws://localhost:8888/ws/backtest/{runId}` for real-time progress
   - SQLAlchemy ORM: Stores backtest results in PostgreSQL
   - Runs on port 8888 independently from trading engine
   - Authentication: JWT tokens with `HTTPBearer` security
3. **Frontend UI** (`frontend/`) - React 19 + Vite dashboard
   - Connects to backend API for backtest UI
   - Cannot run without backend
   - Zustand state management with localStorage persistence
   - Runs on port 5173 (dev) or 3000 (prod)

**Deployment independence**: Trading bot runs successfully WITHOUT backend/frontend. Backend optional for backtest visualization.

**Backend startup**: `make backend-run` or `python -m uvicorn backend.main:app --reload --port 8888`

### Configuration System (YAML-first with Type-Safe Constants)

**Three-layer architecture**:

1. **YAML** (`app/config.yaml`): User-facing configuration with comments
2. **Dataclasses** (`app/config.py`): Type-safe hierarchical structure with defaults
3. **Module Constants** (`app/constants.py`): Singleton values extracted from config for direct imports

**Key pattern**: Always import from `constants.py`, never parse config repeatedly

```python
# ✅ CORRECT: Direct constant import from constants.py
from constants import USD_PER_TRADE, ZSCORE_THRESH, MANAGE_EXITS

# ❌ AVOID: Repeated config parsing in functions
config = config()  # Each call reloads YAML
```

**Configuration highlights**:

- **Environment modes**: `environment: "development"` vs `"production"` auto-configures logging behavior
- **Network routing**: Unified `dydx:` block OR separate `dydx_testnet:`/`dydx_mainnet:` keys
- **Market data source**: `indexer` connects to MAINNET for better data even in testnet trading
- **Feature flags**: `findCointegratedPairs`, `placeTrades`, `manageExits` control loop execution independently

### Enhanced State Management (JSON-First Persistence)

**Three persistent storage files** (all survive bot restarts - critical for position tracking):

1. **`bot_agents.json`** - Active paired positions (live trading state)

   ```json
   [
     {
       "market_1": "BTC-USD",
       "market_2": "ETH-USD",
       "hedge_ratio": 0.05,
       "z_score": 1.8,
       "half_life": 12.5,
       "order_id_m1": "abc123",
       "order_m1_size": 0.01,
       "order_m1_side": "BUY",
       "order_id_m2": "def456",
       "order_m2_size": 0.2,
       "order_m2_side": "SELL",
       "pair_status": "LIVE",  # States: FAILED, LIVE, CLOSE, ERROR
       "comments": ""
     }
   ]
   ```

2. **`cointegrated_pairs.json`** - Pair analysis results (v2.0 format with metadata)

   ```json
   {
     "metadata": {
       "analysis_timestamp": "2025-10-17T18:49:41Z",
       "total_pairs": 50,
       "confidence_threshold": 0.7
     },
     "pairs": [
       {
         "base_market": "BTC-USD",
         "quote_market": "ETH-USD",
         "hedge_ratio": 0.05,
         "half_life": 12.5,
         "p_value": 0.001,
         "confidence_score": 0.82,
         "analysis_timestamp": "2025-10-17T18:49:41Z"
       }
     ]
   }
   ```

3. **`cointegrated_pairs.csv`** - Legacy format for workflow compatibility
4. **`pair_history/`** - Timestamped backups (7-day retention, auto-cleanup)

**Storage pattern**: Always use `pair_storage` singleton from `models/pair_storage.py`

```python
from app.models.pair_storage import pair_storage

# Load with format detection (JSON preferred, CSV fallback)
pairs = pair_storage.load_pairs()

# Save (creates JSON + CSV + timestamped backup automatically)
pair_storage.save_pairs(pairs)

# High-confidence filtering
high_confidence = pair_storage.get_high_confidence_pairs()  # score >= 0.7
```

## Trading Logic Deep Dive

### BotAgent State Machine (`func_bot_agent.py`) - Atomic Paired Execution

**States**: `FAILED` | `LIVE` | `CLOSE` | `ERROR`

**Atomic execution pattern** - both orders must succeed or entire pair fails with emergency cleanup:

```python
class BotAgent:
    async def open_trades(self):
        # 1. Place market_1 order, verify FILLED
        order_m1 = await place_market_order(client, market_1, side_1, size_1)
        m1_status = await check_order_status(client, order_m1)

        # 2. Place market_2 order, verify FILLED
        order_m2 = await place_market_order(client, market_2, side_2, size_2)
        m2_status = await check_order_status(client, order_m2)

        # 3. If market_2 fails → emergency close market_1 (failsafe_price)
        if not m2_status.FILLED:
            await place_market_order(client, market_1, opposite_side, size_1, reduce_only=True)
            return {"pair_status": "FAILED"}

        # 4. Critical failures → exit(1) with Telegram alert
        return {"pair_status": "LIVE", "order_id_m1": order_m1, "order_id_m2": order_m2}
```

**Why this matters**: Single order failure in testnet (liquidity issues, invalid symbols) must not leave orphaned positions.

### Entry Logic Flow (`func_entry_pairs.py`)

**Load → Calculate Z-scores → Trigger trades** pattern:

```python
# Load cointegrated_pairs.json (via pair_storage singleton)
pairs = pair_storage.load_pairs()

# For each pair, calculate current Z-score from recent candles
for pair in pairs:
    series_1 = await get_candles_recent(client, pair.base_market)
    series_2 = await get_candles_recent(client, pair.quote_market)
    z_score = calculate_zscore(series_1, series_2, pair.hedge_ratio)

    # Entry trigger: |Z-score| >= ZSCORE_THRESH (default 1.5)
    if abs(z_score) >= ZSCORE_THRESH:
        # Determine trade sides based on Z-score direction
        base_side = "BUY" if z_score < 0 else "SELL"
        quote_side = "BUY" if z_score > 0 else "SELL"  # Opposite direction

        # Position sizing: USD_PER_TRADE converted to asset quantities using tick_size
        base_size = format_number(USD_PER_TRADE / price_1, tick_size_1)
        quote_size = format_number(hedge_ratio * base_size, tick_size_2)

        # Create BotAgent for atomic paired execution
        agent = BotAgent(client, pair.base_market, pair.quote_market, ...)
        result = await agent.open_trades()
```

**Pattern**: Use `format_number(value, tick_size)` for all exchange precision requirements.

### Exit Logic Flow (`func_exit_pairs.py`)

**Monitor → Recalculate Z-scores → Close on mean reversion** pattern:

```python
# Load active positions from bot_agents.json
with open("bot_agents.json") as f:
    active_positions = json.load(f)

# For each position, recalculate current Z-score
for position in active_positions:
    if position["pair_status"] != "LIVE":
        continue

    # Fetch recent price data for both markets
    series_1 = await get_candles_recent(client, position["market_1"])
    series_2 = await get_candles_recent(client, position["market_2"])
    z_score = calculate_zscore(series_1, series_2, position["hedge_ratio"])

    # Exit trigger: Z-score crosses zero (mean reversion)
    if CLOSE_AT_ZSCORE_CROSS and z_score crosses zero:
        # Place reduce_only=True market orders to close both positions
        order_m1 = await place_market_order(
            client,
            position["market_1"],
            opposite_side(position["order_m1_side"]),
            position["order_m1_size"],
            reduce_only=True
        )
        order_m2 = await place_market_order(
            client,
            position["market_2"],
            opposite_side(position["order_m2_side"]),
            position["order_m2_size"],
            reduce_only=True
        )
        # Update position status to CLOSE
        position["pair_status"] = "CLOSE"
```

**Critical pattern**: **Critical pattern**: Validate exchange state matches local state before closing (reconciliation step).

### Frontend Integration Pattern (`frontend/src/api.ts`)

**Centralized Axios client** for all backend communication:

```typescript
// Single API client instance - ALL backend calls go through here
class ApiClient {
  // JWT auto-injection via request interceptor
  // 401 handling: logout + redirect to /login

  async login(username: string, password: string): Promise<{ access_token }>
  async getCurrentUser(): Promise<User>
  async listBacktests(skip: number, limit: number): Promise<{ backtests: [...] }>
  async getBacktest(runId: string): Promise<BacktestData>
  async runBacktest(params: BacktestStartRequest): Promise<{ run_id }>
  async connectBacktestSocket(runId: string, token: string): WebSocket
}
```

**Frontend state management** (`frontend/src/store/auth.ts`):

```typescript
// Zustand store with localStorage persistence
useAuthStore: {
  user: User | null
  loading: boolean
  error: string | null
  login(username, password): Promise<void>   // Calls api.login + getCurrentUser
  logout(): void                              // Clears token + user
  isAuthenticated(): boolean
}
```

**Key frontend patterns**:

1. **Protected Routes**: Wrap with `<ProtectedRoute>` - redirects to /login if not authenticated
2. **Loading + Error States**: All components follow `{loading, error, data}` pattern
3. **Real-time Updates**: `useBacktestProgress` hook opens WebSocket for live progress
4. **Dark Theme**: `bg-slate-900`, `text-white`, financial colors: `text-green-400` (profit), `text-red-400` (loss)
5. **Recharts Visualization**: Responsive containers with dark theme colors (22c55e green, ef4444 red)

**Response handling** (IMPORTANT):

```typescript
// Backend response has nested structure
const response = await api.listBacktests(0, 10);
// Structure: {success, message, data: {backtests: [...]}, timestamp}
const backTests = response.data?.backtests || []; // Extract nested data
```

## Development Workflow

### dYdX Client Architecture (`func_connections.py`)

```python
class Client:
    indexer          # Market data (always mainnet for better liquidity data)
    indexer_account  # Position/balance queries (testnet/mainnet based on is_testnet)
    node             # Order placement (testnet connection regardless of trading mode)
    wallet           # Transaction signing
```

### Backend API Architecture (`backend/main.py`)

**FastAPI services** for backtest management and real-time monitoring:

```python
# Core services (dependency injection pattern)
class UserService:
    create_user(username, password) → User  # Hash passwords with bcrypt
    authenticate(username, password) → User # Verify credentials

class BacktestRunService:
    create_run(BacktestStartRequest) → BacktestRun  # Store config snapshot
    update_run_status(run_id, status) → BacktestRun
    list_runs(skip, limit, user_id) → List[BacktestRun]
    get_run(run_id) → BacktestRun

class AuditLogService:
    log_action(user_id, action, resource_id) → AuditLog  # Track all operations
```

**REST Endpoints pattern**:

```python
# POST /api/v1/auth/login → {access_token, refresh_token, user}
# GET /api/v1/users/me → {user_id, username, created_at}
# POST /api/v1/backtests/run → {run_id, status, created_at}
# GET /api/v1/backtests/{runId} → BacktestData with results/metrics
# GET /api/v1/backtests?skip=0&limit=10 → {backtests: [...], total}
```

**WebSocket real-time updates**:

```python
# ws://localhost:8888/ws/backtest/{runId}?token=JWT
# Broadcast BacktestProgressUpdate every N seconds:
#   {run_id, progress_pct, current_pair, status, timestamp}
# Frontend useBacktestProgress hook subscribes for live UI updates
```

**Database schema** (SQLAlchemy ORM):

```python
class BacktestRun:
    run_id: str                    # Unique identifier
    user_id: int                   # FK to User
    start_date: datetime
    end_date: datetime
    num_pairs: int
    config_snapshot: dict          # Store full config.yaml snapshot
    status: str                    # RUNNING, COMPLETE, FAILED
    result: BacktestResult         # OneToMany relationship

class BacktestResult:
    run_id: str
    total_pnl: float
    total_return_pct: float
    sharpe_ratio: float
    win_rate: float
    # ... 20+ performance metrics
```

**Response wrapper pattern** (ALL endpoints):

```python
{
    "success": true,
    "message": "Backtests retrieved successfully",
    "data": {
        "backtests": [...],
        "total": 42
    },
    "timestamp": "2025-10-17T15:30:00Z"
}
```

**IMPORTANT**: Frontend expects nested response.data structure - always extract `response.data?.backtests` not `response.backtests`

## Development Workflow

### Essential Setup Commands

```bash
# Initial setup (one-time)
make setup           # Create Python virtual environment
make install         # Install dependencies from requirements.txt
make config          # Create app/config.yaml from template

# Running the bot
make run             # Start bot in foreground (foreground execution)
make start           # Start bot in background (uses scripts/manage_bot.sh)
make stop            # Stop background bot
make restart         # Restart background bot
make status          # Check if bot is running
make logs            # View recent bot logs

# Code quality
make test            # Run pytest suite
make lint            # Check with flake8 + pylint
make format          # Auto-format with black
```

### Docker Deployment (Multi-stage)

```bash
# Production deployment
make docker-build           # Build optimized production image
make docker-run             # Run bot in Docker container
make docker-up              # Start with Docker Compose (full stack)
make docker-down            # Stop Docker Compose services

# Development containers
make docker-build-dev       # Build dev image with live code mounting
make docker-dev             # Start interactive dev container
make devcontainer           # Open in VS Code Dev Container (recommended)
```

### Logging & Monitoring

```bash
# Environment-specific Loki testing
make test-loki-dev          # Test Loki connectivity (development environment)
make test-loki-prod         # Test Loki connectivity (production environment)

# Full observability stack (Loki + Grafana)
make docker-up-logging      # Start Loki + Grafana on localhost:3000
# Grafana queries: {job="dydx-trading-bot", level="error"} |= "CRITICAL"
```

### Backtesting Commands

```bash
# Quick backtesting
make backtest-quick         # 1-month test with 3 pairs
make backtest-3month        # 3-month test with 10 pairs

# Custom backtesting
make backtest START=2024-01-01 END=2024-03-31 PAIRS=5

# Analysis and management
make backtest-analysis      # Comprehensive results analysis
make backtest-clean         # Clean up old results (keeps 20 most recent)
```

## Configuration & Constants

### Key Parameters (`app/config.yaml`)

```yaml
botSettings:
  ZScoreThreshold: 1.5 # Entry trigger threshold
  statsWindow: 21 # Rolling window for Z-score calculation
  maxHalfLife: 24 # Max half-life hours for cointegration
  usdPerTrade: 10.0 # Position size per trade
  usdMinCollateral: 100.0 # Required account balance
  closeAtZscoreCross: true # Exit on mean reversion
```

### Behavioral Flags

```yaml
botSettings:
  abortAllPositions: false # Close all positions on startup
  findCointegratedPairs: true # Run statistical analysis
  manageExits: true # Monitor existing positions
  placeTrades: true # Execute new trades
```

### Database & Persistence Configuration

**Three-layer persistence architecture**:

```yaml
# 1. SQLite (Development) OR PostgreSQL (Production)
database:
  type: sqlite # sqlite or postgresql | Env: DB_TYPE
  name: dydx_backtest.db # Database name | Env: DB_NAME
  user: postgres # DB username (PostgreSQL only) | Env: DB_USER
  password: "" # DB password (PostgreSQL only) | Env: DB_PASSWORD
  host: localhost # DB host | Env: DB_HOST
  port: "5432" # DB port | Env: DB_PORT
  pool_size: 5 # Connection pool size | Env: DB_POOL_SIZE
  max_overflow: 10 # Max overflow connections | Env: DB_MAX_OVERFLOW
  timeout: 30 # Query timeout in seconds | Env: DB_TIMEOUT

# 2. Redis Caching Layer (Optional - for backtest result acceleration)
redis:
  enabled: true # Enable Redis caching | Env: REDIS_ENABLED
  host: localhost # Redis hostname | Env: REDIS_HOST
  port: 6379 # Redis port | Env: REDIS_PORT
  db: 0 # Redis database number | Env: REDIS_DB
  password: null # Redis password (if required) | Env: REDIS_PASSWORD
  ssl: false # Use SSL connection | Env: REDIS_SSL
  timeout: 5 # Connection timeout in seconds | Env: REDIS_TIMEOUT
  cache_ttl_seconds: 86400 # Cache TTL (24 hours) | Env: REDIS_CACHE_TTL
  max_connections: 10 # Max connections in pool | Env: REDIS_MAX_CONNECTIONS

# 3. JSON Files (Primary - survives restarts)
# bot_agents.json, cointegrated_pairs.json, pair_history/
```

**Environment Variable Override Pattern**:

```python
# Config supports environment variable overrides for production deployments
# Example: export DB_TYPE=postgresql DB_HOST=prod-db.example.com DB_PASSWORD=secret
# Database constructor automatically detects and uses these overrides
```

**Redis Caching Strategy** (backtesting results):

```python
# Backtest results cached with 24-hour TTL
# Key format: "backtest:{run_id}"
# Enables quick re-fetching without re-running simulation
# Automatic expiration prevents stale results

from backend.redis_service import redis_service
result = await redis_service.get(f"backtest:{run_id}")  # Cache hit
if not result:
    result = await run_backtest(...)  # Cache miss - run simulation
    await redis_service.set(f"backtest:{run_id}", result, ttl=86400)
```

## Non-Obvious Workflow Commands (Not in Files)

### Backtesting Workflows That Require Shell Knowledge

```bash
# ⚠️ These patterns aren't obvious from file inspection:

# 1. Test current period (last 30 days) with ALL pairs - full market coverage
make backtest START=$(date -d '30 days ago' +%Y-%m-%d) END=$(date +%Y-%m-%d) PAIRS=ALL

# 2. Compare multiple strategies by running backtests with different configs
# Edit app/config.yaml → Run backtest → Save results → Edit config → Run again
python scripts/run_backtest.py --start 2024-09-01 --end 2024-10-01 --pairs 10
# Then analyze: python scripts/analyze_backtest_results.py --compare

# 3. Validate code changes without modifying state files
python app/main.py --dry-run  # Tests connection and config without trading

# 4. Debug: Check why Z-scores aren't triggering trades
cat app/cointegrated_pairs.json | jq '.pairs[] | select(.confidence_score >= 0.7) | {base: .base_market, quote: .quote_market, zscore: .current_zscore}'

# 5. Emergency position closure (critical!)
python scripts/close_open_positions.py  # Closes ALL positions immediately

# 6. Development container for isolation (recommended over local install)
make devcontainer  # Opens full VS Code dev environment
```

### Database & Persistence Patterns

```bash
# These are NOT obvious from code inspection:

# 1. Database migration workflow
make db-upgrade    # Apply pending migrations
make db-downgrade  # Revert last migration
make db-current    # Check current schema version

# 2. Three-layer persistence (all important):
# - JSON files (app/*.json) - Primary state, survives restarts
# - PostgreSQL (backend) - Backtest results history, optional
# - Redis (backend) - Cache layer, accelerates repeated queries

# 3. Configure all three layers via environment variables
export DB_TYPE=postgresql DB_HOST=prod-db.com DB_PASSWORD=secret
export REDIS_ENABLED=true REDIS_HOST=cache.example.com
# Now run: python app/main.py

# 4. Development uses SQLite (no setup needed), Production uses PostgreSQL
# This is auto-detected by config.yaml database.type parameter
```

## Critical Developer Patterns

### Market Data Always Uses MAINNET Indexer

**Important**: Even when `is_testnet: true`, market data comes from MAINNET indexer for better liquidity data:

```python
from constants import MARKET_DATA_MODE, INDEXER_ENDPOINT_MAINNET

# Market data ALWAYS uses mainnet indexer
indexer = IndexerClient(INDEXER_ENDPOINT_MAINNET)

# Account queries use testnet/mainnet based on config
indexer_account = IndexerClient(INDEXER_ACCOUNT_ENDPOINT)  # Testnet if is_testnet=true
```

### Format Numbers BEFORE Every Exchange Call

**All numeric values sent to dYdX must match exchange tick_size/stepSize precision**:

```python
from func_utils import format_number

# ✅ CORRECT: Format with market metadata
base_size = format_number(USD_PER_TRADE / base_price, base_step_size)
quote_size = format_number(hedge_ratio * base_size, quote_step_size)

# Get tick sizes from markets metadata
markets = await get_markets(client)
tick_size = markets["markets"]["BTC-USD"]["tickSize"]
accept_price = format_number(45123.456789, tick_size)

# Place order with formatted values
await place_market_order(client, "BTC-USD", "BUY", base_size, accept_price, reduce_only=False)
```

**Why**: Exchange rejects orders with incorrect precision. `format_number(value, reference)` matches decimal places of reference number.

### API Rate Limiting Pattern

**All API calls have built-in 0.2-0.5s delays. Never remove them**:

```python
import time

# func_public.py pattern - automatic delay
async def get_candles_recent(client, market):
    # ... fetch data ...
    time.sleep(0.2)  # Protect API - REQUIRED
    return candles

# func_private.py pattern - manual delay between critical calls
order_m1 = await place_market_order(...)
time.sleep(0.5)  # MUST wait before market_2 order
order_m2 = await place_market_order(...)
```

### Atomic Paired Execution Pattern (BotAgent)

**Critical**: If market_2 order fails, emergency-close market_1 with failsafe price:

```python
class BotAgent:
    async def open_trades(self):
        # 1. Place and verify market_1
        order_m1 = await place_market_order(client, market_1, side_1, size_1, price_1, False)

        # 2. Verify market_1 filled
        m1_status = await check_order_status(client, order_m1)
        if not m1_status.get("FILLED"):
            logger.error("Market 1 order not filled")
            return {"pair_status": "FAILED"}

        # 3. Place market_2
        order_m2 = await place_market_order(client, market_2, side_2, size_2, price_2, False)

        # 4. If market_2 fails → CLOSE market_1 immediately with failsafe_price
        m2_status = await check_order_status(client, order_m2)
        if not m2_status.get("FILLED"):
            logger.error("Market 2 failed, emergency closing market 1")
            await place_market_order(
                client, market_1, opposite_side(side_1), size_1,
                failsafe_price_m1, reduce_only=True
            )
            return {"pair_status": "FAILED"}

        # 5. Both succeeded
        return {"pair_status": "LIVE", "order_id_m1": order_m1, "order_id_m2": order_m2}
```

### Wallet Optional for Backtesting

**Backtesting mode skips wallet creation (no signing needed)**:

```python
async def connect_dydx():
    # ... create indexer, indexer_account, node ...

    wallet = None
    if not IS_BACKTEST_MODE:
        try:
            wallet = Wallet.from_mnemonic(MNEMONIC)
        except Exception:
            logger.warning("Failed to create wallet (backtesting mode?)")

    client = Client(indexer, indexer_account, node, wallet)
    return client
```

### Singleton Pattern for Configuration & Storage

**Both config and storage follow Python singleton - instantiate once, reuse everywhere**:

```python
from config import config  # Singleton - loads YAML once
from models.pair_storage import pair_storage  # Singleton - manages JSON/CSV

# Call once at module startup in constants.py
_CONFIG = config()
ZSCORE_THRESH = _CONFIG.botSettings.ZScoreThreshold

# Use anywhere without re-parsing
from constants import ZSCORE_THRESH
if abs(z_score) >= ZSCORE_THRESH:
    # Trade

# Storage singleton - automatically handles JSON + CSV + backups
pairs = pair_storage.load_pairs()  # Try JSON first, fallback to CSV
pair_storage.save_pairs(pairs)     # Auto-creates timestamped backup
```

### Logging Initialization (CRITICAL - Must Be First)

**Always call `setup_logging()` FIRST, before any logging calls**:

```python
from logging_setup import setup_logging
import logging

setup_logging()  # ⚠️ MUST be first line in main() - initializes Loki, console, file handlers
logger = logging.getLogger(__name__)
logger.info("Script started")

# Bad pattern - don't do this:
logger = logging.getLogger(__name__)
setup_logging()  # Too late - logging already configured incorrectly
```

**Why this matters**: Loki integration, log levels, and environment detection all depend on setup_logging() running first.

### Module Constants Pattern

**Always import from `constants.py`, never parse config in functions**:

```python
# ✅ CORRECT
from constants import USD_PER_TRADE, ZSCORE_THRESH, MANAGE_EXITS
usd_amount = USD_PER_TRADE  # Direct access, no parsing

# ❌ AVOID
from config import config
cfg = config()  # Reload YAML every time function is called
```

### Data Storage Pattern

**Always use `pair_storage` singleton for persistence**:

```python
from models.pair_storage import pair_storage
pairs = pair_storage.load_pairs()      # JSON preferred, CSV fallback
pair_storage.save_pairs(pairs)         # Auto-creates backups
```

### Exchange Precision Pattern

**Always format numbers before sending to dYdX**:

```python
from func_utils import format_number
size = format_number(amount_usd / price, tick_size)  # Format to exchange tick_size
```

### Error Handling Pattern

**Critical errors: log, alert Telegram, then exit(1). Never continue with orphaned state**:

```python
try:
    result = await some_critical_operation()
except Exception as e:
    logger.error("Critical failure: %s", e)
    messenger.send_error_message("Operation Failed", str(e), is_critical=True)
    exit(1)  # Don't allow bot to continue with orphaned state

# For non-critical errors, use try-except-continue:
try:
    position = await check_position(client, market)
except Exception as e:
    logger.warning("Could not check position, skipping: %s", e)
    continue  # Move to next position
```

### Async Pattern - All dYdX API Calls Are Async

**All dYdX API calls use async/await pattern - use await consistently**:

````python
async def some_function(client):
    # ✅ Use await for ALL client calls
    markets = await get_markets(client)
    order = await place_market_order(client, market, side, size)
    positions = await get_open_positions(client)

    # ❌ DON'T do this - blocking calls in async function
    # order = place_market_order(client, market, side, size)  # Missing await!
```## Logging & Monitoring (`logging_setup.py`)

### Custom Loki Integration

Uses direct HTTP requests (not `logging_loki` library which fails silently). Log levels sent as stream labels for Grafana filtering.

```python
# Grafana queries (requires Loki configured):
{job="dydx-trading-bot", level="error"} |= "CRITICAL"
{job="dydx-trading-bot"} | level="error" | pattern "<_>"
````

### Production Logging Pattern

- **Console handler**: Always active for development/debugging
- **Loki handler**: Optional remote aggregation (requires auth in production)
- **Environment detection**: Auto-configures based on `environment: "production"` in config.yaml
- **Critical pattern**: Call `setup_logging()` BEFORE any logging calls in new scripts

## Emergency & Debugging Tools

### Critical Scripts (`scripts/`)

```bash
python scripts/close_open_positions.py      # Emergency position closure
python scripts/fast_cointegration.py --n 30 # Quick statistical analysis
python scripts/request_testnet_usdc.py      # Testnet USDC funding
python scripts/test_loki.py [env]           # Test log aggregation connectivity
```

### Enhanced Monitoring & Validation

```bash
# State inspection (JSON-first with confidence metrics)
cat app/cointegrated_pairs.json | jq '.metadata'           # Analysis summary
cat app/cointegrated_pairs.json | jq '.pairs[].confidence_score' # Confidence scores
cat app/bot_agents.json | jq length                        # Active position count

# Storage system validation
python -c "from app.models.pair_storage import pair_storage; print(pair_storage.get_storage_info())"

# Advanced logging
make test-loki-dev test-loki-prod          # Environment-specific Loki tests
make docker-up-logging                     # Full observability stack (Loki + Grafana)
# Access Grafana: http://localhost:3000 (admin/admin)
```

### Development Container Workflow

```bash
# Recommended: VS Code Dev Container (full IDE integration)
make devcontainer                          # Open in VS Code Dev Container

# Alternative: Manual dev container management
make devcontainer-up                       # Start dev container
make devcontainer-shell                    # Interactive shell
make devcontainer-logs                     # View container logs
```

### Jurisdiction & Connectivity

- **Startup check**: Bot tests market data access (HTTP 403 = geographical restriction)
- **Rate limiting**: Built-in delays prevent API throttling (0.2-0.5s between calls)
- **Testnet safety**: Use `is_testnet: true` + environment detection for safe testing
- **Health checks**: Docker containers include automated health validation

## Backtesting System

### Core Backtesting Components

```
## Backtesting System

### Core Backtesting Components

```

app/func_backtesting.py # BacktestEngine simulation engine
app/models/backtest_models.py # BacktestResult, BacktestTrade dataclasses
app/models/backtest_storage.py # JSON storage with singleton pattern
scripts/run_backtest.py # Main backtesting execution script
scripts/analyze_backtest_results.py # Performance analysis and reporting

````

### Backtesting Workflow Commands

```bash
# Quick backtesting
make backtest-quick                    # 1-month test with 3 pairs
make backtest-3month                   # 3-month test with 10 pairs

# Custom backtesting
make backtest START=2024-01-01 END=2024-03-31 PAIRS=5

# Analysis and management
make backtest-analysis                 # Comprehensive results analysis
make backtest-clean                    # Clean up old results (keeps 20 most recent)

# Direct script usage
python scripts/run_backtest.py --start 2024-01-01 --end 2024-03-31 --pairs 10
python scripts/analyze_backtest_results.py --top 5 --chart --export results.csv
````

### Backtesting Configuration (`app/config.yaml`)

```yaml
backtesting:
  # Historical data settings
  candleResolution: "1HOUR" # 1MIN, 5MINS, 15MINS, 1HOUR, 4HOURS, 1DAY
  maxHistoryDays: 90 # Maximum lookback period

  # Simulation parameters
  startingBalance: 1000.0 # USD starting capital for simulation
  transactionFee: 0.0005 # 0.05% per trade (dYdX maker fee)
  slippage: 0.001 # 0.1% estimated slippage

  # Analysis settings
  benchmarkSymbol: "BTC-USD" # Benchmark for Sharpe ratio calculation
  riskFreeRate: 0.02 # Annual risk-free rate (2%)
```

### Backtesting Patterns

- **Uses existing trading logic**: Same cointegration analysis and Z-score calculations as live trading
- **Testnet client**: Always connects via testnet to avoid mainnet API costs during backtesting
- **JSON-first storage**: Results stored in `app/backtest_results/` with timestamped backups
- **Performance metrics**: PnL, Sharpe ratio, win rate, drawdown, profit factor, trade duration
- **Analysis tools**: CSV export, matplotlib charts, aggregate statistics across multiple backtests

````

### Backtesting Workflow Commands

```bash
# Quick backtesting
make backtest-quick                    # 1-month test with 3 pairs
make backtest-3month                   # 3-month test with 10 pairs

# Custom backtesting
make backtest START=2024-01-01 END=2024-03-31 PAIRS=5

# Analysis and management
make backtest-analysis                 # Comprehensive results analysis
make backtest-clean                   # Clean up old results (keeps 20 most recent)

# Direct script usage
python scripts/run_backtest.py --start 2024-01-01 --end 2024-03-31 --pairs 10
python scripts/analyze_backtest_results.py --top 5 --chart --export results.csv
````

### Backtesting Configuration (`app/config.yaml`)

```yaml
backtesting:
  # Historical data settings
  candleResolution: "1HOUR" # 1MIN, 5MINS, 15MINS, 1HOUR, 4HOURS, 1DAY
  maxHistoryDays: 90 # Maximum lookback period

  # Simulation parameters
  startingBalance: 1000.0 # USD starting capital for simulation
  transactionFee: 0.0005 # 0.05% per trade (dYdX maker fee)
  slippage: 0.001 # 0.1% estimated slippage

  # Analysis settings
  benchmarkSymbol: "BTC-USD" # Benchmark for Sharpe ratio calculation
  riskFreeRate: 0.02 # Annual risk-free rate (2%)
```

### Backtesting Patterns

- **Uses existing trading logic**: Same cointegration analysis and Z-score calculations as live trading
- **Testnet client**: Always connects via testnet to avoid mainnet API costs during backtesting
- **JSON-first storage**: Results stored in `app/backtest_results/` with timestamped backups
- **Performance metrics**: PnL, Sharpe ratio, win rate, drawdown, profit factor, trade duration
- **Analysis tools**: CSV export, matplotlib charts, aggregate statistics across multiple backtests

### BacktestEngine Architecture & Strategy Parameter Injection

**Key Feature**: BacktestEngine supports optional `strategy_params` dict to override config.yaml without file modifications:

```python
# Example: Test custom parameters without modifying config.yaml
from app.func_backtesting import BacktestEngine

engine = BacktestEngine(
    client=client,
    config=config,
    run_id="test-123",
    strategy_params={
        'zscore_threshold': 2.0,      # Override default 1.5
        'usd_per_trade': 20.0,         # Override default 25.0
        'stats_window': 21,            # Override default 14
        'close_at_zscore_cross': True,
        'transaction_fee': 0.0005,
        'slippage': 0.001
    },
    progress_callback=async_progress_callback  # Optional real-time updates
)

results = await engine.run_backtest(
    start_date="2024-01-01",
    end_date="2024-03-31",
    pairs=["BTC-USD", "ETH-USD"]
)
```

**Parameter precedence** (highest to lowest):

1. `strategy_params` dict (explicit overrides)
2. `config.yaml` values (defaults)

**Use cases**:

- A/B testing different threshold values
- Sensitivity analysis on USD per trade
- Batch backtesting with parameter sweeps
- No code changes needed for strategy variations

### Backtesting Critical Patterns (IMPORTANT)

**1. Timezone-Aware Datetime Comparisons**

```python
# ✅ CORRECT: All pd.Timestamp() must be timezone-aware
trading_timestamp = pd.Timestamp(trading_date, tz="UTC")  # Matches DataFrame index
mask = df.index <= trading_timestamp  # Safe comparison

# ❌ WRONG: Naive Timestamp causes "Invalid comparison" error
trading_timestamp = pd.Timestamp(trading_date)  # No tz parameter = NAIVE
mask = df.index <= trading_timestamp  # FAILS: tz-aware vs naive
```

**Why**: Backtesting DataFrames have timezone-aware UTC indices from dYdX API. All timestamp comparisons must match this.

**2. Polymorphic Z-Score Calculation**
The `_calculate_zscore()` method handles TWO input types:

```python
# Entry signals: CointegrationResult objects (attributes)
pair = CointegrationResult(base_market="BTC-USD", quote_market="ETH-USD", ...)
z_score = self._calculate_zscore(pair, prices, date)  # pair.base_market works

# Exit signals: Position dictionaries (string keys)
position = {"market_1": "BTC-USD", "market_2": "ETH-USD", "hedge_ratio": 0.05}
fake_pair = {"base_market": position["market_1"], ...}
z_score = self._calculate_zscore(fake_pair, prices, date)  # Dict with get() fallback
```

Implementation detects type and accesses appropriately:

```python
if isinstance(pair, dict):
    market_1 = pair.get("base_market") or pair.get("market_1")  # Try both keys
    market_2 = pair.get("quote_market") or pair.get("market_2")
else:
    market_1 = pair.base_market  # CointegrationResult attribute
    market_2 = pair.quote_market
```

**3. Cointegration Data Format Conversion**

```python
# ✅ CORRECT: Convert dict of Series to DataFrame
analysis_data = {"BTC-USD": series1, "ETH-USD": series2, ...}
analysis_df = pd.DataFrame(analysis_data)  # Convert before passing
store_cointegration_results(analysis_df)

# ❌ WRONG: Passing dict directly causes "'dict' object has no attribute 'columns'"
store_cointegration_results(analysis_data)  # FAILS
```

**4. Frontend JWT Token Refresh**

```typescript
// Frontend API client auto-handles 401 errors
if (status === 401) {
  try {
    await this.client.get("/api/v1/users/me"); // Check if session valid
    if (error.config) {
      return this.client(error.config); // Retry original request
    }
  } catch (refreshError) {
    this.logout();
    window.location.href = "/login"; // Truly invalid, redirect
  }
}
```

This prevents "redirect to login after Run Backtest click" issue.

## Integration Points & Dependencies

**External Services** (these require configuration):

- **dYdX v4 Mainnet/Testnet**: `dydx-v4-client` library, configured via `app/config.yaml` `dydx:` block

  - Indexer (market data) always uses MAINNET for liquidity (even in testnet trading mode!)
  - Node/Wallet use testnet/mainnet based on `is_testnet` flag
  - Testnet funding: `python scripts/request_testnet_usdc.py`

- **Telegram Bot**: Push notifications for trades/errors, configured via `telegram:` block in config

  - Token generated via Telegram BotFather
  - Critical: alerts are ONE-WAY (bot→you), not interactive

- **Grafana Loki** (optional): Real-time log aggregation for production monitoring
  - Configured via `logging.loki:` block
  - Uses direct HTTP API (not `logging_loki` library due to silent failures)
  - Query example: `{job="dydx-trading-bot", level="error"}`

**Internal Systems** (no external config needed):

- **Statistical Analysis**: `scipy`, `statsmodels` imported on-demand (only when `findCointegratedPairs` runs)
- **Backend API**: FastAPI on port 8888, independent from trading engine, stores backtests in PostgreSQL
- **Redis Cache**: Optional acceleration layer, 24h TTL for backtest results (env: `REDIS_*` vars)
- **React Frontend**: Connects only to backend API, cannot run standalone

## Key Data Models & Patterns

### Core Data Structures (`app/models/`)

**CointegrationResult** - Statistical pair analysis results:

```python
# Dataclass from pair_storage.py
@dataclass
class CointegrationResult:
    base_market: str          # e.g., "BTC-USD"
    quote_market: str         # e.g., "ETH-USD"
    hedge_ratio: float        # Beta coefficient from regression
    half_life: float          # Mean reversion period (hours)
    p_value: float            # Statistical significance (ADF/Johansen)
    confidence_score: float   # 0-1 (score >= 0.7 = tradeable)
    analysis_timestamp: str   # ISO format timestamp
```

**BacktestTrade** - Individual trade execution record:

```python
# From backtest_models.py
@dataclass
class BacktestTrade:
    trade_id: str
    entry_timestamp: datetime  # When position opened
    exit_timestamp: datetime   # When position closed
    market_1: str              # Base market
    market_2: str              # Quote market
    entry_zscore: float        # Z-score at entry
    exit_zscore: float         # Z-score at exit
    pnl_usd: float            # Profit/loss in USD
    pnl_pct: float            # Return percentage
    trade_duration_hours: float
    win: bool                  # True if pnl_usd > 0
```

**BacktestResult** - Complete simulation results:

```python
# From backtest_models.py & database.py
@dataclass
class BacktestResult:
    run_id: str
    total_trades: int
    total_pnl: float
    total_return_pct: float
    sharpe_ratio: float
    win_rate: float            # % of winning trades
    max_drawdown_pct: float
    profit_factor: float       # Gross wins / Gross losses
    avg_trade_duration_hours: float
    trades: List[BacktestTrade]
```

### State File Formats

**Position State** (`bot_agents.json`):

```json
[
  {
    "market_1": "BTC-USD",
    "market_2": "ETH-USD",
    "hedge_ratio": 0.05,
    "z_score": 1.8,
    "pair_status": "LIVE",      # FAILED, LIVE, CLOSE, ERROR
    "order_id_m1": "abc123",
    "order_id_m2": "def456",
    "order_m1_size": 0.01,
    "order_m1_side": "BUY",
    "order_m2_size": 0.2,
    "order_m2_side": "SELL"
  }
]
```

**Pair Analysis** (`cointegrated_pairs.json` - v2.0 format):

```json
{
  "metadata": {
    "analysis_timestamp": "2025-10-20T18:49:41Z",
    "total_pairs": 50,
    "confidence_threshold": 0.7
  },
  "pairs": [
    {
      "base_market": "BTC-USD",
      "quote_market": "ETH-USD",
      "hedge_ratio": 0.05,
      "half_life": 12.5,
      "p_value": 0.001,
      "confidence_score": 0.82,
      "analysis_timestamp": "2025-10-20T18:49:41Z"
    }
  ]
}
```

## Quick Reference: File Locations & Purposes

| Location                        | Purpose                                                  | Key Pattern                                                     |
| ------------------------------- | -------------------------------------------------------- | --------------------------------------------------------------- |
| `app/main.py`                   | Entry point - orchestrates full trading loop             | `setup_logging()` FIRST, then config, then loop                 |
| `app/config.yaml`               | YAML-based configuration - always use as source of truth | Environment vars override YAML values                           |
| `app/constants.py`              | Singleton config values for imports - NO re-parsing      | Import here, use everywhere without calling `config()`          |
| `app/models/pair_storage.py`    | JSON/CSV persistence singleton for pairs                 | `pair_storage.load_pairs()` tries JSON first, falls back to CSV |
| `app/models/backtest_models.py` | Dataclasses for backtest data                            | Use `BacktestResult` for complete results object                |
| `app/func_backtesting.py`       | BacktestEngine simulation engine                         | Accepts `strategy_params` to override config values             |
| `backend/main.py`               | FastAPI server on port 8888                              | Response wrapper: `{success, message, data, timestamp}`         |
| `backend/redis_service.py`      | Redis caching layer for backtest results                 | TTL: 24h, enables fast re-fetching                              |
| `frontend/src/api.ts`           | Centralized Axios client - ALL backend calls here        | Extracts `response.data` nested structure                       |
| `frontend/src/store/auth.ts`    | Zustand auth store with localStorage persistence         | `useAuthStore()` - no selectors needed                          |
