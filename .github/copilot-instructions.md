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

### Current Project Structure (November 2024)

```
dydx-trading-bot/
├── bot/                          # Python trading engine & FastAPI server
│   ├── main.py                   # Standalone bot entry point
│   ├── main_instance.py          # Multi-instance bot support
│   ├── bot_api_server.py         # FastAPI server (port 8000)
│   ├── bot_instance_manager.py   # Multi-bot process management
│   ├── constants.py              # Single source of truth for config
│   ├── config.py                 # YAML config dataclasses
│   ├── func_bot_agent.py         # Atomic paired order execution
│   ├── func_cointegration.py     # Statistical analysis engine
│   ├── func_entry_pairs.py       # Trade entry logic
│   ├── func_exit_pairs.py        # Trade exit management
│   ├── models/                   # Data models for backtest results
│   │   └── backtest_models.py
│   └── bot_agents.json           # Active position tracking
├── backend/                      # Go REST API & database
│   ├── cmd/server/main.go        # Entry point with middleware setup
│   ├── config/config.go          # Environment configuration
│   ├── internal/
│   │   ├── services/pair_storage.go  # Pair storage implementation
│   │   ├── handlers/             # HTTP request handlers
│   │   └── models/models.go      # Database models
│   └── migrations/               # Database schema migrations
├── frontend/                     # React dashboard
│   ├── src/
│   │   ├── api.ts               # Centralized API client
│   │   ├── store/auth.ts        # Zustand state management
│   │   ├── pages/               # Route-level components
│   │   └── components/          # Reusable UI components
│   └── package.json
└── scripts/                     # Utility scripts
```

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

**⚠️ PROJECT STRUCTURE NOTE**: Based on the Makefile, the Python code refers to `app/` directory in configs, but actual structure uses `bot/`. This may require path adjustments.

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

### Constants Pattern (`bot/constants.py`)

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

### Key Configuration Flags (`bot/config.yaml`)

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

### Working Directory Patterns

**Python Bot**: Always run from `bot/` directory for proper file access:

```bash
cd bot && python main.py                  # Standalone mode
cd bot && python bot_api_server.py       # API server mode
```

**Go Backend**: Run from `backend/` directory:

```bash
cd backend && make dev                    # Development with hot-reload
cd backend && go run cmd/server/main.go   # Direct execution
```

**Frontend**: Standard Node.js patterns:

```bash
cd frontend && npm run dev                # Development server
cd frontend && npm run build              # Production build
```

**CRITICAL PATH ISSUE**: The Go backend pair storage references `app/` directory, but the Python bot is in `bot/` directory. This may cause file path mismatches:

```go
// backend/internal/services/pair_storage.go
storagePath: "app",                              // ❌ Wrong path
jsonFile: filepath.Join("app", "cointegrated_pairs.json"),  // Should be "bot/"
```

## Critical Implementation Notes

### Missing Python Pair Storage Module

**ISSUE**: The codebase imports `from models.pair_storage import pair_storage` but this file doesn't exist. This suggests either:

1. **Backend Bridge**: Python bot bridges to Go backend pair storage via API calls
2. **Missing File**: The `bot/models/pair_storage.py` file needs to be created as a wrapper
3. **Direct JSON Access**: Alternative implementation using direct JSON file manipulation

**Current Pattern**: The bot directly reads/writes `cointegrated_pairs.json` and `bot_agents.json` files:

```python
# Current working pattern in func_cointegration.py and func_entry_pairs.py
import json

# Save pairs directly to JSON
with open("cointegrated_pairs.json", "w") as f:
    json.dump(pairs_data, f)

# Load active positions
with open("bot_agents.json", "r") as f:
    positions = json.load(f)
```

### Data Storage Architecture

### Pair Storage System

The project has **dual pair storage implementations**:

**Python Bot Side** (`bot/func_cointegration.py`):

- **IMPORTANT**: Imports use `from models.pair_storage import pair_storage` but the actual implementation bridges to Go backend services
- Uses `pair_storage.save_pairs()` and `pair_storage.load_pairs()` for cointegration results
- JSON Primary: `cointegrated_pairs.json` with metadata and confidence scores
- CSV Fallback: Legacy `cointegrated_pairs.csv` for backward compatibility
- Timestamped Backups: `pair_history/pairs_*.json` with cleanup policies

