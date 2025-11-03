# dYdX Trading Bot - AI Coding Agent Instructions

**Multi-Component dYdX Trading System** - Complete guide for AI agents working across the trading bot engine, Go API backend, and React frontend.

## System Overview

**Three-tier architecture** for statistical arbitrage trading on dYdX v4:

### 🐍 `bot/` - Python Trading Engine (Core)

- **Standalone execution**: `python bot/main.py` runs autonomous trading
- **API-controlled instances**: FastAPI server manages multiple bot processes
- **Paired trading**: TWO positions (base + quote) executed atomically via `BotAgent`
- **Statistical analysis**: Engle-Granger cointegration + Z-score mean reversion
- **State persistence**: JSON files (`bot_agents.json`, `cointegrated_pairs.json`) survive restarts
- **JWT Authentication**: Complete 2FA system with TOTP and email verification

### 🔧 `backend/` - Go REST API & Database

- **Multi-instance management**: API-controlled bot deployment and monitoring
- **Credential encryption**: AES-256-GCM encrypted storage of dYdX keys
- **JWT authentication**: Role-based access with 2FA support
- **Dual database**: SQLite (dev) + PostgreSQL (prod) with auto-migrations

### ⚛️ `frontend/` - React Dashboard

- **React 19 + TypeScript**: Modern UI with Vite hot-reload
- **Zustand state**: Lightweight store with localStorage persistence
- **Real-time updates**: WebSocket backtest progress + Recharts visualizations
- **Dark theme**: Financial-focused color coding (green/red P&L)

**Communication Flow**: Frontend ↔ Backend API ↔ Bot Management ↔ Trading Engine

## ⚠️ Critical Development Setup

### Environment Loading Pattern (Python)

**CRITICAL**: `bot/main.py` loads `.env` before any imports to ensure config availability:

```python
# ⚠️ CRITICAL: Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

# Only AFTER load_dotenv() import config-dependent modules
from config import config  # ← Reads DB_*, REDIS_* from environment
```

### Project Initialization Workflow

```bash
# 1. Setup Python environment
make setup && make install

# 2. Create configuration files
make config        # Creates bot/config.yaml from template
make env-setup     # Creates .env from template

# 3. Start individual components
make run           # Python trading bot (foreground)
make backend-run   # Go API server (port 8888)
cd frontend && npm run dev  # React UI (port 5173)

# 4. OR start everything with Docker
make docker-up     # Full stack with compose
```

## Component Architecture Overview

### 🐍 Bot Engine (`bot/`) - Core Trading Logic

## Component Architecture Overview

### 🐍 Bot Engine (`bot/`) - Core Trading Logic

**Dual Operation Modes**:

1. **Standalone**: `python bot/main.py` - original autonomous mode
2. **API-Controlled**: FastAPI server on port 8000 manages multiple instances

**Trading Loop Flow (`bot/main.py`)**:

```
setup_logging() → validate config → connect_dydx()
→ [FIND_COINTEGRATED_PAIRS] construct_market_prices() → store_cointegration_results()
→ MAIN LOOP:
    ├─ [MANAGE_EXITS] manage_trade_exits()      # Check bot_agents.json, close on Z-score cross
    └─ [PLACE_TRADES] open_positions()          # Load cointegrated_pairs.json, find Z-score triggers
```

**Key Bot Files**:
| File | Purpose | Key Patterns |
|------|---------|-------------|
| `bot/main.py` | Entry point - orchestrates full trading loop | `load_dotenv()` FIRST, then `setup_logging()`, then config |
| `bot/constants.py` | Single source of truth for all config values | **Always import from here, never call config() in functions** |
| `bot/func_bot_agent.py` | Atomic paired order executor | **BOTH orders must succeed or entire pair fails** |
| `bot/func_cointegration.py` | Statistical analysis with confidence scoring | `SmartError` for graceful degradation |
| `bot/bot_api_server.py` | FastAPI server for multi-instance management | JWT auth, WebSocket streams, bot lifecycle |
| `bot/bot_instance_manager.py` | Multi-bot process management | Subprocess control, state tracking |

### 🔧 Backend API (`backend/`) - Go Service Layer

