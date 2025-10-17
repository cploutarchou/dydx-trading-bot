# dYdX Trading Bot - AI Agent Instructions

## Project Overview

Automated cointegration pairs trading bot for dYdX v4 decentralized exchange. Uses statistical analysis to identify mean-reverting cryptocurrency pairs, opens paired positions when Z-scores exceed thresholds (±1.5), and closes when correlations revert to the mean (Z-score crosses zero).

**Key fact**: This is a **paired trading bot** - all trades consist of TWO positions (base + quote markets) executed atomically via `BotAgent`. Single position failures trigger emergency cleanup of the paired position.

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

| File                     | Purpose                                                                      | Input                                   | Output                                  |
| ------------------------ | ---------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------- |
| `func_cointegration.py`  | Statistical analysis (ADF, Johansen tests, Z-score calc)                     | Market prices DataFrame                 | `cointegrated_pairs.json` + CSV         |
| `func_entry_pairs.py`    | Load pairs, find Z-score triggers, spawn `BotAgent` instances                | `cointegrated_pairs.json` + market data | Trades written to `bot_agents.json`     |
| `func_exit_pairs.py`     | Monitor `bot_agents.json`, recalculate Z-scores, close on mean reversion     | `bot_agents.json` + market data         | Position state updates                  |
| `func_bot_agent.py`      | Atomic paired order executor - BOTH orders must succeed or entire pair fails | BotAgent init params                    | Order state dict in JSON                |
| `func_connections.py`    | dYdX client wrapper managing indexer/node/wallet lifecycle                   | Config credentials                      | `Client` object (indexer, node, wallet) |
| `func_private.py`        | Account queries, order placement, cancellations                              | Client + order params                   | Order confirmations, filled status      |
| `func_public.py`         | Market data API (candles, markets list, prices)                              | Client + market symbols                 | Price series, market metadata           |
| `models/pair_storage.py` | JSON-first persistence with CSV backward compatibility                       | `CointegrationResult` dataclass list    | JSON + CSV files + timestamped backups  |

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

**Critical pattern**: Validate exchange state matches local state before closing (reconciliation step).

### dYdX Client Architecture (`func_connections.py`)

```python
class Client:
    indexer          # Market data (always mainnet for better liquidity data)
    indexer_account  # Position/balance queries (testnet/mainnet based on is_testnet)
    node             # Order placement (testnet connection regardless of trading mode)
    wallet           # Transaction signing
```

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

## Critical Developer Patterns

### Logging Initialization

**Always call `setup_logging()` first in any script**:

```python
from logging_setup import setup_logging
import logging

setup_logging()  # Must be first - initializes Loki, console, file handlers
logger = logging.getLogger(__name__)
logger.info("Script started")
```

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

**Critical errors: log, alert Telegram, then exit(1)**:

```python
try:
    result = await some_critical_operation()
except Exception as e:
    logger.error("Critical failure: %s", e)
    messenger.send_error_message("Operation Failed", str(e), is_critical=True)
    exit(1)  # Don't allow bot to continue with orphaned state
```

### Async Pattern

**All dYdX API calls use async/await pattern**:

````python
async def some_function(client):
    # Use await for client calls
    markets = await get_markets(client)
    order = await place_market_order(client, market, side, size)
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

## Integration Points

- **dYdX v4**: `dydx-v4-client` library for all exchange operations
- **Statistical analysis**: `scipy`, `statsmodels` for cointegration tests (imported only when needed)
- **Telegram**: Real-time notifications for trades, errors, and system status
- **Backtesting**: Historical simulation using same trading logic, risk-free strategy validation
- **Backend API**: FastAPI server (`backend/main.py`) with SQLAlchemy ORM for backtest storage
- **Frontend**: React/TypeScript dashboard (`frontend/src/`) with Zustand auth store for backtest visualization