**Backend Go Implementation** (`backend/internal/services/pair_storage.go`):

- **Singleton pattern**: `GetPairStorage()` returns shared `PairStorageManager` instance
- **JSON-first storage**: Structured format with metadata, version info, confidence scores
- **CSV compatibility**: Maintains legacy CSV format for older bot versions
- **API endpoints**: `/api/v1/pairs/*` for external access to stored pairs

```python
# Python usage (func_cointegration.py, func_entry_pairs.py)
from models.pair_storage import pair_storage

# Load with format detection (JSON preferred, CSV fallback)
pairs = pair_storage.load_pairs()

# Save (creates JSON + CSV + timestamped backup automatically)
result = pair_storage.save_pairs(criteria_met_pairs)

# High-confidence filtering
high_confidence = pair_storage.get_high_confidence_pairs()  # score >= 0.7
```

```go
// Go backend usage (backend/internal/services/)
storage := services.GetPairStorage()
pairs, err := storage.LoadPairs()
result, err := storage.SavePairs(pairs)
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

## Complete API Endpoint Reference

### Bot API (FastAPI - Port 8000)

#### Authentication Endpoints

- `POST /auth/login` - Login with username/password → returns `{access_token, refresh_token}`
- `POST /auth/refresh` - Refresh expired access token
- `POST /auth/register` - Register new user account
- `POST /auth/logout` - Logout and invalidate tokens
- `POST /auth/2fa/setup` - Enable TOTP 2FA
- `POST /auth/2fa/verify` - Verify 2FA token during login
- `GET /auth/me` - Get current user profile

#### Bot Management Endpoints

- `POST /api/v1/bots` - Create new bot instance
  ```json
  {
    "instance_id": "bot-001",
    "credentials": { "address": "...", "mnemonic": "..." },
    "trading_params": { "is_testnet": true, "zscore_threshold": 1.5 }
  }
  ```
- `GET /api/v1/bots` - List all bot instances
- `GET /api/v1/bots/{instance_id}` - Get bot status
- `POST /api/v1/bots/{instance_id}/start` - Start bot trading
- `POST /api/v1/bots/{instance_id}/stop` - Stop bot gracefully
- `POST /api/v1/bots/{instance_id}/restart` - Restart bot
- `DELETE /api/v1/bots/{instance_id}` - Delete bot instance
- `POST /api/v1/bots/quick-deploy` - Fast bot deployment

#### Position Monitoring

- `GET /api/v1/bots/{instance_id}/positions/current` - Active positions
- `GET /api/v1/bots/{instance_id}/positions/{position_id}` - Position details
- `GET /api/v1/bots/{instance_id}/position-history/{position_id}` - Position history
- `GET /api/v1/bots/{instance_id}/trades` - All trades (paginated)

#### Analytics & Stats

- `GET /api/v1/bots/{instance_id}/stats` - Performance statistics
- `GET /api/v1/bots/{instance_id}/realtime-stats` - Real-time P&L updates
- `GET /api/v1/bots/{instance_id}/history` - Execution history
- `GET /api/v1/bots/{instance_id}/jobs` - Job queue status
- `GET /api/v1/bots/{instance_id}/market-data` - Current market data
- `GET /api/v1/bots/{instance_id}/alerts` - Alert history

#### System Status

- `GET /health` - Health check
- `GET /api/v1/system/status` - System status and resource usage

### Backend API (Go REST API - Port 8888)

#### Authentication

- `POST /api/v1/auth/login` - Go backend authentication
- `POST /api/v1/auth/refresh` - Refresh tokens
- `GET /api/v1/users/me` - Current user profile

#### Backtest Management (Delegated to Bot API)

- `POST /api/v1/backtests` - Create/run backtest
- `GET /api/v1/backtests` - List backtests
- `GET /api/v1/backtests/{run_id}` - Get backtest results
- `GET /api/v1/backtests/stats/summary` - Backtest statistics
- `WebSocket /ws/backtest/{run_id}` - Real-time progress updates

#### Pair Storage

- `GET /api/v1/pairs/load` - Load cointegrated pairs
- `POST /api/v1/pairs/save` - Save analysis results
- `GET /api/v1/pairs/best` - Get top pairs by confidence
- `GET /api/v1/pairs/high-confidence` - Filter high-confidence pairs
- `GET /api/v1/pairs/storage-info` - Storage statistics

#### dYdX Key Management

- `POST /api/v1/keys` - Store encrypted dYdX key
- `GET /api/v1/keys` - List stored keys
- `DELETE /api/v1/keys/{key_id}` - Delete key

#### Strategy Management

- `POST /api/v1/strategies` - Save trading strategy
- `GET /api/v1/strategies` - List strategies
- `PUT /api/v1/strategies/{strategy_id}` - Update strategy
- `DELETE /api/v1/strategies/{strategy_id}` - Delete strategy

## Bot Database Models

### Python Bot Database (SQLAlchemy ORM)

**BotInstance** - Individual bot instance lifecycle

```python
- instance_id: str (unique)
- status: BotStatusEnum (CREATED, RUNNING, STOPPED, FAILED, etc.)
- process_id: int
- configuration: JSON
- created_at: datetime
- started_at: datetime
```

**Job** - Task execution tracking

```python
- instance_id: str (FK)
- job_type: JobStatusEnum (cointegration, entry, exit, etc.)
- status: str
- result: JSON
- error_message: str
- started_at, completed_at: datetime
```

**Trade** - Individual trade records

```python
- instance_id: str (FK)
- market_1, market_2: str
- entry_timestamp: datetime
- hedge_ratio: float
- z_score_entry: float
- status: TradeStatusEnum
- pnl: float
- exit_timestamp: datetime
```

### Backend Database Models (Go)

**BacktestStrategy** - Saved trading strategies

```go
- Name, Description: string
- ZscoreThreshold, MaxHalfLife, UsdPerTrade: float/int
- FindCointegratedPairs, ManageExits, PlaceTrades: bool
- MaxPositions, StopLossPct, TakeProfitPct: int/float
```

**BacktestRun** - Backtest execution records

```go
- RunID: string (unique)
- Status: string (running, completed, failed)
- StartDate, EndDate: string
- NumPairs, TotalMarkets: int
- TotalPnL, TotalReturn: float
- EquityCurve: JSON array
- TradingStats: JSON (Sharpe, MaxDD, WinRate, etc.)
```

**DYDXKey** - Encrypted dYdX credentials

```go
- UserID: int (FK)
- Network: string (testnet/mainnet)
- ChainAddress: string
- EncryptedSecret: string (AES-256-GCM)
```

## Frontend Implementation Details

### Page Components

- **Login.tsx** - Authentication UI, TOTP 2FA support
- **Dashboard.tsx** - Main hub with bot status, backtest runner
- **BacktestDetails.tsx** - Detailed results with charts (equity curve, P&L scatter)
- **Settings.tsx** - User settings, dYdX key management, Redis configuration
- **BacktestDetailsV2.tsx** - Enhanced comparison and analytics

### Reusable Components

- **BacktestRunner.tsx** - Form for backtest parameters (dates, pairs, thresholds)
- **BacktestList.tsx** - Table of runs with filters and sorting
- **BacktestProgress.tsx** - Real-time progress bar via WebSocket
- **PerformanceMetrics.tsx** - P&L display, key metrics
- **TradeHistory.tsx** - Trade-by-trade breakdown with entry/exit details
- **DYDXKeyManager.tsx** - Credential encryption and storage UI
- **StrategyManager.tsx** - Create, save, and manage trading strategies
- **Sidebar.tsx** - Navigation and bot status indicator

### Zustand Stores

- **useAuthStore** (`store/auth.ts`) - User state, login/logout, token management
- Additional stores for backtest state, settings, real-time updates

### WebSocket Integration

```typescript
// Real-time backtest progress
ws://localhost:8888/ws/backtest/{runId}?token=JWT_TOKEN
// Messages: {progress: 0-100, current_pair: string, status: string}
```

## Environmental Variables Reference

### Python Bot (.env)

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=bot_user
DB_PASSWORD=***
DB_NAME=trading_bot

# Redis (caching)
REDIS_HOST=localhost
REDIS_PORT=6379

# dYdX
DYDX_ACCOUNT_ADDRESS=dydx1...
DYDX_MNEMONIC=***
IS_TESTNET=true

# Telegram Alerts
TELEGRAM_BOT_TOKEN=***
TELEGRAM_CHAT_ID=***

# JWT
JWT_SECRET_KEY=***
JWT_ALGORITHM=HS256

# Logging
LOG_LEVEL=INFO
```

