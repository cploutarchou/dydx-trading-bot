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
└─ func_messaging.py       # Telegram notifications
```

### Configuration System (YAML-first)
- **Primary path**: `app/config.yaml` → `config.py` (dataclasses) → `constants.py` (module constants)
- **Critical pattern**: Singleton `ConfigurationManager.get_config()` with type-safe hierarchy
- **Setup command**: `make config` creates template with placeholders
- **Network flexibility**: Supports unified `dydx:` block OR separate `dydx_testnet:`/`dydx_mainnet:` keys

### State Management 
- **`bot_agents.json`**: Active paired positions with order IDs, hedge ratios, Z-scores (empty array = no trades)
- **`cointegrated_pairs.csv`**: Statistical analysis results (p-values, half-lives, hedge ratios)
- **Persistence**: Files survive bot restarts, critical for position tracking

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
make setup install config    # Complete development environment
make run                     # Start bot (validates config + checks jurisdiction)
make test                    # Run pytest with PYTHONPATH=. 
make lint format            # flake8, pylint, mypy, bandit + black, isort
```

### Docker Deployment (Multi-stage)
```bash
# Production (optimized image)
make docker-build docker-run      # Build + run production container  

# Development (with dev tools)
make docker-build-dev docker-dev  # Interactive development container

# Monitoring stack  
make docker-up-logging            # Loki + Grafana for log aggregation
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
python scripts/close_open_positions.py    # Emergency position closure
python scripts/fast_cointegration.py --n 30  # Quick statistical analysis
```

### State Validation
```bash
# Check active positions
cat app/bot_agents.json | jq length        # Count of tracked pairs

# Verify statistical analysis
head -5 app/cointegrated_pairs.csv         # Recent cointegration results

# Monitor logs  
make docker-logs                          # Container output
# OR check Grafana: {job="dydx-trading-bot", level="error"}
```

### Jurisdiction & Connectivity
- **Startup check**: Bot tests market data access (HTTP 403 = geographical restriction)
- **Rate limiting**: Built-in delays prevent API throttling
- **Testnet safety**: Use `is_testnet: true` for safe testing with testnet funds

## Integration Points
- **dYdX v4**: `dydx-v4-client` library for all exchange operations
- **Statistical analysis**: `scipy`, `statsmodels` for cointegration tests (imported only when needed)
- **Telegram**: Real-time notifications for trades, errors, and system status
