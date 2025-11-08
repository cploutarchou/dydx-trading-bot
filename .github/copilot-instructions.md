# dYdX Trading Bot - AI Coding Agent Instructions

**Essential guide for AI agents working on this multi-component trading system.** Focus: productivity through pattern discovery, cross-component integration, and codebase-specific conventions.

---

## System Architecture at a Glance

**Three-tier system** for statistical arbitrage trading on dYdX v4:

```
┌──────────────────────────────────────────────────┐
│ Frontend (React 19 + TypeScript)                 │
│ localhost:5173 - Dashboard + WebSocket updates   │
└──────────────────────────────────────────────────┘
                      ↔ HTTP
┌──────────────────────────────────────────────────┐
│ Bot API (FastAPI, Python)                        │
│ localhost:8000 - Bot lifecycle + WebSocket layer │
└──────────────────────────────────────────────────┘
                      ↔ IPC
┌──────────────────────────────────────────────────┐
│ Bot Trading Engine (Async Python subprocesses)   │
│ - Entry: cointegration + Z-score                 │
│ - Exit: mean reversion (Z crosses zero)          │
│ - State: JSON files + SQLAlchemy DB              │
└──────────────────────────────────────────────────┘
```

### Running the Project

**Standalone bot** (original mode):
```bash
cd bot && python main.py  # Reads from config.yaml, uses constants.py
```

**Full stack with API**:
```bash
# Terminal 1: Bot API server
cd bot && python bot_api_server.py   # or start_api.py

# Terminal 2: Frontend
cd frontend && npm run dev           # Vite on :5173

# Terminal 3: Individual bot instance (optional)
cd bot && python main_instance.py --instance-id "bot-1"
```

**Production Docker**:
```bash
make docker-up  # Compose with all services
```

---

## Critical Patterns (Read These)

### 1. Configuration Loading - Single Source of Truth

**Pattern**: `config.yaml` → `config.py` (dataclasses) → `constants.py` (exports) → runtime code

```python
# ❌ WRONG: Repeated parsing in functions
def some_function():
    cfg = config()  # Reload YAML every time
    threshold = cfg.botSettings.ZScoreThreshold

# ✅ RIGHT: Import constants once
from constants import ZSCORE_THRESH
def some_function():
    if abs(z_score) >= ZSCORE_THRESH:  # Direct use
        ...
```

**Why**: `config()` is expensive (YAML parse + env var interpolation). Parse once at startup, export constants.

**Location**: `bot/config.yaml` (user-editable), `bot/config.py` (dataclasses), `bot/constants.py` (runtime imports)

### 2. Environment Bootstrap - Order Matters

**File**: `bot/main.py` - CRITICAL ordering:

```python
# ⚠️ LINE 1: Load .env BEFORE any imports
from dotenv import load_dotenv
load_dotenv()

# Line 2+: Then import config-dependent modules
from config import config
from constants import ZSCORE_THRESH
```

**Why**: `config()` reads env vars (DB_HOST, REDIS_PORT, JWT_KEY). If you import before `load_dotenv()`, config tries to parse before vars exist.

### 3. Atomic Paired Execution - BotAgent Pattern

**File**: `bot/func_bot_agent.py` - Two dYdX orders must both succeed or entire trade fails

```python
class BotAgent:
    async def open_trades(self):
        # 1. Place base market order
        order_1 = await place_market_order(client, market_1, side_1, size_1)
        if not (await check_order_status(client, order_1)) == "FILLED":
            return {"pair_status": "FAILED"}
        
        # 2. Place quote market order
        order_2 = await place_market_order(client, market_2, side_2, size_2)
        if not (await check_order_status(client, order_2)) == "FILLED":
            # EMERGENCY CLEANUP: Close market_1 to avoid orphaned position
            await place_market_order(client, market_1, opposite_side, size_1, reduce_only=True)
            return {"pair_status": "FAILED"}
        
        return {"pair_status": "LIVE", "order_id_m1": order_1, "order_id_m2": order_2}
```

**Key rule**: If market_2 fails after market_1 filled, MUST emergency-close market_1. No orphaned positions.

### 4. State Persistence - JSON Files

**Key files** (read/write atomically):

- `bot_agents.json` - Active positions with pair status (LIVE, CLOSE, FAILED)
- `cointegrated_pairs.json` - Analysis results from last cointegration run
- `pair_history/pairs_*.json` - Timestamped backups with retention policy

**Current approach**: Direct JSON manipulation (no singleton manager yet)

```python
import json

# Save: Call once after cointegration analysis
with open("cointegrated_pairs.json", "w") as f:
    json.dump([{"base_market": "BTC-USD", "quote_market": "ETH-USD", "hedge_ratio": 0.05, ...}], f)

# Load: Call at entry signal check
with open("cointegrated_pairs.json") as f:
    pairs = json.load(f)
```

### 5. Error Handling - Two Tiers