**Architecture Pattern**: `cmd/server/main.go` → middleware chain → handlers → services → repositories → database

**Request Flow**:

```
gin.Router → CORSMiddleware → AuthMiddleware → RateLimitMiddleware
→ Handler → Service → Repository → DB
```

**Key Backend Files**:
| File | Purpose | Patterns |
|------|---------|----------|
| `backend/cmd/server/main.go` | Application entry with middleware setup | Dependency injection, auto-migrations |
| `backend/config/config.go` | Centralized env var config with defaults | Database DSN generation, migration path switching |
| `backend/internal/db/db.go` | Database abstraction layer | Connection pooling, retries, SQLite/PostgreSQL dual support |

### ⚛️ Frontend (`frontend/`) - React Dashboard

**Architecture**: React 19 + TypeScript + Vite + Zustand + Recharts

**API Integration Pattern**:

```typescript
// Centralized API client (src/api.ts)
class ApiClient {
  login(username, password): Promise<{access_token}>
  runBacktest(params): Promise<{run_id}>
  connectBacktestSocket(runId, token): WebSocket
}

// Zustand store (src/store/auth.ts)
useAuthStore: {
  user: User | null
  login(): Promise<void>
  isAuthenticated(): boolean
}
```

**Component Structure**:

- **Pages**: Dashboard, BacktestDetails, Login (route-level)
- **Components**: BacktestRunner, BacktestList, BacktestProgress (reusable)
- **Hooks**: useBacktestProgress (WebSocket integration)
- **Styling**: Dark theme (slate-900 backgrounds), financial color coding`

**Key Bot Files**:
| File | Purpose | Key Patterns |
|------|---------|-------------|
| `bot/main.py` | Entry point - orchestrates full trading loop | `load_dotenv()` FIRST, then `setup_logging()`, then config |
| `bot/constants.py` | Single source of truth for all config values | **Always import from here, never call config() in functions** |
| `bot/func_bot_agent.py` | Atomic paired order executor | **BOTH orders must succeed or entire pair fails** |
| `bot/func_cointegration.py` | Statistical analysis with confidence scoring | `SmartError` for graceful degradation |

### 🔧 Backend API (`backend/`) - Go Service Layer

**Architecture Pattern**: `cmd/server/main.go` → middleware chain → handlers → services → repositories → database

**Request Flow**:

```
gin.Router → CORSMiddleware → AuthMiddleware → RateLimitMiddleware
→ Handler → Service → Repository → DB
```

**Key Backend Files**:
| File | Purpose | Patterns |
|------|---------|----------|
| `backend/cmd/server/main.go` | Application entry with middleware setup | Dependency injection, auto-migrations |
| `backend/config/config.go` | Centralized env var config with defaults | Database DSN generation, migration path switching |
| `backend/internal/db/db.go` | Database abstraction layer | Connection pooling, retries, SQLite/PostgreSQL dual support |

### ⚛️ Frontend (`frontend/`) - React Dashboard

**Architecture**: React 19 + TypeScript + Vite + Zustand + Recharts

**API Integration Pattern**:

```typescript
// Centralized API client (src/api.ts)
class ApiClient {
  login(username, password): Promise<{access_token}>
  runBacktest(params): Promise<{run_id}>
  connectBacktestSocket(runId, token): WebSocket
}

// Zustand store (src/store/auth.ts)
useAuthStore: {
  user: User | null
  login(): Promise<void>
  isAuthenticated(): boolean
}
```

## Critical Trading Patterns

### BotAgent State Machine - Atomic Paired Execution

**States**: `FAILED` | `LIVE` | `CLOSE` | `ERROR`

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

### Entry Logic Flow (`func_entry_pairs.py`)

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
        # Create BotAgent for atomic paired execution
        agent = BotAgent(client, pair.base_market, pair.quote_market, ...)
        result = await agent.open_trades()
```

### Exit Logic Flow (`func_exit_pairs.py`)

```python
# Load active positions from bot_agents.json
with open("bot_agents.json") as f:
    active_positions = json.load(f)

# For each position, recalculate current Z-score
for position in active_positions:
    if position["pair_status"] != "LIVE":
        continue

    z_score = calculate_zscore(series_1, series_2, position["hedge_ratio"])

    # Exit trigger: Z-score crosses zero (mean reversion)
    if CLOSE_AT_ZSCORE_CROSS and z_score_crosses_zero:
        # Place reduce_only=True market orders to close both positions
        await close_position(client, position)
        position["pair_status"] = "CLOSE"
```

