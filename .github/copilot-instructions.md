# dYdX Trading Bot - AI Agent Instructions

## Project Overview

Automated cointegration pairs trading bot for dYdX v4 decentralized exchange. Uses statistical analysis to identify mean-reverting cryptocurrency pairs, opens paired positions when Z-scores exceed thresholds (±1.5), and closes when correlations revert to the mean (Z-score crosses zero).

## Architecture & Data Flow

### Core Components (`app/`)

```
main.py → setup_logging() → config validation → connect_dydx() → trading loop
├─ func_cointegration.py   # Statistical analysis & pair identification  
├─ func_entry_pairs.py     # Trade entry logic & BotAgent orchestration
├─ func_exit_pairs.py      # Position monitoring & mean reversion exits
├─ func_bot_agent.py       # Atomic paired order state machine
├─ func_connections.py     # dYdX client wrapper (indexer+node+wallet)
├─ func_private.py         # Order placement & account queries
├─ func_messaging.py       # Telegram notifications
└─ models/
   ├─ pair_storage.py      # Enhanced JSON-first pair storage with CSV fallback
   └─ __init__.py          # Model package initialization
```

### Configuration System (YAML-first)

- **Primary path**: `app/config.yaml` → `config.py` (dataclasses) → `constants.py` (module constants)
- **Critical pattern**: Singleton `ConfigurationManager.get_config()` with type-safe hierarchy
- **Setup command**: `make config` creates template with placeholders
- **Environment detection**: Top-level `environment: "development"/"production"` flag
- **Network flexibility**: Supports unified `dydx:` block OR separate `dydx_testnet:`/`dydx_mainnet:` keys

### Enhanced State Management

- **`bot_agents.json`**: Active paired positions with order IDs, hedge ratios, Z-scores (empty array = no trades)
- **`cointegrated_pairs.json`**: Primary storage with metadata, confidence scores, timestamps (v2.0 format)
- **`cointegrated_pairs.csv`**: Legacy compatibility for existing workflows
- **`pair_history/`**: Timestamped backups with automatic cleanup (7-day retention)
- **Persistence**: All files survive bot restarts, critical for position tracking

## Trading Logic Deep Dive

### BotAgent State Machine (`func_bot_agent.py`)

```python
# States: FAILED, LIVE, CLOSE, ERROR
# Atomic execution: both orders succeed or entire pair fails with cleanup
class BotAgent:
    async def open_trades(self):
        # 1. Place market_1 order, verify FILLED
        # 2. Place market_2 order, verify FILLED  
        # 3. If market_2 fails → emergency close market_1 (failsafe_price)
        # 4. Critical failures → exit(1) with Telegram alert
```

### Entry Logic Flow (`func_entry_pairs.py`)

```python
# Load cointegrated_pairs.csv → calculate current Z-scores → trigger trades
if |z_score| >= ZSCORE_THRESH:  # Default 1.5
    base_side = "BUY" if z_score < 0 else "SELL"
    quote_side = "BUY" if z_score > 0 else "SELL"  # Opposite direction
    # Position sizing: USD_PER_TRADE (default $10) converted to asset quantities
```

### Exit Logic Flow (`func_exit_pairs.py`)

```python
# Monitor bot_agents.json positions → recalculate Z-scores → close on mean reversion
if CLOSE_AT_ZSCORE_CROSS and z_score crosses zero:
    # Place reduce_only=True market orders for both positions
    # Critical: Validate exchange state matches local state before closing
```

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
make setup install config    # Complete development environment + config template
make run                     # Start bot foreground (validates config + checks jurisdiction)
make start stop restart      # Background bot control via scripts/manage_bot.sh
make status logs            # Check bot status and view recent activity
make test lint format       # Testing + code quality (pytest, flake8, pylint, mypy, black)
```

### Docker Deployment (Multi-stage)

```bash
# Production deployment
make docker-build docker-run      # Build + run optimized production container
make docker-up docker-down        # Docker Compose orchestration with persistence