### Go Backend (.env)

```bash
# Database
DB_TYPE=postgres  # or sqlite
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=***
DB_NAME=dydx_bot

# Encryption
ENCRYPTION_KEY=***  # For AES-256-GCM

# API
API_PORT=8888
BOT_API_URL=http://localhost:8000

# JWT
JWT_SECRET=***
```

### Frontend (Vite)

```bash
VITE_API_URL=http://localhost:8888
VITE_BOT_API_URL=http://localhost:8000
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
✅ **Do**: Encrypt sensitive data (mnemonics, API keys) before persistence
✅ **Do**: Always use JWT Bearer tokens for authenticated API calls

## Key Implementation Patterns

### Position Entry Pattern (Atomic Paired Trades)

```python
# func_entry_pairs.py pattern
async def open_positions(client):
    pairs = pair_storage.load_pairs()  # Load cointegrated pairs

    for pair in pairs:
        # Calculate current Z-score
        zscore = calculate_zscore(
            await get_candles_recent(client, pair.base_market),
            await get_candles_recent(client, pair.quote_market),
            pair.hedge_ratio
        )

        # Entry trigger
        if abs(zscore) >= ZSCORE_THRESH:
            agent = BotAgent(client, pair.base_market, pair.quote_market, ...)
            result = await agent.open_trades()  # Atomic execution

            if result["pair_status"] == "LIVE":
                bot_agents.append(result)  # Save position
