# System Architecture Overview

## 🎯 Executive Summary

The dYdX Trading Bot is a sophisticated automated trading system implementing statistical arbitrage through cointegration analysis. The system identifies pairs of cryptocurrencies with long-term statistical relationships, executes paired trades when deviations exceed thresholds, and closes positions when correlations revert to the mean.

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        dYdX Trading Bot                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Configuration │  │     Logging     │  │   Messaging     │ │
│  │     System      │  │     System      │  │   (Telegram)    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  Data Pipeline  │  │ Cointegration  │  │ Trading Engine  │ │
│  │   (Market Data) │  │    Analysis     │  │   (Execution)   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ State Management│  │  Order Manager  │  │  Risk Manager   │ │
│  │  (Persistence)  │  │   (BotAgent)    │  │   (Controls)    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  dYdX v4 Client Layer                      │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │ │
│  │  │   Indexer   │ │    Node     │ │       Wallet        │  │ │
│  │  │(Market Data)│ │ (Orders)    │ │     (Signing)       │  │ │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 Core Components

### 1. Configuration System (`app/config.py`)
**Purpose**: Centralized YAML-based configuration management
- **Dataclass Hierarchy**: Type-safe configuration structures
- **Environment Support**: Testnet/mainnet configurations
- **Migration Path**: Legacy .env file support
- **Validation**: Runtime configuration validation

### 2. Connection Layer (`app/func_connections.py`)
**Purpose**: dYdX v4 client management and connection pooling
- **Multi-Client Architecture**: Separate indexer, account, node, and wallet clients
- **Market Data Strategy**: Always uses mainnet indexer for price data
- **Jurisdiction Checking**: Validates geographical access restrictions
- **Connection Pooling**: Manages client lifecycle and reconnection

### 3. Data Pipeline (`app/func_public.py`)
**Purpose**: Market data acquisition and historical price construction
- **Real-time Data**: Current market prices and candles
- **Historical Data**: Multi-timeframe historical price matrices
- **Data Normalization**: Consistent price series formatting
- **Rate Limiting**: API protection with intelligent delays

### 4. Cointegration Engine (`app/func_cointegration.py`)
**Purpose**: Statistical analysis for identifying trading opportunities
- **Cointegration Testing**: Engle-Granger methodology with p-value validation
- **Half-Life Calculation**: Mean reversion speed analysis
- **Z-Score Computation**: Rolling window statistical deviation
- **Pair Selection**: Automated filtering and ranking

### 5. Trading Engine
#### Entry Manager (`app/func_entry_pairs.py`)
**Purpose**: Identifies and executes new trading opportunities
- **Signal Detection**: Z-score threshold monitoring
- **Position Sizing**: Dynamic sizing based on volatility and account balance
- **Pair Validation**: Market availability and liquidity checks
- **Execution Coordination**: Manages paired order placement

#### Exit Manager (`app/func_exit_pairs.py`)
**Purpose**: Manages position closure and profit realization
- **Mean Reversion Detection**: Z-score cross-zero monitoring
- **Position Reconciliation**: Exchange vs. local state validation
- **Force Closure**: Emergency position closure mechanisms
- **P&L Calculation**: Real-time profit/loss tracking

### 6. Order Management (`app/func_bot_agent.py`)
**Purpose**: Atomic paired trade execution and monitoring
- **State Machine**: FAILED → LIVE → CLOSE → ERROR states
- **Order Sequencing**: First-order validation before second-order placement
- **Failsafe Logic**: Automatic position closure on partial fills
- **Status Monitoring**: Real-time order status polling

### 7. Risk Management (`app/func_private.py`)
**Purpose**: Position limits and account protection
- **Collateral Checking**: Minimum account balance validation
- **Position Limits**: Maximum position size enforcement
- **Market Order Bounds**: ±70% price protection
- **Emergency Controls**: Abort all positions functionality

### 8. State Management
**Purpose**: Persistent state across bot restarts
- **Active Positions**: `bot_agents.json` tracks live paired trades
- **Cointegration Results**: `cointegrated_pairs.csv` stores statistical analysis
- **State Validation**: Exchange reconciliation on startup
- **Data Integrity**: Atomic file operations for consistency

## 🔄 Data Flow Architecture

### Market Data Flow
```
External APIs → dYdX Indexer → func_public.py → Price Matrices → func_cointegration.py
```

### Trading Signal Flow
```
Cointegration Analysis → Z-Score Calculation → Entry/Exit Signals → BotAgent → dYdX Orders
```

### State Flow
```
Order Execution → BotAgent State → bot_agents.json → Exit Manager → Position Closure
```

## 🛡️ Security Architecture

### API Security
- **Rate Limiting**: Intelligent API call spacing (0.2-0.5s delays)
- **Error Handling**: Graceful degradation on API failures
- **Timeout Management**: Configurable API timeouts
- **Retry Logic**: Exponential backoff on transient failures

### Trading Security
- **Market Order Protection**: Price bounds (±70%) prevent extreme fills
- **Partial Fill Handling**: Automatic position closure on incomplete orders
- **State Reconciliation**: Continuous validation against exchange state
- **Emergency Stops**: Manual and automated position closure

### Data Security
- **Configuration Encryption**: Sensitive data in environment variables
- **State File Protection**: Atomic writes prevent corruption
- **Log Sanitization**: No sensitive data in log files
- **Network Security**: HTTPS/WSS connections only

## ⚡ Performance Architecture

### Asynchronous Design
- **AsyncIO**: Full async/await pattern for non-blocking operations
- **Concurrent Processing**: Parallel market data fetching
- **Connection Pooling**: Reusable client connections
- **Memory Management**: Efficient DataFrame operations

### Optimization Strategies
- **Lazy Loading**: Heavy libraries loaded only when needed
- **Caching**: Market metadata and configuration caching
- **Batch Operations**: Bulk price data requests
- **Resource Cleanup**: Proper resource disposal

## 📊 Monitoring Architecture

### Logging System (`app/logging_setup.py`)
- **Structured Logging**: JSON-formatted log entries
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Multiple Handlers**: Console and optional Loki integration
- **Stream Labels**: Grafana-compatible log level labeling

### Health Monitoring
- **Connection Health**: Periodic dYdX API connectivity checks
- **Position Health**: Continuous state validation
- **Performance Metrics**: Execution time and success rate tracking
- **Alert System**: Telegram notifications for critical events

## 🔄 Scalability Considerations

### Horizontal Scaling
- **Stateless Design**: Configuration-driven behavior
- **Container Ready**: Docker-first deployment approach
- **Service Isolation**: Independent service components
- **Load Distribution**: Multiple bot instances with different pairs

### Vertical Scaling
- **Memory Efficiency**: Optimized data structures
- **CPU Optimization**: Vectorized calculations
- **I/O Optimization**: Connection pooling and batching
- **Storage Optimization**: Efficient state file management

## 🎯 Integration Points

### External Dependencies
- **dYdX v4 Client**: Official Python SDK
- **Statistical Libraries**: statsmodels, scipy, numpy, pandas
- **Networking**: aiohttp, requests
- **Monitoring**: Grafana Loki integration

### Internal Dependencies
- **Configuration**: YAML-based configuration system
- **State Management**: JSON-based persistence
- **Logging**: Centralized logging infrastructure
- **Messaging**: Telegram integration for alerts

This architecture supports a robust, scalable, and maintainable trading system capable of executing sophisticated statistical arbitrage strategies on the dYdX v4 decentralized exchange.