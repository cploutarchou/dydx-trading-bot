# dYdX Trading Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/dYdX-v4-green.svg" alt="dYdX Version">
  <img src="https://img.shields.io/badge/Strategy-Cointegration-purple.svg" alt="Strategy">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

## 🎯 Overview

**dYdX Trading Bot** is a sophisticated automated trading system that implements statistical arbitrage through cointegration analysis on the dYdX v4 decentralized exchange. The bot identifies pairs of cryptocurrency assets with long-term statistical relationships and profits from temporary deviations that tend to revert to the mean.

### Key Features

- 🔬 **Statistical Cointegration Analysis** - Uses Engle-Granger methodology to identify tradeable pairs
- 📊 **Z-Score Based Signals** - Enters trades when deviations exceed statistical thresholds
- 🤖 **Automated Execution** - Handles paired trades with atomic order management
- 🛡️ **Risk Management** - Built-in position limits and failsafe mechanisms
- 🐳 **Docker Ready** - Complete containerization with production deployment support
- 📈 **Comprehensive Monitoring** - Grafana Loki integration for observability
- ⚙️ **YAML Configuration** - Type-safe, validated configuration system

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- dYdX v4 account (testnet or mainnet)
- Telegram bot (for notifications)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd dydx-trading-bot

# Set up development environment
make setup install

# Create configuration
make config
# Edit app/config.yaml with your credentials

# Run tests
make test

# Start the bot
make run
```

### Docker Quick Start

```bash
# Build and run with Docker
make docker-build
make docker-run

# Or use Docker Compose (recommended)
make docker-up
```

## 📖 Documentation

Comprehensive documentation is available in the [`docs/`](./docs/) directory:

### 📚 **[Complete Documentation Index](./docs/README.md)**

### 🎯 Quick Navigation

| I want to... | Go to... |
|--------------|----------|
| **Get started quickly** | [Quick Start Guide](./docs/guides/quick-start.md) |
| **Configure the bot** | [Configuration Guide](./docs/guides/configuration.md) |
| **Deploy with Docker** | [Docker Setup](./docs/deployment/docker-setup.md) |
| **Understand the strategy** | [Trading Strategy](./docs/trading/strategy.md) |
| **Troubleshoot issues** | [Troubleshooting Guide](./docs/guides/troubleshooting.md) |
| **Develop & contribute** | [Development Guide](./docs/guides/development.md) |
| **View system architecture** | [Architecture Overview](./docs/architecture/system-overview.md) |
| **Check API documentation** | [API Reference](./docs/api/core-modules.md) |

## 🏗️ Architecture

The bot implements a sophisticated multi-component architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                        dYdX Trading Bot                         │
├─────────────────────────────────────────────────────────────────┤
│  Configuration │     Logging     │   Messaging   │ Monitoring   │
│     System     │     System      │  (Telegram)   │   (Grafana)  │
├─────────────────────────────────────────────────────────────────┤
│  Data Pipeline │ Cointegration  │ Trading Engine│ Risk Manager │
│ (Market Data)  │    Analysis     │  (Execution)  │  (Controls)  │
├─────────────────────────────────────────────────────────────────┤
│ State Management │ Order Manager │   dYdX v4 Client Layer      │
│  (Persistence)   │  (BotAgent)   │  (Indexer│Node│Wallet)      │
└─────────────────────────────────────────────────────────────────┘
```

**[📊 View Detailed Architecture](./docs/architecture/system-overview.md)**

## 📈 Trading Strategy

The bot implements a **cointegration-based pairs trading strategy**:

1. **📊 Statistical Analysis** - Identifies cointegrated cryptocurrency pairs using the Engle-Granger test
2. **🎯 Signal Generation** - Calculates Z-scores from price spreads to generate entry/exit signals  
3. **⚡ Trade Execution** - Opens paired positions when |Z-score| ≥ 1.5
4. **🔄 Mean Reversion** - Closes positions when Z-score crosses zero (mean reversion)
5. **🛡️ Risk Controls** - Enforces position limits and account balance requirements

**[📖 Learn More About the Strategy](./docs/trading/strategy.md)**

## ⚙️ Configuration

