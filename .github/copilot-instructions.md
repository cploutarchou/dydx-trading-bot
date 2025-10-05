# dYdX Trading Bot - AI Agent Instructions

## Project Overview
This is an automated cointegration trading bot for dYdX v4 decentralized exchange. The bot identifies statistically cointegrated cryptocurrency pairs, opens paired positions when Z-scores exceed thresholds, and closes positions when correlations revert to the mean.

## Architecture & Core Components

### Configuration System (YAML-based)
- **Primary config**: `app/config.yaml` - structured YAML configuration (preferred)
- **Legacy fallback**: `.env` file (deprecated, points users to YAML)
- **Config loading**: `app/config.py` - singleton pattern with dataclasses for type safety
- **Constants mapping**: `app/constants.py` - maps config to module-level constants
- Use `make config` to generate template configuration files

### Main Execution Flow (`app/main.py`)
1. **Configuration validation** - Load and validate config, exit on errors
2. **dYdX connection** - Connect to testnet/mainnet via multiple indexer endpoints
3. **Position cleanup** (optional) - Close all open positions if `ABORT_ALL_POSITIONS=true`
4. **Cointegration analysis** (optional) - Fetch 400+ hours of price data, calculate statistical relationships
5. **Continuous trading loop**:
   - Exit management: Monitor open pairs, close when Z-scores cross zero
   - Entry management: Scan for new trading opportunities based on Z-score thresholds

### Client Connection Pattern (`func_connections.py`)
- **Custom Client class**: Wraps multiple dYdX client types (indexer, account, node, wallet)
- **Endpoint logic**: Uses mainnet indexer for price data regardless of testnet/mainnet trading
- **Jurisdiction check**: Validates API access (dYdX blocks certain countries)
- **Connection hierarchy**: `indexer` (market data) → `indexer_account` (positions) → `node` (orders) → `wallet` (signing)

### Statistical Trading Engine

#### Cointegration Analysis (`func_cointegration.py`)
- **Pair discovery**: Tests all market combinations for statistical cointegration
- **Key metrics**: P-value < 0.05, half-life ≤ 24 hours, hedge ratio calculation
- **Output**: `cointegrated_pairs.csv` with tradeable pairs and their parameters
- **Z-score calculation**: Rolling window (21 periods) for entry/exit signals

#### Trade Entry Logic (`func_entry_pairs.py`)
- **Trigger**: |Z-score| ≥ 1.5 (configurable via `ZScoreThreshold`)
- **Position sizing**: Fixed USD amount per trade (`USD_PER_TRADE`)
- **Market checks**: Validates minimum order sizes, tick sizes, collateral requirements
- **BotAgent pattern**: Each pair trade managed as a state machine instance

#### Trade Exit Logic (`func_exit_pairs.py`)
- **Exit condition**: Z-score crosses zero (mean reversion complete)
- **State persistence**: `bot_agents.json` tracks all open paired positions
- **Order matching**: Validates exchange records match local state before closing
- **Failsafe logic**: Force-exits if position mismatches detected

### Order Management (`func_private.py`)
- **Market orders only**: Uses market orders with price bounds for reliability
- **Order tracking**: Polls order status, handles cancellations and failures
- **Size formatting**: Respects exchange tick sizes and step sizes via `format_number()`
- **Failsafe prices**: Wide price bounds (±70%) to ensure fills in volatile conditions

### State Management Patterns

#### Bot Agent State Machine (`func_bot_agent.py`)
- **Atomic pair trading**: Opens both positions or fails completely
- **Error handling**: Closes first position if second position fails
- **Status tracking**: `FAILED`, `LIVE`, `CLOSE`, `ERROR` states
- **Telegram integration**: Sends critical failure alerts

#### Persistent State Files
- **`bot_agents.json`**: Active paired positions with hedge ratios, Z-scores, order IDs
- **`cointegrated_pairs.csv`**: Statistical analysis results for pair selection
- **Empty `bot_agents.json`** indicates no open positions (reset after cleanup)

## Development Workflows

### Configuration Setup
```bash
make config          # Creates app/config.yaml with defaults
make env            # Creates legacy .env (redirects to YAML)
```

### Running the Bot
```bash
cd app && python main.py    # Main trading loop
python test.py             # Test single order placement
```

### Key Configuration Parameters
- **Trading thresholds**: `ZScoreThreshold` (1.5), `maxHalfLife` (24h), `statsWindow` (21)
- **Position sizing**: `usdPerTrade` (10), `usdMinCollateral` (100)
- **Behavior flags**: `abortAllPositions`, `findCointegratedPairs`, `manageExits`, `placeTrades`
- **Network selection**: `is_testnet` (false for mainnet)

### Error Handling Patterns
- **Critical failures**: Exit immediately with status code 1 and Telegram alert
- **API rate limiting**: 0.2-0.5 second delays between dYdX API calls
- **Order failures**: Implement failsafe closure logic to prevent orphaned positions
- **Jurisdiction errors**: HTTP 403 indicates geographical restriction

## Integration Points
- **dYdX v4 API**: Uses `dydx-v4-client` for all exchange interactions
- **Telegram alerts**: Sends startup confirmations and critical error notifications
- **Statistical libraries**: `statsmodels` for cointegration tests, `pandas` for data manipulation
- **File-based state**: JSON and CSV files for persistence across bot restarts

## Testing & Debugging
- **Test mode**: Use `is_testnet: true` for safe testing with testnet funds
- **Debug workflow**: Check `cointegrated_pairs.csv` for statistical analysis results
- **Position validation**: Verify `bot_agents.json` matches exchange open positions
- **Connection testing**: Bot performs jurisdiction/connectivity checks on startup