# Development containers  
make docker-build-dev docker-dev  # Interactive dev container with live mounts
make devcontainer               # VS Code Dev Container (recommended)

# Monitoring & debugging
make docker-up-logging          # Loki + Grafana stack (localhost:3000)
make test-loki-dev test-loki-prod  # Test log aggregation connectivity
```

### Enhanced Storage System (`models/pair_storage.py`)

```python
# JSON-first storage with automatic CSV compatibility
from app.models.pair_storage import pair_storage, CointegrationResult

# Save pairs (creates JSON + CSV + timestamped backup)
pairs = [CointegrationResult(...)]  # With confidence_score, timestamps
pair_storage.save_pairs(pairs)

# Load with format detection (JSON preferred, CSV fallback)
pairs = pair_storage.load_pairs()
high_confidence = pair_storage.get_high_confidence_pairs()  # score >= 0.7
```

### Critical File Patterns

- **Logging initialization**: ALWAYS call `setup_logging()` first in any script
- **Module imports**: Use `logger = logging.getLogger(__name__)` pattern
- **API rate limiting**: 0.2-0.5s delays (`time.sleep()`) between dYdX calls
- **Number formatting**: Use `format_number(value, tick_size)` for exchange precision
- **Error handling**: Critical failures call `exit(1)` + send Telegram alerts

## Configuration & Constants

### Key Parameters (`app/config.yaml`)

```yaml
botSettings:
  ZScoreThreshold: 1.5        # Entry trigger threshold  
  statsWindow: 21             # Rolling window for Z-score calculation
  maxHalfLife: 24             # Max half-life hours for cointegration
  usdPerTrade: 10.0          # Position size per trade
  usdMinCollateral: 100.0    # Required account balance
  closeAtZscoreCross: true   # Exit on mean reversion
```

### Behavioral Flags

```yaml  
botSettings:
  abortAllPositions: false      # Close all positions on startup
  findCointegratedPairs: true   # Run statistical analysis
  manageExits: true            # Monitor existing positions  
  placeTrades: true            # Execute new trades
```

## Logging & Monitoring (`logging_setup.py`)

### Custom Loki Integration

```python
# Uses direct HTTP requests (not logging_loki library which fails silently)
# Log levels sent as stream labels: {job="dydx-trading-bot", level="error"}
# Grafana queries: {job="dydx-trading-bot"} |= "CRITICAL"
```

### Production Logging Pattern

- **Console handler**: Always active for development/debugging
- **Loki handler**: Optional remote aggregation (requires auth in production)
- **Environment detection**: Auto-configures based on `environment: "production"`

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
make docker-up-logging                     # Full observability stack
# Grafana queries: {job="dydx-trading-bot", level="error"} |= "CRITICAL"
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
app/func_backtesting.py         # BacktestEngine simulation engine
app/models/backtest_models.py   # BacktestResult, BacktestTrade dataclasses
app/models/backtest_storage.py  # JSON storage with singleton pattern
scripts/run_backtest.py         # Main backtesting execution script
scripts/analyze_backtest_results.py  # Performance analysis and reporting
```

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
```

### Backtesting Configuration (`app/config.yaml`)

```yaml
backtesting:
  # Historical data settings
  candleResolution: "1HOUR"      # 1MIN, 5MINS, 15MINS, 1HOUR, 4HOURS, 1DAY
  maxHistoryDays: 90             # Maximum lookback period
  
  # Simulation parameters
  startingBalance: 1000.0        # USD starting capital for simulation
  transactionFee: 0.0005         # 0.05% per trade (dYdX maker fee)
  slippage: 0.001               # 0.1% estimated slippage
  
  # Analysis settings
  benchmarkSymbol: "BTC-USD"     # Benchmark for Sharpe ratio calculation
  riskFreeRate: 0.02            # Annual risk-free rate (2%)
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