**Critical failures** (exit immediately):
```python
try:
    result = await critical_dydx_operation()
except Exception as e:
    logger.error("Critical: %s", e)
    messenger.send_error_message("CRITICAL", str(e), is_critical=True)
    exit(1)  # Don't continue with orphaned state
```

**Non-critical** (skip and log):
```python
try:
    coint_flag, hr, hl = calculate_cointegration(series_1, series_2)
except SmartError as e:
    logger.debug("Skipping pair %s: %s", market_pair, e)
    continue  # Move to next pair
```

---

## Key Files & Their Roles

### Bot Core (`bot/` directory)

| File | Purpose | Key Exports/Functions |
|------|---------|-------|
| `main.py` | Standalone bot entry + logging setup | Entry point with signal handlers |
| `constants.py` | Runtime constants from config | `ZSCORE_THRESH`, `USD_PER_TRADE`, etc. |
| `config.py` | YAML parsing + dataclasses | `config()` function returns full config tree |
| `func_bot_agent.py` | Atomic paired order execution | `BotAgent.open_trades()` - handles emergency cleanup |
| `func_entry_pairs.py` | Trade entry signal logic | Loads pairs, calculates Z-scores, spawns BotAgent |
| `func_exit_pairs.py` | Trade exit signal logic | Z-score zero-crossing detection + close orders |
| `func_cointegration.py` | Statistical analysis | Engle-Granger test, saves to JSON |
| `bot_api_server.py` | FastAPI + multi-instance mgmt | `BotInstanceManager` for subprocess control |
| `websocket_server.py` | Real-time data broadcast | Position updates, market data streaming |
| `models.py` | SQLAlchemy ORM for auth/bot state | `BotInstance`, `Trade`, `Job`, `User` |

### API & Data Layer

| File | Purpose |
|------|---------|
| `auth_routes.py` | JWT login/refresh, 2FA setup |
| `bot_api_models.py` | Pydantic schemas for API requests/responses |
| `repository.py` | Data access layer (auth/bot data) |
| `repository_backtest.py` | Backtest execution + result storage |
| `service_backtest.py` | Backtest orchestration logic |
| `service_dydx_credentials.py` | Credential encryption/storage (AES-256-GCM) |
| `database.py` | SQLAlchemy session management + auto-migrations |

### Frontend (`frontend/` directory)

| Path | Purpose |
|------|---------|
| `src/api.ts` | Centralized HTTP client (axios) with JWT interceptors |
| `src/store/auth.ts` | Zustand auth store with localStorage persistence |
| `src/pages/` | Route-level components (Dashboard, BacktestDetails, Login) |
| `src/components/` | Reusable UI (BacktestRunner, TradeHistory, etc.) |

---

## Trading Loop Flow (What Happens When Bot Runs)

**`main.py` orchestration**:

```
1. setup_logging() + load_dotenv() + config()
2. Connect to dYdX client (testnet/mainnet from constants)
3. [IF FIND_COINTEGRATED] Run cointegration analysis → save cointegrated_pairs.json
4. MAIN LOOP (every N seconds):
   ├─ [IF MANAGE_EXITS] Load bot_agents.json → check Z-scores → close positions on zero-cross
   └─ [IF PLACE_TRADES] Load cointegrated_pairs.json → check entry signals → spawn BotAgent
5. [IF ABORT_ALL_POSITIONS] Emergency close all open positions (Telegram alert)
```

**Entry signal** (`func_entry_pairs.py`):
- Load cointegrated pairs from JSON
- For each pair: fetch recent candles, calculate Z-score
- If `|Z-score| >= ZSCORE_THRESH`: spawn `BotAgent(market_1, market_2, ...)`
- On success: append to `bot_agents.json` with status "LIVE"

**Exit signal** (`func_exit_pairs.py`):
- Load active positions from `bot_agents.json` (status="LIVE")
- For each: recalculate Z-score from current prices
- If `Z-score crosses zero`: place reduce_only market orders to close both sides
- Update status to "CLOSE"

---

## Development Workflows

### Local Development (Recommended)

```bash
# Setup once
cd bot && python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run tests
make test

# Run bot
cd bot && python main.py

# Run API (separate terminal)
cd bot && python bot_api_server.py
```

### Common Tasks

**Adding new config parameter**:
1. Add to `config.yaml` with defaults
2. Add field + type to `config.py` dataclass
3. Export from `constants.py`
4. Import from `constants` in code (never call `config()`)

**Fixing trade execution issues**:
1. Check `bot_agents.json` - what positions exist?
2. Review logs for emergency cleanup messages
3. Check dYdX order status via account query
4. Verify `ZSCORE_THRESH` and market prices in logs

**Testing a backtest**:
```bash
cd bot
python -m pytest tests/test_backtesting.py -v
# or
python scripts/run_backtest.py --start 2025-01-01 --end 2025-02-01
```

---

## Integration Points (Cross-Component)

### Frontend → Bot API

**Pattern**: All requests go to `localhost:8000/api/v1/...` with JWT Bearer token

