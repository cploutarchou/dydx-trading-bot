# dydx-trading-bot

## Overview

This is a trading bot for the dYdX decentralized exchange, using cointegration strategy to find trading opportunities.

## Configuration

There are two ways to configure the bot:

### 1. Using Environment Variables (Legacy)

You can create a `.env` file with the required configuration using:

```bash
make env
```

This will create a `.env` file with default values that you can edit.

### 2. Using YAML Configuration (Recommended)

You can create a `config.yaml` file with the required configuration using:

```bash
make config
```

### Recommended local setup (virtualenv)

Create a virtual environment and install dependencies before running the bot. Example (macOS / zsh):

```bash
# create venv
python3 -m venv .venv
# activate
source .venv/bin/activate
# upgrade pip (you may see a message to upgrade; upgrading to latest pip is recommended)
python -m pip install --upgrade pip
# install requirements
pip install -r requirements.txt
# run tests
PYTHONPATH=. pytest -q
# run bot
. .venv/bin/activate
python app/main.py
```

Note: heavy scientific libraries (scipy/statsmodels) are imported only when cointegration calculations run. This speeds up lightweight commands and tests.

This will create a `config.yaml` file in the app directory with default values that you can edit. The YAML configuration provides a more structured and maintainable way to configure the bot.

## Configuration Parameters

### dYdX Settings

- `dydx_chain_address`: Your dYdX chain address
- `dydx_secret_phrase`: Your secret phrase (mnemonic)
- `is_testnet`: Whether to use testnet (true) or mainnet (false)

### Telegram Settings

- `token`: Your Telegram bot token
- `chat_id`: Your Telegram chat ID

### Bot Settings

- `abortAllPositions`: Whether to abort all positions on startup
- `findCointegratedPairs`: Whether to find cointegrated pairs
- `manageExits`: Whether to manage exits
- `placeTrades`: Whether to place trades
- `resolutionTimeframe`: The timeframe for resolution (e.g., "1HOUR")
- `strategy`: The trading strategy (e.g., "cointegration")
- `statsWindow`: The window for statistics
- `maxHalfLife`: Maximum half-life for cointegration
- `ZScoreThreshold`: Z-score threshold for opening positions
- `usdPerTrade`: USD amount per trade
- `usdMinCollateral`: Minimum USD collateral
- `closeAtZscoreCross`: Whether to close at Z-score cross
- `indexer_endpoint`: Endpoints for the indexer (testnet and mainnet)

### Logging Settings

- `logging.level`: Global log level (e.g., `INFO`, `DEBUG`).
- `logging.loki.enabled`: Enable or disable shipping logs to Grafana Loki.
- `logging.loki.url`: Base URL for your Grafana Loki instance (for Grafana Cloud, omit the trailing `/loki/api/v1/push`).
- `logging.loki.username`: Grafana Cloud stack user (e.g., `1354229`).
- `logging.loki.password`: Grafana Cloud API token with `logs:write` scope.
- `logging.loki.tenant_id`: Optional tenant ID for multi-tenant Loki deployments.
- `logging.loki.labels`: Key/value pairs applied to each log line (for example, `app` or `environment`).