```

### Error Recovery Pattern

```python
# Critical operations must handle failures gracefully
try:
    result = await critical_operation()
except Exception as e:
    logger.error("Operation failed: %s", e)
    messenger.send_error_message("Error", str(e), is_critical=True)
    exit(1)  # Don't silently continue with orphaned state

# Non-critical operations skip and log
try:
    result = await non_critical_operation()
except SmartError as e:
    logger.debug("Skipping: %s", e)
    continue  # Move to next item
```

### Number Precision Pattern

```python
# ALWAYS format numbers for dYdX exchange
from func_utils import format_number

# Get market metadata for precision
markets = await get_markets(client)
market = markets[market_id]

# Format: amount, ticket size, step size
size = format_number(usd_amount / price, market["minOrderSize"])
price = format_number(current_price, market["stepSize"])

# Then place order with formatted values
order = await place_market_order(client, market_id, side, size, price)
```

### WebSocket Real-Time Updates (Backend → Frontend)

```typescript
// Frontend WebSocket connection pattern
const connectBacktestSocket = (runId: string, token: string) => {
  const ws = new WebSocket(
    `ws://localhost:8888/ws/backtest/${runId}?token=${token}`
  );

  ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    // {progress: 0-100, current_pair: string, status: string}
    updateBacktestProgress(update);
  };

  ws.onclose = () => logger.log("🔌 Backtest socket disconnected");
};
```

### Multi-Instance State Management Pattern

```python
# bot_instance_manager.py manages isolated state per instance
class BotInstanceManager:
    def __init__(self):
        self.instances: Dict[str, BotState] = {}

    def create_instance(self, instance_id: str) -> BotState:
        # Each instance gets isolated files
        bot_agents_file = f"bot_agents_{instance_id}.json"
        pairs_file = f"cointegrated_pairs_{instance_id}.json"
        log_file = f"bot_{instance_id}.log"

        return BotState(
            instance_id=instance_id,
            process=None,
            config_file=None,
            state_files={...}
        )
```

### Backtest Execution Pattern

```python
# func_backtesting.py demonstrates backtest engine structure
class BacktestEngine:
    async def run_backtest(self, strategy_params):
        # 1. Load historical data
        df = await self._fetch_historical_data()

        # 2. Find cointegrated pairs at analysis date
        pairs = await self._find_cointegrated_pairs()

        # 3. Simulate trading loop
        for date in date_range:
            # Entry signals
            entries = self._check_entry_signals(date, pairs)

            # Execute trades
            for entry in entries:
                self.trades.append(await self._simulate_trade(entry, date))

            # Exit signals
            exits = self._check_exit_signals(date)
            for exit in exits:
                self.trades[-1].close(exit)

        # 4. Calculate metrics
        return BacktestResult(
            pnl=sum(t.pnl for t in self.trades),
            sharpe=calculate_sharpe(...),
            max_dd=calculate_max_dd(...)
        )