The bot uses a modern YAML-based configuration system. Create your configuration file:

```bash
# Generate configuration template
make config
```

This creates `app/config.yaml` with the following structure:

```yaml
# Network Configuration
is_testnet: true  # false for mainnet

# dYdX Connection
dydx:
  dydx_chain_address: "dydx1..."
  dydx_chain_secret: "word1 word2 word3..."

# Telegram Notifications  
telegram:
  token: "123456789:ABCDEF..."
  chat_id: "123456789"

# Trading Parameters
botSettings:
  findCointegratedPairs: true
  manageExits: true
  placeTrades: true
  ZScoreThreshold: 1.5
  usdPerTrade: 10.0
  # ... more settings

# Logging & Monitoring
logging:
  level: "INFO"
  loki:
    enabled: false  # Enable for Grafana integration
```

**[📋 Complete Configuration Guide](./docs/guides/configuration.md)**

### Legacy Configuration (.env - deprecated)

**⚠️ WARNING: .env configuration is deprecated**  
**➡️ Please migrate to app/config.yaml using: `make config`**  
**📖 Documentation: [Configuration Guide](./docs/guides/configuration.md)**

## 🐳 Docker Deployment

### Production Deployment

```bash
# Production deployment with Docker Compose
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

### Development Environment

```bash
# Start development container
make docker-up-dev

# Interactive development
make docker-dev

# Run tests in container
make docker-test
```

### Monitoring Stack

```bash
# Deploy with Grafana Loki monitoring
make docker-up-logging

# Access Grafana dashboard
open http://localhost:3000
```

**[🐳 Complete Docker Guide](./docs/deployment/docker-setup.md)**

## 🛠️ Development

### Local Development Setup

```bash
# Set up virtual environment
make setup

# Install dependencies
make install

# Run linting and formatting
make lint format

# Run tests
make test

# Start bot in development mode
make run
```

### Recommended local setup (virtualenv)

Create a virtual environment and install dependencies before running the bot:

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

### Project Structure

```
dydx-trading-bot/
├── app/                    # Main application code
│   ├── main.py            # Entry point
│   ├── config.py          # Configuration management
│   ├── func_*.py          # Core trading modules
│   └── config.yaml        # Configuration file
├── docs/                   # Comprehensive documentation
├── scripts/                # Utility scripts
├── tests/                  # Test suite
├── docker-compose.yml      # Docker orchestration
├── Dockerfile             # Multi-stage container image
├── Makefile              # Development automation
└── requirements.txt       # Python dependencies
```

**[🔧 Development Guide](./docs/guides/development.md)**

## 📊 Key Metrics & Parameters

### Configuration Parameters

#### dYdX Settings

- `dydx_chain_address`: Your dYdX chain address
- `dydx_chain_secret`: Your secret phrase (mnemonic)  
- `is_testnet`: Whether to use testnet (true) or mainnet (false)

#### Telegram Settings

- `token`: Your Telegram bot token
- `chat_id`: Your Telegram chat ID

#### Bot Settings

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

#### Logging Settings

- `logging.level`: Global log level (e.g., `INFO`, `DEBUG`)
- `logging.loki.enabled`: Enable or disable shipping logs to Grafana Loki
- `logging.loki.url`: Base URL for your Grafana Loki instance
- `logging.loki.username`: Grafana Cloud stack user
- `logging.loki.password`: Grafana Cloud API token with `logs:write` scope
- `logging.loki.tenant_id`: Optional tenant ID for multi-tenant Loki deployments
- `logging.loki.labels`: Key/value pairs applied to each log line

## ⚠️ Disclaimer

**IMPORTANT**: This software is provided for educational and research purposes only. 

- **Trading Risk**: Cryptocurrency trading involves substantial risk of loss and is not suitable for every investor
- **No Financial Advice**: This bot does not constitute financial advice or investment recommendations  
- **Use at Your Own Risk**: Users are solely responsible for their trading decisions and outcomes
- **No Warranties**: The software is provided "AS IS" without any warranties or guarantees
- **dYdX Terms**: Ensure compliance with dYdX's terms of service and your local regulations

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.

---

<p align="center">
  Made with ❤️ for the DeFi community
</p>
