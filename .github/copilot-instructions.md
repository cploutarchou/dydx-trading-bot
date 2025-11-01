# dYdX Trading Bot - AI Coding Agent Instructions

**Bot-Focused Guide** - Essential patterns, workflows, and architecture for the dYdX trading bot engine.

## Bot Overview

Statistical arbitrage trading bot for dYdX v4 that executes paired trades based on cointegration analysis.

**Key Architecture**:
- **Paired Trading**: All trades consist of TWO positions (base + quote markets) executed atomically
- **Statistical Analysis**: Uses Engle-Granger cointegration test to identify mean-reverting pairs  
- **State Persistence**: JSON files (`bot_agents.json`, `cointegrated_pairs.json`) survive restarts
- **Configuration-Driven**: All behavior controlled via YAML flags - no code changes needed

## ⚠️ Critical Startup Sequence

**Environment loading is CRITICAL** - `main.py` loads `.env` before any other imports to ensure DB/Redis variables are available to config loader:

```python
# ⚠️ CRITICAL: Load environment variables FIRST, before any other imports
from dotenv import load_dotenv
load_dotenv()

# Only AFTER load_dotenv() can we import modules that depend on env vars
import asyncio
import logging
from config import config  # ← This reads DB_*, REDIS_* from environment
```

**Why this matters**: Configuration system expects environment variables to be loaded before `config()` is called. Importing modules in wrong order causes missing database connections and Redis cache failures.

## Core Bot Components

### Trading Loop (`main.py`)
```
setup_logging() → validate config → connect_dydx()
→ [FIND_COINTEGRATED_PAIRS] construct_market_prices() → store_cointegration_results()
→ MAIN LOOP:
    ├─ [MANAGE_EXITS] manage_trade_exits()      # Check bot_agents.json, close on Z-score cross
    └─ [PLACE_TRADES] open_positions()          # Load cointegrated_pairs.json, find Z-score triggers
```

### Key Files

| File                     | Purpose                                                | Key Patterns                                                    |
| ------------------------ | ------------------------------------------------------ | --------------------------------------------------------------- |
| `main.py`                | Entry point - orchestrates full trading loop          | `load_dotenv()` FIRST, then `setup_logging()`, then config     |
| `constants.py`           | Single source of truth for all config values          | **Always import from here, never call config() in functions**  |
| `config.py`              | YAML-based configuration with environment overrides   | Singleton pattern: `ConfigurationManager.get_config()`         |
| `func_cointegration.py`  | Statistical analysis with confidence scoring           | `SmartError` for graceful degradation, `MIN_RETURN_STD` filter |
| `func_bot_agent.py`      | Atomic paired order executor                          | **BOTH orders must succeed or entire pair fails**               |
| `func_entry_pairs.py`    | Load pairs, find Z-score triggers                     | Read `cointegrated_pairs.json`, create `BotAgent` instances     |
| `func_exit_pairs.py`     | Monitor positions, close on mean reversion            | Poll `bot_agents.json`, check Z-score crosses zero             |
| `func_connections.py`    | dYdX client wrapper                                   | 4 components: indexer, indexer_account, node, wallet           |
| `func_messaging.py`      | Telegram notifications                                | HTML-formatted messages with Mintscan account links            |
| `logging_setup.py`       | Custom logging with Loki integration                  | Call `setup_logging()` FIRST in any new script                 |

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
  abortAllPositions: false     # Emergency: close all positions on startup
  findCointegratedPairs: true  # Run cointegration analysis
  manageExits: true           # Monitor and close positions
  placeTrades: true           # Execute new trades
  ZScoreThreshold: 1.5        # Entry trigger threshold
  maxHalfLife: 24            # Maximum mean reversion period (hours)
  usdPerTrade: 10.0          # Position size per trade
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

## Bot Workflows

### Running the Bot
```bash
# Standard operation
python main.py

# Environment override
ABORT_ALL_POSITIONS=true python main.py

# Docker (recommended)
make docker-run
```

### Emergency Operations
```bash
# Emergency: Close all positions immediately
python -c "
import asyncio
from constants import config
from func_connections import connect_dydx  
from func_private import abort_all_positions
async def emergency(): 
    client = await connect_dydx()
    await abort_all_positions(client)
asyncio.run(emergency())
"
```

### State Inspection
```bash
# Check active positions
cat bot_agents.json | jq length

# Check cointegrated pairs 
cat cointegrated_pairs.json | jq '.metadata'

# Check confidence scores
cat cointegrated_pairs.json | jq '.pairs[].confidence_score'
```

## Integration Points

### dYdX Client (`func_connections.py`)
```python
class Client:
    indexer          # Market data (always mainnet for better liquidity data)
    indexer_account  # Account queries (testnet/mainnet based on config)
    node            # Chain operations (matches account endpoint)
    wallet          # Transaction signing (optional for backtesting)
```

### Telegram Integration (`func_messaging.py`)
- **Professional Format**: HTML-formatted messages with clickable links
- **Error Classification**: `is_critical` parameter determines response urgency
- **Account Integration**: Links to Mintscan explorer based on testnet/mainnet

### Logging (`logging_setup.py`) 
- **Loki Integration**: Custom HTTP implementation (logging_loki fails silently)
- **Environment Awareness**: Dev vs prod authentication handling
- **Call First**: Always `setup_logging()` before any other logging calls

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
