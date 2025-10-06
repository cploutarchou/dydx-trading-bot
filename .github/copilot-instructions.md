# dYdX Trading Bot - AI Agent Instructions

## Project Overview
Automated cointegration trading bot for dYdX v4 decentralized exchange. Identifies statistically cointegrated cryptocurrency pairs, opens paired positions when Z-scores exceed thresholds, and closes positions when correlations revert to the mean.

## Key Architecture Patterns

### Configuration System (YAML-first)
- **Primary**: `app/config.yaml` → `app/config.py` (dataclasses) → `app/constants.py` (module constants)
- **Legacy**: `.env` file (deprecated, redirects to YAML)
- **Setup**: `make config` creates template with defaults
- **Pattern**: Singleton ConfigurationManager with type-safe dataclass hierarchy

### Execution Flow (`app/main.py`)
1. Config validation → 2. dYdX connection → 3. Optional position cleanup → 4. Optional cointegration analysis → 5. Continuous trading loop (exits then entries)

### Client Architecture (`func_connections.py`)
- **Custom Client wrapper**: Bundles `indexer` (market data) + `indexer_account` (positions) + `node` (orders) + `wallet` (signing)
- **Critical pattern**: Always uses mainnet indexer for price data, regardless of testnet/mainnet trading
- **Jurisdiction validation**: HTTP 403 = geographical restriction

### Trading Engine Components

#### Cointegration Analysis (`func_cointegration.py`)
- Tests all market pairs for statistical cointegration (p-value < 0.05, half-life ≤ 24h)
- Output: `cointegrated_pairs.csv` with hedge ratios and Z-score parameters
- Uses 21-period rolling window for Z-score calculations

#### Entry/Exit Logic (`func_entry_pairs.py`, `func_exit_pairs.py`)
- **Entry trigger**: |Z-score| ≥ 1.5, creates paired positions via BotAgent state machine
- **Exit trigger**: Z-score crosses zero (mean reversion)
- **State file**: `bot_agents.json` tracks active pairs with hedge ratios, order IDs
- **Failsafe**: Force-close positions on exchange/local state mismatches

#### Order Management (`func_private.py`)
- Market orders only with ±70% price bounds for reliability
- Respects exchange tick/step sizes via `format_number()`
- 0.2-0.5s delays between API calls for rate limiting

#### BotAgent State Machine (`func_bot_agent.py`)
- Manages atomic pair trades: both positions succeed or entire trade fails
- States: `FAILED`, `LIVE`, `CLOSE`, `ERROR` with Telegram notifications
- Handles order polling, cancellations, and cleanup logic

### State Files
- **`bot_agents.json`**: Active paired positions (empty array = no open trades)
- **`cointegrated_pairs.csv`**: Statistical analysis results
- **Key pattern**: Files persist state across bot restarts

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

### Virtual Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -q      # Run tests
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