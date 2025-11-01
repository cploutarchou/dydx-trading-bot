# dYdX Trading Bot - Complete API Usage Guide

**Version:** 1.0.0  
**Last Updated:** November 2025  
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Getting Started](#getting-started)
4. [API Endpoints](#api-endpoints)
5. [Bot Lifecycle](#bot-lifecycle)
6. [Trading Parameters](#trading-parameters)
7. [Backtesting Guide](#backtesting-guide)
8. [Real-Time Data Streaming](#real-time-data-streaming)
9. [Examples & Code Samples](#examples--code-samples)
10. [Error Handling](#error-handling)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The dYdX Trading Bot provides a complete API for:

- **Bot Management**: Create, start, stop, and monitor multiple bot instances
- **Trading Execution**: Place trades, manage positions, exit trades
- **Backtesting**: Test strategies on historical data before live trading
- **Real-Time Monitoring**: Stream live position, market data, and alerts via WebSocket
- **Historical Analysis**: Retrieve job history, trade records, and performance stats

### Key Features

- **Multi-Instance Support**: Run multiple independent bots simultaneously
- **API-Driven Control**: Full bot lifecycle management via REST API
- **WebSocket Streaming**: Real-time position and market data updates
- **Database Persistence**: Store all transactions, trades, and metrics
- **Backtesting Engine**: Test strategies without risk using historical data
- **Comprehensive Logging**: Track all bot activities with detailed audit trails

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Server (port 8889)                │
│  (bot_api_server.py)                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Bot Manager  │  │ Backtesting  │  │ WebSocket    │      │
│  │ (REST API)   │  │ Engine       │  │ Server       │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                  │             │
└────────────────────────────────────────────────────────────┤
                        │                      │
        ┌───────────────┴──────────────────────┴──────────┐
        │                                                 │
    ┌───────────────────────────┐      ┌────────────────┐ │
    │  Database Layer           │      │  dYdX Client   │ │
    │  (SQLAlchemy ORM)         │      │  Connection    │ │
    │                           │      │                │ │
    │  - bot_instances          │      │  - Markets     │ │
    │  - live_positions         │      │  - Accounts    │ │
    │  - trades                 │      │  - Orders      │ │
    │  - jobs                   │      │                │ │
    │  - alerts                 │      └────────────────┘ │
    └───────────────────────────┘                         │
        (SQLite/PostgreSQL)                               │
                                                          │
        ┌────────────────────────────────────────────────┘
        │
    ┌───────────────┐
    │ Bot Instances │
    │ (Subprocess)  │
    └───────────────┘
```

### Data Flow

```
Client Request
    ↓
REST API Endpoint (FastAPI)
    ↓
Bot Manager / Data Service
    ↓
dYdX Client + Database
    ↓
Response + WebSocket Broadcast
```

---

## Getting Started

### 1. Prerequisites

```bash
# Python 3.10+
python --version

# Required packages (should be installed)
pip list | grep -E "fastapi|uvicorn|sqlalchemy|pydantic"

# dYdX testnet/mainnet account ready
```

### 2. Start the API Server

```bash
# Navigate to bot directory
cd /home/chris/workspace/dydx-trading-bot/bot

# Start API server (runs on port 8889)
python bot_api_server.py

# Or with background process
nohup python bot_api_server.py > api.log 2>&1 &

# Check if running
curl http://localhost:8889/health

# Expected response:
# {"success": true, "message": "API Server is healthy", ...}
```

### 3. Verify Setup

```bash
# Check system status
curl http://localhost:8889/api/v1/system/status

# List bot instances (should be empty initially)
curl http://localhost:8889/api/v1/bots
```

---

## API Endpoints

### Authentication

**Note:** Current version has no authentication. For production, add:

- API Key validation
- JWT tokens
- Rate limiting

### Response Format

All endpoints return consistent JSON response:

```json
{
  "success": true,
  "message": "Operation successful",
  "data": { /* response data */ },
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

---

## Bot Instance Management

### 1. Create Bot Instance

**Endpoint:** `POST /api/v1/bots`

**Purpose:** Create a new bot instance (doesn't start trading, just configures it)

**Request Payload:**

```json
{
  "instance_id": "btc-eth-bot-01",
  "instance_name": "BTC-ETH Arbitrage Bot 01",
  "credentials": {
    "address": "dydx1a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9",
    "mnemonic": "word1 word2 word3 ... word12"
  },
  "trading_params": {
    "is_testnet": true,
    "abort_all_positions": false,
    "find_cointegrated_pairs": true,
    "manage_exits": true,
    "place_trades": true,
    "resolution_timeframe": "1HOUR",
    "strategy": "cointegration",
    "stats_window": 21,
    "max_half_life": 24,
    "zscore_threshold": 1.5,
    "usd_per_trade": 25.0,
    "usd_min_collateral": 100.0,
    "close_at_zscore_cross": true
  }
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:8889/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "btc-eth-bot-01",
    "instance_name": "BTC-ETH Arbitrage Bot",
    "credentials": {
      "address": "dydx1...",
      "mnemonic": "word1 word2 ..."
    },
    "trading_params": {
      "is_testnet": true,
      "zscore_threshold": 1.5,
      "usd_per_trade": 25.0
    }
  }'
```

**Python Example:**

```python
import requests

url = "http://localhost:8889/api/v1/bots"

payload = {
    "instance_id": "btc-eth-bot-01",
    "instance_name": "BTC-ETH Arbitrage Bot",
    "credentials": {
        "address": "dydx1...",
        "mnemonic": "word1 word2 ..."
    },
    "trading_params": {
        "is_testnet": True,
        "zscore_threshold": 1.5,
        "usd_per_trade": 25.0,
        "find_cointegrated_pairs": True,
        "manage_exits": True,
        "place_trades": True,
    }
}

response = requests.post(url, json=payload)
print(response.json())
```

**Response:**

```json
{
  "success": true,
  "message": "Bot instance 'btc-eth-bot-01' created successfully",
  "data": {
    "instance_id": "btc-eth-bot-01",
    "instance_name": "BTC-ETH Arbitrage Bot",
    "status": "stopped",
    "network": "testnet",
    "created_at": "2025-11-02T10:30:45.123456"
  },
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

---

### 2. List All Bot Instances

**Endpoint:** `GET /api/v1/bots`

**Purpose:** Retrieve all bot instances with summary information

**cURL Example:**

```bash
curl http://localhost:8889/api/v1/bots
```

**Python Example:**

```python
import requests

response = requests.get("http://localhost:8889/api/v1/bots")
data = response.json()

print(f"Total instances: {data['data']['total_instances']}")
print(f"Running: {data['data']['running_instances']}")
print(f"Stopped: {data['data']['stopped_instances']}")

for instance in data['data']['instances']:
    print(f"  - {instance['instance_name']}: {instance['status']}")
```

**Response:**

```json
{
  "success": true,
  "message": "Retrieved 2 bot instances",
  "data": {
    "instances": [
      {
        "instance_id": "btc-eth-bot-01",
        "instance_name": "BTC-ETH Arbitrage Bot",
        "status": "running",
        "network": "testnet",
        "created_at": "2025-11-02T10:00:00.000000",
        "started_at": "2025-11-02T10:05:00.000000",
        "last_activity": "2025-11-02T10:30:45.123456",
        "active_positions": 3,
        "total_trades": 12,
        "total_pnl_usd": 145.50,
        "daily_pnl_usd": 45.30
      },
      {
        "instance_id": "sol-luna-bot-01",
        "instance_name": "SOL-LUNA Arbitrage Bot",
        "status": "stopped",
        "network": "testnet",
        "created_at": "2025-11-02T11:00:00.000000"
      }
    ],
    "total_instances": 2,
    "running_instances": 1,
    "stopped_instances": 1,
    "error_instances": 0
  },
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

---

### 3. Get Bot Instance Details

**Endpoint:** `GET /api/v1/bots/{instance_id}`

**Purpose:** Get detailed status of a specific bot instance

**URL Parameters:**

- `instance_id` (string): The bot instance ID

**cURL Example:**

```bash
curl http://localhost:8889/api/v1/bots/btc-eth-bot-01
```

**Response:**

```json
{
  "success": true,
  "message": "Retrieved status for instance 'btc-eth-bot-01'",
  "data": {
    "instance_id": "btc-eth-bot-01",
    "instance_name": "BTC-ETH Arbitrage Bot",
    "status": "running",
    "network": "testnet",
    "created_at": "2025-11-02T10:00:00.000000",
    "started_at": "2025-11-02T10:05:00.000000",
    "stopped_at": null,
    "last_activity": "2025-11-02T10:30:45.123456",
    "total_trades": 12,
    "active_positions": 3,
    "total_pnl_usd": 145.50,
    "daily_pnl_usd": 45.30,
    "strategy": "cointegration",
    "usd_per_trade": 25.0,
    "zscore_threshold": 1.5,
    "pid": 12345,
    "cpu_usage": 2.5,
    "memory_usage_mb": 185.3
  },
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

---

## Bot Execution

### 1. Start Bot Instance

**Endpoint:** `POST /api/v1/bots/{instance_id}/start`

**Purpose:** Start trading on a bot instance

**What Happens:**

1. Launches bot as separate subprocess
2. Bot loads configuration and connects to dYdX
3. Performs initial analysis (cointegration search)
4. Begins placing trades based on strategy
5. Monitors and manages exits

**cURL Example:**

```bash
curl -X POST http://localhost:8889/api/v1/bots/btc-eth-bot-01/start
```

**Python Example:**

```python
import requests

instance_id = "btc-eth-bot-01"
response = requests.post(
    f"http://localhost:8889/api/v1/bots/{instance_id}/start"
)

result = response.json()
if result['success']:
    print(f"Bot started: {result['data']['status']}")
    print(f"Process ID: {result['data']['pid']}")
else:
    print(f"Error: {result['message']}")
```

**Response:**

```json
{
  "success": true,
  "message": "Bot instance 'btc-eth-bot-01' started successfully",
  "data": {
    "instance_id": "btc-eth-bot-01",
    "status": "running",
    "pid": 12345,
    "started_at": "2025-11-02T10:35:00.000000"
  },
  "timestamp": "2025-11-02T10:35:00.000000"
}
```

**Status Check (poll for running status):**

```python
import requests
import time

instance_id = "btc-eth-bot-01"

# Check if bot is actually running
for attempt in range(30):  # 30 second timeout
    response = requests.get(f"http://localhost:8889/api/v1/bots/{instance_id}")
    status = response.json()['data']['status']
    
    if status == 'running':
        print("Bot is running!")
        break
    elif status == 'error':
        print("Bot failed to start")
        break
    
    time.sleep(1)
```

---

### 2. Stop Bot Instance

**Endpoint:** `POST /api/v1/bots/{instance_id}/stop`

**Purpose:** Stop trading and shut down a bot instance

**What Happens:**

1. Signals bot to stop accepting new trades
2. Allows existing trades to complete/exit
3. Closes all open positions (optional based on config)
4. Saves all statistics and job records
5. Terminates subprocess

**cURL Example:**

```bash
curl -X POST http://localhost:8889/api/v1/bots/btc-eth-bot-01/stop
```

**Python Example:**

```python
import requests

instance_id = "btc-eth-bot-01"
response = requests.post(
    f"http://localhost:8889/api/v1/bots/{instance_id}/stop"
)

result = response.json()
print(f"Stop status: {result['data']['status']}")
print(f"Stopped at: {result['data']['stopped_at']}")
```

**Response:**

```json
{
  "success": true,
  "message": "Bot instance 'btc-eth-bot-01' stopped successfully",
  "data": {
    "instance_id": "btc-eth-bot-01",
    "status": "stopped",
    "stopped_at": "2025-11-02T11:00:00.000000"
  },
  "timestamp": "2025-11-02T11:00:00.000000"
}
```

---

### 3. Restart Bot Instance

**Endpoint:** `POST /api/v1/bots/{instance_id}/restart`

**Purpose:** Stop and immediately restart a bot instance

**Equivalent to:**

```python
requests.post(f"/api/v1/bots/{instance_id}/stop")
requests.post(f"/api/v1/bots/{instance_id}/start")
```

**cURL Example:**

```bash
curl -X POST http://localhost:8889/api/v1/bots/btc-eth-bot-01/restart
```

---

### 4. Delete Bot Instance

**Endpoint:** `DELETE /api/v1/bots/{instance_id}`

**Purpose:** Remove bot instance configuration and all associated data

**⚠️ Warning:** This is destructive and cannot be undone

**cURL Example:**

```bash
curl -X DELETE http://localhost:8889/api/v1/bots/btc-eth-bot-01
```

---

## Trading Data Endpoints

### 1. Get Bot Trading History

**Endpoint:** `GET /api/v1/bots/{instance_id}/history`

**Purpose:** Retrieve all trading events and job records for a bot

**Query Parameters:**

- `limit` (int, optional): Max records to return (default: 100)
- `offset` (int, optional): Pagination offset (default: 0)
- `status` (string, optional): Filter by status (e.g., "LIVE", "CLOSED", "ERROR")

**cURL Example:**

```bash
# Get last 50 trades
curl "http://localhost:8889/api/v1/bots/btc-eth-bot-01/history?limit=50"

# Get only closed positions
curl "http://localhost:8889/api/v1/bots/btc-eth-bot-01/history?status=CLOSED&limit=20"
```

**Response:**

```json
{
  "success": true,
  "message": "Retrieved 25 historical records",
  "data": {
    "records": [
      {
        "id": 1,
        "bot_instance_id": 1,
        "pair": "BTC-USD/ETH-USD",
        "status": "CLOSED",
        "entry_time": "2025-11-02T09:00:00",
        "exit_time": "2025-11-02T10:00:00",
        "entry_zscore": 1.8,
        "exit_zscore": 0.2,
        "position_duration_hours": 1.0,
        "pnl_usd": 45.50,
        "win": true
      }
    ],
    "total": 25,
    "limit": 50,
    "offset": 0
  },
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

---

### 2. Get Bot Jobs

**Endpoint:** `GET /api/v1/bots/{instance_id}/jobs`

**Purpose:** Get job execution records with status and timing

**Query Parameters:**

- `limit` (int, optional): Max jobs to return (default: 20)
- `status` (string, optional): Filter by status (PENDING, RUNNING, COMPLETED, FAILED)
- `days` (int, optional): Filter to last N days (default: all)

**cURL Example:**

```bash
# Get recent job status
curl "http://localhost:8889/api/v1/bots/btc-eth-bot-01/jobs?limit=10"

# Get failed jobs from last 7 days
curl "http://localhost:8889/api/v1/bots/btc-eth-bot-01/jobs?status=FAILED&days=7"
```

**Response:**

```json
{
  "success": true,
  "message": "Retrieved 10 jobs",
  "data": {
    "jobs": [
      {
        "id": 1,
        "bot_instance_id": 1,
        "job_name": "cointegration_analysis",
        "job_type": "analysis",
        "status": "completed",
        "start_time": "2025-11-02T10:00:00",
        "end_time": "2025-11-02T10:05:30",
        "duration_seconds": 330,
        "pid": 12345,
        "exit_code": 0,
        "output_size_bytes": 1024
      }
    ],
    "total": 10
  },
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

---

### 3. Get Bot Trades

**Endpoint:** `GET /api/v1/bots/{instance_id}/trades`

**Purpose:** Detailed trade-by-trade P&L and execution data

**Query Parameters:**

- `limit` (int): Max trades (default: 50)
- `win_only` (bool): Only winning trades
- `from_date` (ISO date): Start date filter
- `to_date` (ISO date): End date filter

**cURL Example:**

```bash
# Last 20 trades
curl "http://localhost:8889/api/v1/bots/btc-eth-bot-01/trades?limit=20"

# Winning trades only
curl "http://localhost:8889/api/v1/bots/btc-eth-bot-01/trades?win_only=true"

# Trades from specific date range
curl "http://localhost:8889/api/v1/bots/btc-eth-bot-01/trades?from_date=2025-11-01&to_date=2025-11-02"
```

**Response:**

```json
{
  "success": true,
  "message": "Retrieved 15 trades",
  "data": {
    "trades": [
      {
        "id": 1,
        "pair": "BTC-USD/ETH-USD",
        "entry_time": "2025-11-02T09:00:00",
        "exit_time": "2025-11-02T10:00:00",
        "entry_price_m1": 43250.50,
        "entry_price_m2": 2150.75,
        "exit_price_m1": 43260.00,
        "exit_price_m2": 2148.50,
        "size_m1": 0.5,
        "size_m2": 10.0,
        "pnl_usd": 45.50,
        "pnl_percent": 0.85,
        "duration_hours": 1.0,
        "winning_trade": true,
        "strategy": "cointegration",
        "zscore_entry": 1.8,
        "zscore_exit": 0.2
      }
    ],
    "total": 15,
    "stats": {
      "win_rate": 0.87,
      "avg_win": 52.30,
      "avg_loss": -35.20,
      "total_pnl": 625.50
    }
  },
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

---

### 4. Get Bot Statistics

**Endpoint:** `GET /api/v1/bots/{instance_id}/stats`

**Purpose:** Aggregated performance statistics

**cURL Example:**

```bash
curl "http://localhost:8889/api/v1/bots/btc-eth-bot-01/stats"
```

**Response:**

```json
{
  "success": true,
  "message": "Retrieved statistics for 'btc-eth-bot-01'",
  "data": {
    "instance_id": "btc-eth-bot-01",
    "period_start": "2025-11-01T00:00:00",
    "period_end": "2025-11-02T10:30:45",
    "total_trades": 25,
    "winning_trades": 22,
    "losing_trades": 3,
    "win_rate": 0.88,
    "total_pnl_usd": 1245.50,
    "avg_trade_pnl_usd": 49.82,
    "max_win_usd": 250.00,
    "max_loss_usd": -85.50,
    "current_positions": 2,
    "max_positions": 5,
    "avg_position_duration_hours": 2.5,
    "sharpe_ratio": 1.45,
    "max_drawdown_pct": -8.5,
    "profit_factor": 2.15
  },
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

---

## Real-Time Data Streaming

### WebSocket Connections

Real-time data is streamed via WebSocket. Multiple clients can subscribe to the same bot's updates.

#### 1. Position Updates Stream

**WebSocket URL:** `ws://localhost:8889/api/v1/bots/{bot_instance_id}/positions/live`

**Purpose:** Stream live position prices, P&L, and updates

**Message Types:**

**Initial State** (sent on connection):

```json
{
  "type": "initial_state",
  "timestamp": "2025-11-02T10:30:45.123456",
  "positions": [
    {
      "id": 1,
      "bot_instance_id": 1,
      "position_id": "POS-001",
      "market_1": "BTC-USD",
      "market_2": "ETH-USD",
      "status": "OPEN",
      "entry_price_m1": 43250.50,
      "current_price_m1": 43260.00,
      "entry_price_m2": 2150.75,
      "current_price_m2": 2148.50,
      "size_m1": 0.5,
      "size_m2": 10.0,
      "unrealized_pnl_usd": 45.50,
      "z_score": 0.8,
      "hedge_ratio": 20.0,
      "opened_at": "2025-11-02T09:00:00",
      "updated_at": "2025-11-02T10:30:45"
    }
  ]
}
```

**Position Opened Event**:

```json
{
  "type": "position_opened",
  "timestamp": "2025-11-02T10:35:00",
  "position": {
    "id": 2,
    "position_id": "POS-002",
    "market_1": "SOL-USD",
    "market_2": "LUNA-USD",
    "status": "OPEN",
    "entry_price_m1": 105.50,
    "current_price_m1": 105.50,
    "size_m1": 100.0,
    "size_m2": 5000.0,
    "unrealized_pnl_usd": 0.0
  }
}
```

**Position Updated Event**:

```json
{
  "type": "position_updated",
  "timestamp": "2025-11-02T10:40:15",
  "position_id": "POS-001",
  "updates": {
    "current_price_m1": 43275.00,
    "current_price_m2": 2145.25,
    "unrealized_pnl_usd": 125.75,
    "z_score": 0.2
  }
}
```

**Position Closed Event**:

```json
{
  "type": "position_closed",
  "timestamp": "2025-11-02T11:00:00",
  "position_id": "POS-001",
  "exit_info": {
    "exit_price_m1": 43280.00,
    "exit_price_m2": 2144.00,
    "realized_pnl_usd": 145.50,
    "duration_hours": 2.0
  }
}
```

**Python WebSocket Client Example:**

```python
import asyncio
import websockets
import json

async def stream_positions(bot_id):
    uri = f"ws://localhost:8889/api/v1/bots/{bot_id}/positions/live"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to position stream")
        
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                if data['type'] == 'initial_state':
                    print(f"Initial positions: {len(data['positions'])}")
                    for pos in data['positions']:
                        print(f"  {pos['position_id']}: {pos['market_1']}/{pos['market_2']} "
                              f"P&L: ${pos['unrealized_pnl_usd']:.2f}")
                
                elif data['type'] == 'position_opened':
                    print(f"New position opened: {data['position']['position_id']}")
                
                elif data['type'] == 'position_updated':
                    print(f"Position {data['position_id']} updated")
                    print(f"  New P&L: ${data['updates']['unrealized_pnl_usd']:.2f}")
                
                elif data['type'] == 'position_closed':
                    print(f"Position {data['position_id']} closed")
                    print(f"  Realized P&L: ${data['exit_info']['realized_pnl_usd']:.2f}")
            
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break

# Run the stream
asyncio.run(stream_positions("btc-eth-bot-01"))
```

---

#### 2. Market Data Stream

**WebSocket URL:** `ws://localhost:8889/api/v1/bots/{bot_instance_id}/market/live`

**Purpose:** Stream market data updates (OHLCV, technicals, funding rates)

**Message Format:**

```json
{
  "type": "market_data",
  "timestamp": "2025-11-02T10:40:00",
  "symbol": "BTC-USD",
  "data": {
    "open": 43240.50,
    "high": 43280.00,
    "low": 43200.00,
    "close": 43260.00,
    "volume": 1234.56,
    "rsi": 65.4,
    "macd": 0.85,
    "macd_signal": 0.75,
    "macd_histogram": 0.10,
    "sma_20": 43150.00,
    "sma_50": 43100.00,
    "sma_200": 42800.00,
    "funding_rate": 0.00015,
    "timestamp": "2025-11-02T10:40:00"
  }
}
```

---

#### 3. Alerts Stream

**WebSocket URL:** `ws://localhost:8889/api/v1/bots/{bot_instance_id}/alerts/live`

**Purpose:** Real-time trading alerts and warnings

**Alert Types:**

```json
{
  "type": "alert",
  "timestamp": "2025-11-02T10:50:00",
  "alert": {
    "id": 1,
    "alert_type": "drawdown_warning",
    "severity": "warning",
    "message": "Portfolio drawdown exceeds -5% threshold",
    "data": {
      "current_drawdown_pct": -5.2,
      "threshold": -5.0
    }
  }
}
```

---

## Backtesting Guide

### Overview

The backtesting engine simulates trading on historical data without placing real orders. Use it to:

- Test strategy parameters
- Evaluate performance metrics
- Optimize trading rules
- Reduce risk before live trading

### Backtesting via API

**Endpoint:** `POST /api/v1/bots/quick-deploy`

**Purpose:** Deploy and run backtesting in one call

**Request Payload:**

```json
{
  "instance_id": "backtest-btc-eth-01",
  "instance_name": "BTC-ETH Backtest Run 1",
  "strategy_params": {
    "zscore_threshold": 1.5,
    "usd_per_trade": 50.0,
    "stats_window": 21,
    "max_half_life": 24,
    "resolution_timeframe": "1HOUR",
    "close_at_zscore_cross": true
  },
  "backtest_config": {
    "start_date": "2025-09-01",
    "end_date": "2025-10-31",
    "historical_days": 60
  }
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:8889/api/v1/bots/quick-deploy \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "backtest-001",
    "instance_name": "Backtest Run 1",
    "strategy_params": {
      "zscore_threshold": 1.5,
      "usd_per_trade": 50.0
    },
    "backtest_config": {
      "start_date": "2025-09-01",
      "end_date": "2025-10-31"
    }
  }'
```

**Python Example:**

```python
import requests

url = "http://localhost:8889/api/v1/bots/quick-deploy"

payload = {
    "instance_id": "backtest-001",
    "instance_name": "Backtest Run 1",
    "strategy_params": {
        "zscore_threshold": 1.5,
        "usd_per_trade": 50.0,
        "stats_window": 21,
    },
    "backtest_config": {
        "start_date": "2025-09-01",
        "end_date": "2025-10-31",
        "historical_days": 60
    }
}

response = requests.post(url, json=payload)
result = response.json()

if result['success']:
    print("Backtest completed!")
    stats = result['data']['backtest_stats']
    print(f"Total trades: {stats['total_trades']}")
    print(f"Win rate: {stats['win_rate']:.2%}")
    print(f"Total P&L: ${stats['total_pnl_usd']:.2f}")
else:
    print(f"Error: {result['message']}")
```

**Response:**

```json
{
  "success": true,
  "message": "Backtest completed successfully",
  "data": {
    "instance_id": "backtest-001",
    "status": "completed",
    "backtest_stats": {
      "start_date": "2025-09-01",
      "end_date": "2025-10-31",
      "total_trades": 45,
      "winning_trades": 39,
      "losing_trades": 6,
      "win_rate": 0.867,
      "total_pnl_usd": 2145.50,
      "avg_trade_pnl_usd": 47.68,
      "max_win_usd": 250.00,
      "max_loss_usd": -85.50,
      "max_drawdown_pct": -8.5,
      "sharpe_ratio": 1.65,
      "profit_factor": 2.45
    }
  },
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

### Backtesting Configuration

**Strategy Parameters (tunable):**

```python
strategy_params = {
    # Entry Signal
    "zscore_threshold": 1.5,      # Z-score for entry (0.5-5.0)
    
    # Exit Signal
    "close_at_zscore_cross": True, # Close on mean reversion
    
    # Analysis Window
    "stats_window": 21,            # Days for statistics (5-100)
    "max_half_life": 24,           # Max mean reversion period (hours)
    
    # Position Sizing
    "usd_per_trade": 50.0,         # Size per trade (USD)
    
    # Resolution
    "resolution_timeframe": "1HOUR" # OHLCV timeframe
}
```

**Backtest Configuration:**

```python
backtest_config = {
    "start_date": "2025-09-01",      # Test period start
    "end_date": "2025-10-31",        # Test period end
    "historical_days": 60            # Lookback for initial analysis
}
```

### Interpreting Backtest Results

| Metric | Interpretation | Good Range |
|--------|-----------------|------------|
| Win Rate | % of profitable trades | > 60% |
| Total P&L | Absolute profit/loss | Positive |
| Sharpe Ratio | Risk-adjusted returns | > 1.0 |
| Max Drawdown | Largest peak-to-valley loss | < -15% |
| Profit Factor | Ratio of wins to losses | > 1.5 |

---

## Examples & Code Samples

### Complete Trading Bot Setup

```python
import requests
import time
import asyncio

class BotController:
    def __init__(self, api_url="http://localhost:8889"):
        self.api_url = api_url
    
    def create_bot(self, instance_id, credentials, trading_params):
        """Create and configure a new bot"""
        payload = {
            "instance_id": instance_id,
            "instance_name": f"Bot {instance_id}",
            "credentials": credentials,
            "trading_params": trading_params
        }
        
        response = requests.post(
            f"{self.api_url}/api/v1/bots",
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()['data']
        else:
            raise Exception(f"Failed to create bot: {response.text}")
    
    def start_bot(self, instance_id):
        """Start bot trading"""
        response = requests.post(
            f"{self.api_url}/api/v1/bots/{instance_id}/start"
        )
        
        if response.status_code == 200:
            print(f"Bot {instance_id} started")
            return response.json()['data']
        else:
            raise Exception(f"Failed to start bot: {response.text}")
    
    def get_stats(self, instance_id):
        """Get bot statistics"""
        response = requests.get(
            f"{self.api_url}/api/v1/bots/{instance_id}/stats"
        )
        
        if response.status_code == 200:
            return response.json()['data']
        else:
            raise Exception(f"Failed to get stats: {response.text}")
    
    def stop_bot(self, instance_id):
        """Stop bot trading"""
        response = requests.post(
            f"{self.api_url}/api/v1/bots/{instance_id}/stop"
        )
        
        if response.status_code == 200:
            print(f"Bot {instance_id} stopped")
            return response.json()['data']
        else:
            raise Exception(f"Failed to stop bot: {response.text}")


# Usage Example
def main():
    controller = BotController()
    
    # 1. Create bot
    credentials = {
        "address": "dydx1...",
        "mnemonic": "word1 word2 ..."
    }
    
    trading_params = {
        "is_testnet": True,
        "zscore_threshold": 1.5,
        "usd_per_trade": 25.0,
        "find_cointegrated_pairs": True,
        "manage_exits": True,
        "place_trades": True
    }
    
    bot = controller.create_bot("btc-eth-bot-01", credentials, trading_params)
    print(f"Bot created: {bot['instance_id']}")
    
    # 2. Start bot
    controller.start_bot("btc-eth-bot-01")
    time.sleep(5)  # Wait for startup
    
    # 3. Monitor stats
    for i in range(6):
        stats = controller.get_stats("btc-eth-bot-01")
        print(f"\nStats (cycle {i+1}):")
        print(f"  Trades: {stats['total_trades']}")
        print(f"  P&L: ${stats['total_pnl_usd']:.2f}")
        print(f"  Win Rate: {stats['win_rate']:.2%}")
        time.sleep(10)
    
    # 4. Stop bot
    controller.stop_bot("btc-eth-bot-01")


if __name__ == "__main__":
    main()
```

### Real-Time Position Monitoring

```python
import asyncio
import websockets
import json

async def monitor_positions(bot_id):
    """Real-time position monitoring via WebSocket"""
    
    uri = f"ws://localhost:8889/api/v1/bots/{bot_id}/positions/live"
    
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {bot_id} position stream")
        
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            
            if data['type'] == 'initial_state':
                print(f"\n=== Initial Positions ({len(data['positions'])}) ===")
                for pos in data['positions']:
                    print(f"{pos['position_id']:20} {pos['market_1']:12} "
                          f"P&L: ${pos['unrealized_pnl_usd']:>10.2f} "
                          f"Z: {pos['z_score']:>5.2f}")
            
            elif data['type'] == 'position_opened':
                pos = data['position']
                print(f"\n✓ OPENED: {pos['position_id']} ({pos['market_1']}/{pos['market_2']})")
            
            elif data['type'] == 'position_updated':
                print(f"  • {data['position_id']}: "
                      f"P&L ${data['updates']['unrealized_pnl_usd']:.2f}")
            
            elif data['type'] == 'position_closed':
                print(f"\n✗ CLOSED: {data['position_id']} "
                      f"(P&L: ${data['exit_info']['realized_pnl_usd']:.2f})")


# Run monitor
asyncio.run(monitor_positions("btc-eth-bot-01"))
```

### Backtesting Multiple Strategies

```python
import requests
import pandas as pd

def run_backtest(strategy_params, name):
    """Run single backtest"""
    
    url = "http://localhost:8889/api/v1/bots/quick-deploy"
    
    payload = {
        "instance_id": f"backtest-{name}",
        "instance_name": f"Backtest {name}",
        "strategy_params": strategy_params,
        "backtest_config": {
            "start_date": "2025-09-01",
            "end_date": "2025-10-31",
            "historical_days": 60
        }
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        return response.json()['data']['backtest_stats']
    else:
        print(f"Backtest failed: {response.text}")
        return None


def compare_strategies():
    """Compare multiple strategy configurations"""
    
    # Different strategy configurations to test
    strategies = [
        {
            "name": "Conservative",
            "params": {
                "zscore_threshold": 2.0,
                "usd_per_trade": 25.0
            }
        },
        {
            "name": "Aggressive",
            "params": {
                "zscore_threshold": 1.0,
                "usd_per_trade": 100.0
            }
        },
        {
            "name": "Balanced",
            "params": {
                "zscore_threshold": 1.5,
                "usd_per_trade": 50.0
            }
        }
    ]
    
    results = []
    
    for strategy in strategies:
        print(f"\nTesting {strategy['name']}...")
        stats = run_backtest(strategy['params'], strategy['name'])
        
        if stats:
            results.append({
                "Strategy": strategy['name'],
                "Total Trades": stats['total_trades'],
                "Win Rate": f"{stats['win_rate']:.2%}",
                "Total P&L": f"${stats['total_pnl_usd']:.2f}",
                "Sharpe Ratio": f"{stats['sharpe_ratio']:.2f}",
                "Max Drawdown": f"{stats['max_drawdown_pct']:.2f}%"
            })
    
    # Display comparison
    df = pd.DataFrame(results)
    print("\n\n=== BACKTEST COMPARISON ===")
    print(df.to_string(index=False))
    
    return df


if __name__ == "__main__":
    compare_strategies()
```

---

## Error Handling

### Common Error Codes

| Code | Error | Cause | Solution |
|------|-------|-------|----------|
| 400 | Bad Request | Invalid payload | Check JSON syntax and required fields |
| 404 | Not Found | Bot instance doesn't exist | Verify instance_id |
| 409 | Conflict | Bot already running | Stop bot before starting |
| 500 | Server Error | Internal error | Check server logs |

### Error Response Format

```json
{
  "success": false,
  "message": "Bot instance 'invalid-bot' not found",
  "data": null,
  "error_code": "NOT_FOUND",
  "timestamp": "2025-11-02T10:30:45.123456"
}
```

### Handling Errors in Python

```python
import requests

def safe_api_call(url, method='get', **kwargs):
    """Helper function for safe API calls"""
    
    try:
        if method.lower() == 'get':
            response = requests.get(url, timeout=30, **kwargs)
        elif method.lower() == 'post':
            response = requests.post(url, timeout=30, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if response.status_code == 200:
            return response.json()
        
        else:
            error_data = response.json()
            raise Exception(
                f"API Error {response.status_code}: "
                f"{error_data.get('message', 'Unknown error')}"
            )
    
    except requests.exceptions.Timeout:
        raise Exception("API request timed out")
    except requests.exceptions.ConnectionError:
        raise Exception("Unable to connect to API server")
    except Exception as e:
        raise Exception(f"API call failed: {str(e)}")


# Usage
try:
    result = safe_api_call("http://localhost:8889/api/v1/bots/my-bot-01")
    print(result)
except Exception as e:
    print(f"Error: {e}")
```

---

## Troubleshooting

### Issue: API Server Won't Start

**Problem:** `Address already in use` error on port 8889

**Solution:**

```bash
# Check what's using port 8889
lsof -i :8889

# Kill the process
kill -9 <PID>

# Or use different port (edit bot_api_server.py)
```

### Issue: Bot Won't Start Trading

**Problem:** Bot status stays "starting" or becomes "error"

**Solution:**

1. Check bot logs:

   ```bash
   # If running in foreground
   # Look for error messages
   
   # If running as subprocess
   tail -f bot.log
   ```

2. Verify credentials:

   ```bash
   # Check if wallet address and mnemonic are correct
   # Ensure wallet has sufficient collateral (usd_min_collateral)
   ```

3. Check dYdX connection:

   ```bash
   # Verify network (testnet vs mainnet)
   # Ensure internet connection is stable
   ```

### Issue: WebSocket Connection Failed

**Problem:** `Unable to connect to WebSocket`

**Solution:**

```python
import asyncio
import websockets

async def test_ws():
    try:
        async with websockets.connect(
            "ws://localhost:8889/api/v1/bots/my-bot/positions/live",
            ping_interval=20
        ) as ws:
            print("Connected!")
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(test_ws())
```

### Issue: Backtest Takes Too Long

**Problem:** Backtest runs for hours

**Solution:**

1. Reduce date range
2. Reduce stats_window
3. Increase usd_per_trade (fewer trades to process)

### Getting Help

When reporting issues, include:

1. API endpoint being called
2. Request payload (without credentials)
3. Response error message
4. Logs from api.log and bot.log
5. System info (OS, Python version, dYdX network)

---

## API Reference Summary

### Bot Management

- `POST /api/v1/bots` - Create bot instance
- `GET /api/v1/bots` - List all bots
- `GET /api/v1/bots/{instance_id}` - Get bot status
- `DELETE /api/v1/bots/{instance_id}` - Delete bot

### Bot Execution

- `POST /api/v1/bots/{instance_id}/start` - Start trading
- `POST /api/v1/bots/{instance_id}/stop` - Stop trading
- `POST /api/v1/bots/{instance_id}/restart` - Restart bot

### Trading Data

- `GET /api/v1/bots/{instance_id}/history` - Trade history
- `GET /api/v1/bots/{instance_id}/jobs` - Job records
- `GET /api/v1/bots/{instance_id}/trades` - Trade details
- `GET /api/v1/bots/{instance_id}/stats` - Performance stats

### Real-Time Data

- `WS /api/v1/bots/{instance_id}/positions/live` - Position stream
- `WS /api/v1/bots/{instance_id}/market/live` - Market data stream
- `WS /api/v1/bots/{instance_id}/alerts/live` - Alert stream

### Backtesting

- `POST /api/v1/bots/quick-deploy` - Run backtest

### System

- `GET /health` - Health check
- `GET /api/v1/system/status` - System status

---

## Additional Resources

- **API Documentation (Interactive):** <http://localhost:8889/docs>
- **OpenAPI Schema:** <http://localhost:8889/openapi.json>
- **Configuration Guide:** See `config.py`
- **Trading Strategy Details:** See `func_entry_pairs.py` and `func_exit_pairs.py`

---

**Last Updated:** November 2, 2025  
**Author:** dYdX Trading Bot Team  
**Questions?** Check the Troubleshooting section or review the code comments