## Configuration System

### Constants Pattern (`constants.py`)

All configuration flows through centralized constants loaded from `config()`. **Never hardcode values**.

```python
# ✅ CORRECT: Import constants once at module startup
from constants import ZSCORE_THRESH, MAX_HALF_LIFE, USD_PER_TRADE

# Use constants directly
if abs(z_score) >= ZSCORE_THRESH:
    # Trade logic

# ❌ AVOID: Repeated config parsing in functions
def some_function():
    cfg = config()  # Reload YAML every time function is called
```

### Key Configuration Flags (`config.yaml`)

```yaml
botSettings:
  abortAllPositions: false # Emergency: close all positions on startup
  findCointegratedPairs: true # Run cointegration analysis
  manageExits: true # Monitor and close positions
  placeTrades: true # Execute new trades
  ZScoreThreshold: 1.5 # Entry trigger threshold
  maxHalfLife: 24 # Maximum mean reversion period (hours)
  usdPerTrade: 10.0 # Position size per trade
```

## Data Storage Architecture

### Pair Storage (`models/pair_storage.py`)

- **JSON Primary**: `cointegrated_pairs.json` with metadata and confidence scores
- **CSV Fallback**: Legacy `cointegrated_pairs.csv` for backward compatibility
- **Timestamped Backups**: `pair_history/pairs_*.json` with cleanup policies

```python
from models.pair_storage import pair_storage

# Load with format detection (JSON preferred, CSV fallback)
pairs = pair_storage.load_pairs()

# Save (creates JSON + CSV + timestamped backup automatically)
pair_storage.save_pairs(pairs)

# High-confidence filtering
high_confidence = pair_storage.get_high_confidence_pairs()  # score >= 0.7
```

### Position Tracking (`bot_agents.json`)

```json
[
  {
    "market_1": "BTC-USD",
    "market_2": "ETH-USD",
    "hedge_ratio": 0.05,
    "z_score": 1.8,
    "pair_status": "LIVE",      # FAILED, LIVE, CLOSE, ERROR
    "order_id_m1": "abc123",
    "order_id_m2": "def456"
  }
]
```

### Multi-Instance Bot Data

- **Instance Files**: `bot_agents_{instance_id}.json` for isolated state
- **Instance Logs**: `bot_{instance_id}.log` for separate logging
- **Database Tables**: SQLite/PostgreSQL for bot metadata and history

## Error Handling Patterns

### Critical Error Pattern

```python
try:
    result = await some_critical_operation()
except Exception as e:
    logger.error("Critical failure: %s", e)
    messenger.send_error_message("Operation Failed", str(e), is_critical=True)
    exit(1)  # Don't allow bot to continue with orphaned state
```

### SmartError Pattern (`func_cointegration.py`)

```python
class SmartError(Exception):
    pass

try:
    coint_flag, hedge_ratio, half_life = calculate_cointegration(series_1, series_2)
except SmartError as e:
    # Skip problematic pairs (constant series, NaNs, near-zero variance)
    logger.debug("Skipping pair %s / %s: %s", base_market, quote_market, e)
    continue  # Move to next pair instead of crashing entire analysis
```

## Development Patterns

### Always Use Async/Await

```python
# ✅ Use await for ALL dYdX client calls
markets = await get_markets(client)
order = await place_market_order(client, market, side, size)

# ❌ Missing await causes silent failures
order = place_market_order(client, market, side, size)  # Wrong!
```

### Format Numbers Before Exchange Calls

```python
from func_utils import format_number

# ✅ CORRECT: Format with market metadata
size = format_number(amount_usd / price, tick_size)
await place_market_order(client, market, side, size, price)
```

### Rate Limiting Pattern

```python
# Built-in delays in func_public.py and func_private.py
await get_candles_recent(client, market)  # Auto 0.2s delay
time.sleep(0.5)  # Manual delay between critical calls
await place_market_order(client, ...)
```

## Development Workflows