```typescript
// frontend/src/api.ts - Centralized client
const loginResponse = await api.post('/auth/login', {username, password});
const token = loginResponse.access_token;

// Auto-attach token to subsequent requests via interceptor
```

### Bot API → Bot Subprocess

**Pattern**: `BotInstanceManager` spawns isolated `main_instance.py` processes

- Each instance has: separate `bot_agents_{id}.json`, separate log file
- IPC via database + state files (no RPC/gRPC)
- Lifecycle: create → start → stop → delete

### WebSocket Real-Time Updates

**Frontend** connects to `ws://localhost:8000/api/v1/bots/{instance_id}/positions/live`
- Bot process broadcasts via `WebSocketServer.broadcast_position_opened()`, etc.
- Messages: `{"event": "position_opened", "data": {...}}`

---

## Anti-Patterns (Avoid These)

❌ Call `config()` in runtime functions - use constants instead  
❌ Miss `await` on dYdX API calls (all are async)  
❌ Skip number formatting - exchange rejects wrong precision (use `format_number()`)  
❌ Continue after atomic execution failure - use `exit(1)` for critical errors  
❌ Import modules before `load_dotenv()` in entry points  
❌ Modify JSON state files without locking - could corrupt  
❌ Ignore Z-score confidence in cointegration results  

✅ Use constants from `constants.py` for all config values  
✅ Format all numbers with `format_number(value, tick_size)` before exchange calls  
✅ Handle BotAgent failures with emergency cleanup (close the first order if second fails)  
✅ Load environment variables FIRST in any executable script  
✅ Use `SmartError` for graceful degradation in cointegration (skip bad pairs, don't crash)  
✅ Log entry points: "Trading loop started", config summary, network (testnet/mainnet)  
✅ Test state recovery: verify bot works after database/file corruption  

---

## Database Schema (Quick Reference)

**Key tables** (SQLAlchemy models in `bot/models.py`):

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | API authentication | username, email, password_hash, 2fa_secret |
| `bot_instances` | Bot instance tracking | instance_id, status (RUNNING/STOPPED), process_id, config |
| `trades` | Individual trade records | trade_id, market_1/2, entry_price, exit_price, pnl |
| `jobs` | Background task records | instance_id, job_type, status, result |

**Migrations**: Uses Alembic. New migrations auto-apply on startup.

---

## Debugging Checklist

**Bot won't start**:
- [ ] Check `.venv/bin/python` can import all modules: `python -c "from config import config; print(config())"`
- [ ] Verify `load_dotenv()` runs first in `main.py`
- [ ] Check `.env` file exists and has required vars (DB_HOST, REDIS_PORT if used)
- [ ] Review logs for missing `config.yaml`

**Orders not executing**:
- [ ] Verify testnet/mainnet flag matches dYdX credentials
- [ ] Check account balance (market_1 + market_2 capital required)
- [ ] Inspect `bot_agents.json` - what's the last status?
- [ ] Search logs for `SmartError` (precision/format issues)
- [ ] Check dYdX order status directly via API

**Positions not closing**:
- [ ] Verify `CLOSE_AT_ZSCORE_CROSS=true` in config
- [ ] Check Z-score calculation in logs (is it crossing zero?)
- [ ] Verify `reduce_only=true` flag on close orders
- [ ] Look for emergency cleanup messages if close failed

**WebSocket not updating**:
- [ ] Verify JWT token valid (hasn't expired)
- [ ] Check `ws://` (not `http://`) in connection URL
- [ ] Verify bot process is running and healthy
- [ ] Check firewall allows WebSocket connections

---

## Performance Tips

- **Cointegration analysis**: Expensive (weeks of candle data). Cache results in `cointegrated_pairs.json`. Re-run only on demand or scheduled.
- **Z-score calculation**: Fast. Recalculate every loop iteration to catch entry/exit signals.
- **Database queries**: Use indexes on `trade_id`, `status`, `opened_at` for large result sets.
- **WebSocket throughput**: Batch updates (don't send per-tick). Send every 1-5 seconds.
- **Backtesting**: Use Redis caching if available; disable for CI/testing to avoid startup overhead.

---

## Useful Make Targets

```bash
make test              # Run pytest suite
make lint              # Code linting (flake8 + pylint)
make format            # Auto-format with Black
make run               # Standalone bot (cd bot first)
make docker-up         # Full stack Docker Compose
make backtest-quick    # 1-month backtest for testing
```

---

## What Changed (Nov 2025 Update)

- **Bot location**: Confirmed `bot/` (not `app/`)
- **API focus**: FastAPI on port 8000 (not Go backend on 8888 - optional now)
- **Configuration**: YAML-first (`config.yaml`) instead of `.env`-only
- **State management**: Direct JSON (no pair_storage singleton yet - use `with open()`)
- **Database**: SQLAlchemy with auto-migrations (not raw SQL)
- **Frontend**: React 19 + Vite (not static dashboard)
