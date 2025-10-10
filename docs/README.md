# dYdX Trading Bot Documentation

Welcome to the comprehensive documentation for the dYdX v4 automated cointegration trading bot.

## 📖 Documentation Structure

### 🏗️ [Architecture](./architecture/)
- [System Overview](./architecture/system-overview.md) - High-level system architecture and components
- [Flow Diagrams](./architecture/flow-diagrams.md) - Visual flow diagrams and process flows
- [Data Flow](./architecture/data-flow.md) - How data moves through the system
- [State Management](./architecture/state-management.md) - Bot state and persistence

### 🔧 [API Documentation](./api/)
- [Core Modules](./api/core-modules.md) - Main trading bot modules
- [Configuration](./api/configuration.md) - Configuration system and classes
- [Connections](./api/connections.md) - dYdX client connections and networking
- [Trading Functions](./api/trading-functions.md) - Order management and execution
- [Utilities](./api/utilities.md) - Helper functions and utilities

### 🚀 [Deployment](./deployment/)
- [Docker Setup](./deployment/docker-setup.md) - Containerization and Docker deployment
- [Production Deployment](./deployment/production.md) - Production deployment best practices
- [CI/CD Pipeline](./deployment/cicd.md) - GitHub Actions and automation
- [Monitoring & Logging](./deployment/monitoring.md) - Grafana, Loki, and observability

### 📚 [User Guides](./guides/)
- [Quick Start](./guides/quick-start.md) - Get up and running quickly
- [Configuration Guide](./guides/configuration.md) - Complete configuration reference
- [Development Setup](./guides/development.md) - Setting up development environment
- [Troubleshooting](./guides/troubleshooting.md) - Common issues and solutions

### 📈 [Trading Strategy](./trading/)
- [Cointegration Theory](./trading/cointegration.md) - Statistical cointegration concepts
- [Strategy Implementation](./trading/strategy.md) - How the trading strategy works
- [Risk Management](./trading/risk-management.md) - Position sizing and risk controls
- [Performance Analysis](./trading/analysis.md) - Analyzing trading performance

## 🚀 Quick Navigation

| I want to... | Go to... |
|--------------|----------|
| **Get started quickly** | [Quick Start Guide](./guides/quick-start.md) |
| **Deploy with Docker** | [Docker Setup](./deployment/docker-setup.md) |
| **Configure the bot** | [Configuration Guide](./guides/configuration.md) |
| **Understand the strategy** | [Trading Strategy](./trading/strategy.md) |
| **Develop & contribute** | [Development Setup](./guides/development.md) |
| **Troubleshoot issues** | [Troubleshooting Guide](./guides/troubleshooting.md) |
| **Deploy in production** | [Production Deployment](./deployment/production.md) |

## 🔍 Key Concepts

- **Cointegration Trading**: Statistical arbitrage strategy that identifies pairs of assets with long-term statistical relationships
- **Z-Score Thresholds**: Entry/exit signals based on statistical deviations from the mean
- **Hedge Ratios**: Calculated ratios for optimal position sizing in paired trades
- **State Management**: Persistent tracking of open positions and trading pairs
- **Risk Controls**: Automated position limits and failsafe mechanisms

## 📊 System Requirements

- Python 3.12+
- Docker & Docker Compose (for containerized deployment)
- dYdX v4 account (testnet or mainnet)
- Telegram bot (for notifications)

## 🤝 Support

For questions, issues, or contributions:

1. Check the [Troubleshooting Guide](./guides/troubleshooting.md)
2. Review the [FAQ](./guides/faq.md)
3. Open an issue on GitHub
4. Refer to the [Development Guide](./guides/development.md) for contributions

---

**⚠️ Disclaimer**: This software is for educational purposes. Trading cryptocurrencies involves substantial risk of loss and is not suitable for every investor.