### Full Stack Development

```bash
# Complete setup from scratch
make setup && make install && make config && make env-setup

# Start all services
make backend-run   # Go API server (port 8888)
make run           # Python bot (foreground)
cd frontend && npm run dev  # React UI (port 5173)

# OR use Docker for everything
make docker-up     # Compose with database + services
```

### Bot-Only Workflows

```bash
# Standalone bot operation (original mode)
cd bot && python main.py

# API-controlled bot (new mode)
curl -X POST localhost:8888/bots/quick-deploy -H "Content-Type: application/json" -d '{...}'

# Emergency position closure
python scripts/close_open_positions.py
```

### Backend Development

```bash
# Go development with hot reload
cd backend && make dev

# Database operations
make migrate-up                    # Apply migrations
make create-migration MSG="desc"   # Create new migration
make migration-verify             # Check current state
```

### Frontend Development

```bash
cd frontend
npm run dev        # Vite development server
npm run build      # Production build
npm run lint       # TypeScript + ESLint checks
```

### Testing & Quality

```bash
# Full project validation
make test          # Python pytest suite
make lint          # Code linting (Python)
make format        # Code formatting (Black)

# Component-specific testing
cd backend && make verify    # Go: fmt + vet + lint + test
cd frontend && npm test      # Frontend unit tests

# Integration testing
make backtest-quick          # Fast 1-month backtest
make docker-up && sleep 30 && make test  # Full stack integration
```

## Cross-Component Integration

### Multi-Tier Communication

- **Frontend API Calls**: `frontend/src/api.ts` → `localhost:8888` → Backend handlers
- **Bot API Management**: FastAPI server (port 8000) → multi-instance bot control
- **Backend Bot Control**: Go services → spawn Python bot processes → `bot/main_instance.py`
- **State Synchronization**: Bot writes `bot_agents.json` → Backend reads for API responses
- **Real-time Updates**: WebSocket connections for backtest progress streaming

### Authentication & Security Architecture

- **Bot API**: FastAPI with JWT authentication, TOTP 2FA, email verification
- **Backend**: Go JWT middleware with AES-256-GCM encryption, role-based access
- **Frontend**: Zustand auth store with localStorage persistence, automatic 401 handling
- **Security Flow**: Frontend login → Bot/Backend JWT → Protected endpoints

### dYdX Client Integration (`bot/func_connections.py`)

```python
class Client:
    indexer          # Market data (always mainnet for better liquidity data)
    indexer_account  # Account queries (testnet/mainnet based on config)
    node            # Chain operations (matches account endpoint)
    wallet          # Transaction signing (optional for backtesting)
```

### Database Architecture

- **Bot API**: SQLite for authentication, user management, bot instances
- **Backend**: SQLite (development) + PostgreSQL (production) for backtests
- **Auto-migrations**: Both systems use migration tools with dirty state recovery
- **Connection Management**: Pooled connections with retry logic

## Critical API Authentication Patterns

### Bot API Authentication (FastAPI)

**Default Admin Account**:

- Username: `admin`
- Password: `admin123` ⚠️ **Change immediately!**
- Email: `admin@localhost`

**Authentication Setup**:

```bash
# Initialize auth database
cd bot && python init_auth_db.py

# Start API server (port 8000)
python start_api.py

# Login and get JWT token
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Use Bearer token for protected endpoints
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/bots"
```

**Key Authentication Endpoints**:

- `/auth/login` - Get JWT tokens (30min access, 7 day refresh)
- `/auth/refresh` - Refresh access token
- `/auth/2fa/setup` - TOTP 2FA setup with QR codes
- `/api/v1/bots/*` - All bot management (🔒 Protected)

### Multi-Instance Bot Management

**Bot Lifecycle API**:

```bash
# Create bot instance
POST /api/v1/bots
{
  "instance_id": "btc-eth-bot-01",
  "credentials": {"address": "...", "mnemonic": "..."},
  "trading_params": {"is_testnet": true, "zscore_threshold": 1.5}
}

# Start trading
POST /api/v1/bots/{instance_id}/start

# Monitor via WebSocket
ws://localhost:8000/api/v1/bots/{instance_id}/positions/live
```

**Instance Isolation**:

- Separate processes per bot: `bot_{instance_id}.log`
- Isolated state files: `bot_agents_{instance_id}.json`
- Database tracking: bot_instances table links to all data

## Frontend Development Patterns

### React Component Structure

**Functional Components with TypeScript**:

```typescript
interface MyComponentProps {
  title: string;
  onSubmit?: (data: FormData) => void;
  isLoading?: boolean;
}

export const MyComponent: React.FC<MyComponentProps> = ({
  title,
  onSubmit,
  isLoading = false,
}) => {
  // Always handle loading, error, and data states
  if (loading)
    return (
      <div className="flex items-center justify-center">
        <Loader />
      </div>
    );
  if (error)
    return <div className="bg-red-900 border-red-700 p-4">Error: {error}</div>;

  return (
    <div className="bg-slate-900 p-4">
      <h2 className="text-white text-xl">{title}</h2>
    </div>
  );
};
```

### Zustand State Management

**Store Pattern (v5 syntax)**:

```typescript
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthStore {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      login: async (email, password) => {
        const response = await api.login(email, password);
        set({ user: response.user });
      },
      isAuthenticated: () => !!get().user,
    }),
    { name: "auth-store" } // localStorage key
  )
);
```

### API Client Pattern

**Centralized HTTP with Interceptors**:

```typescript
// All API calls go through src/api.ts
class ApiClient {
  private client = axios.create({
    baseURL: "http://localhost:8888/api/v1",
    timeout: 30000,
  });

  constructor() {
    // Auto-attach JWT tokens
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem("auth-token");
      if (token) config.headers.Authorization = `Bearer ${token}`;
      return config;
    });

    // Handle 401 errors (logout + redirect)
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          useAuthStore.getState().logout();
          window.location.href = "/login";
        }
        throw error;
      }
    );
  }
}
```

## Backend Development Patterns

### Go Service Architecture

**Layer Separation**:

```go
// cmd/server/main.go - Entry point with middleware
func main() {
    config.LoadConfig()
    db := database.Initialize()

    router := gin.Default()
    router.Use(middleware.CORS())
    router.Use(middleware.Auth())

    routes.SetupRoutes(router, services)
}

// internal/handlers/ - HTTP request processing
func (h *BacktestHandler) RunBacktest(c *gin.Context) {
    userID := c.GetString("user_id") // From auth middleware
    result, err := h.service.RunBacktest(userID, params)
    c.JSON(200, gin.H{"success": true, "data": result})
}

// internal/services/ - Business logic
func (s *BacktestService) RunBacktest(userID string, params BacktestParams) (*BacktestResult, error) {
    // Validate, encrypt credentials, spawn bot process
    return s.repository.Create(backtest)
}
```

### Database Migration Pattern

```bash
# Create migration
make migrate-create NAME=add_user_profiles

# Apply migrations
make migrate-up

# Rollback if needed
make migrate-down N=1

# Check status
make migration-verify
```

### Development Commands

```bash
# Backend (Go)
cd backend
make dev           # Hot reload with air
make verify        # fmt + vet + lint + test
make lint-fix      # Auto-fix linter issues

# Frontend (React)
cd frontend
npm run dev        # Vite dev server (port 5173)
npm run build      # Production build
npm run lint       # ESLint + TypeScript check

# Bot (Python)
cd bot
make run           # Standalone bot
python start_api.py # Multi-instance API server
```

## Bot-Specific Anti-Patterns

❌ **Don't**: Call `config()` in functions - use constants instead
❌ **Don't**: Miss `await` on dYdX API calls - they're all async  
❌ **Don't**: Skip number formatting - dYdX rejects wrong precision
❌ **Don't**: Continue after atomic execution failures - use `exit(1)`
❌ **Don't**: Import modules before `load_dotenv()` in main.py
❌ **Don't**: Modify state files directly - use singleton managers

✅ **Do**: Use constants from `constants.py` for all config values
✅ **Do**: Format all numbers with `format_number()` before exchange calls
✅ **Do**: Handle both orders in BotAgent atomically with emergency cleanup
✅ **Do**: Load environment variables first in any new script
✅ **Do**: Use SmartError for graceful cointegration analysis degradation