```

### JWT Authentication Pattern (Python & Go)

```python
# Python: Validate token in auth_middleware.py
async def get_current_active_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
    except JWTError:
        raise credentials_exception

    user = get_user(username)
    return user
```

```go
// Go: JWT middleware in internal/middleware/
func RequireAuth() gin.HandlerFunc {
    return func(c *gin.Context) {
        token := c.GetHeader("Authorization")
        claims, err := jwt.Parse(token, ...)
        if err != nil || !claims.Valid {
            c.JSON(401, gin.H{"error": "Unauthorized"})
            c.Abort()
            return
        }
        c.Set("user_id", claims.Subject)
        c.Next()
    }
}
```

### Encryption Pattern (AES-256-GCM)

```go
// Backend key encryption in internal/services/key_service.go
func (ks *KeyService) EncryptSecret(plaintext string) (string, error) {
    key := []byte(os.Getenv("ENCRYPTION_KEY"))
    plainBytes := []byte(plaintext)

    // Generate nonce
    nonce := make([]byte, 12)
    rand.Read(nonce)

    // AES-256-GCM encrypt
    cipher, _ := aes.NewCipher(key)
    aesgcm, _ := cipher.AEAD(cipher.BlockSize())
    ciphertext := aesgcm.Seal(nonce, nonce, plainBytes, nil)

    return base64.StdEncoding.EncodeToString(ciphertext), nil
}
```

## Common Debugging Scenarios

### Bot Won't Start

1. Check `load_dotenv()` is first line in `main.py`
2. Verify `.env` file exists with all required variables
3. Check database connection: `make migrate-up` in `backend/`
4. Look for port conflicts (8000 bot API, 8888 Go API, 5173 frontend)

### Orders Not Executing

1. Verify dYdX network (testnet vs mainnet) matches configuration
2. Check balance with `GET /api/v1/bots/{id}/stats` → current_balance
3. Ensure market prices haven't changed dramatically (check Z-score in response)
4. Look for `SmartError` in logs for precision/format issues

### Positions Not Closing on Exit

1. Verify Z-score is properly crossing zero in exit condition
2. Check `CLOSE_AT_ZSCORE_CROSS` flag is `true` in config
3. Verify reduce_only flag is working (check exchange order details)
4. Look for emergency cleanup in logs if market_2 order failed

### WebSocket Not Receiving Updates

1. Verify JWT token in WebSocket URL is valid and not expired
2. Check backend firewall allows WebSocket connections
3. Verify `ws://` protocol (not `http://`) in frontend connection
4. Check `allowOrigins` CORS configuration in backend

### High Latency/Slow Backtests

1. Reduce `num_pairs` in backtest parameters
2. Use shorter date ranges for testing
3. Check Redis is running if caching is enabled
4. Profile with `make backtest-quick` (1 month) first

## Deployment Quick Reference

### Local Development (All Components)

```bash
# Terminal 1: Backend
cd backend && make dev

# Terminal 2: Bot API
cd bot && python start_api.py

# Terminal 3: Frontend
cd frontend && npm run dev

# Terminal 4: Standalone bot (optional)
cd bot && python main.py
```

### Docker Stack

```bash
make docker-up          # Full stack
make docker-logs -f     # Stream logs
make docker-down        # Stop all services
```

### Production Checklist

- [ ] Change default admin credentials
- [ ] Set strong JWT_SECRET_KEY and ENCRYPTION_KEY
- [ ] Use PostgreSQL instead of SQLite
- [ ] Configure Redis for caching
- [ ] Set up Telegram alerts
- [ ] Enable TOTP 2FA for all users
- [ ] Use HTTPS/TLS in frontend/backend communication
- [ ] Set up proper database backups
- [ ] Monitor disk space (backtest data grows)
- [ ] Configure rate limiting in Go middleware
