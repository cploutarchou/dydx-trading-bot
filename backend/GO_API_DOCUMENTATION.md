# dYdX Trading Bot - Backend Go API Documentation

## Overview

The Go backend now provides a complete REST API for managing bot instances, backtest operations, and real-time trading data. All endpoints communicate with the Python bot engine running on localhost:8000 and persist data to the PostgreSQL/SQLite database.

## Architecture

```
Frontend (React) 
    ↓
Backend Go API (Port 8888)
    ├── Bot Instance Management (/api/v1/bots/*)
    ├── Backtest Management (/api/v1/backtests/*)
    └── Bot API Communication (HTTP Client to localhost:8000)
         ↓
Python Bot API (Port 8000)
    ├── FastAPI Server
    └── Direct Trading with dYdX v4
```

## Authentication

All endpoints (except `/health` and `/auth/*`) require JWT authentication via the `Authorization` header:

```bash
Authorization: Bearer <JWT_TOKEN>
```

### Get JWT Token

```bash
curl -X POST http://localhost:8888/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Response:

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "user": { "id": 1, "username": "admin", ... }
  }
}
```

## API Endpoints

### Bot Instance Management

#### 1. List Bot Instances

```
GET /api/v1/bots?skip=0&limit=100
Authorization: Bearer <TOKEN>
```

**Query Parameters:**

- `skip`: Offset for pagination (default: 0)
- `limit`: Max results per page (default: 100, max: 500)

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "instance_id": "btc-eth-bot-01",
      "instance_name": "BTC-ETH Arbitrage",
      "status": "running",
      "network": "testnet",
      "strategy": "default",
      "total_trades": 15,
      "total_pnl": 125.50,
      "current_balance": 1125.50,
      "starting_balance": 1000.00,
      "created_at": "2025-11-03T10:00:00Z",
      "updated_at": "2025-11-03T14:30:00Z"
    }
  ]
}
```

#### 2. Create Bot Instance

```
POST /api/v1/bots
Authorization: Bearer <TOKEN>
Content-Type: application/json
```

**Request Body:**

```json
{
  "instance_id": "btc-eth-bot-01",
  "instance_name": "BTC-ETH Arbitrage Bot",
  "network": "testnet",
  "strategy": "default",
  "config": {
    "address": "dydx1...",
    "mnemonic": "seed phrase..."
  },
  "trading_params": {
    "zscore_threshold": 1.5,
    "usd_per_trade": 50.0,
    "close_at_zscore_cross": true
  }
}
```

**Response:** (201 Created)

```json
{
  "success": true,
  "data": {
    "id": 1,
    "instance_id": "btc-eth-bot-01",
    ...
  }
}
```

#### 3. Get Bot Instance Details

```
GET /api/v1/bots/:instance_id
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "id": 1,
    "instance_id": "btc-eth-bot-01",
    "status": "running",
    ...
  }
}
```

#### 4. Start Bot Instance

```
POST /api/v1/bots/:instance_id/start
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "status": "started"
  }
}
```

#### 5. Stop Bot Instance

```
POST /api/v1/bots/:instance_id/stop
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "status": "stopped"
  }
}
```

#### 6. Restart Bot Instance

```
POST /api/v1/bots/:instance_id/restart
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "status": "restarted"
  }
}
```

#### 7. Delete Bot Instance

```
DELETE /api/v1/bots/:instance_id
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "status": "deleted"
  }
}
```

#### 8. Get Bot Instance Statistics

```
GET /api/v1/bots/:instance_id/stats
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "total_trades": 15,
    "winning_trades": 10,
    "losing_trades": 5,
    "win_rate": 0.67,
    "avg_win": 18.75,
    "avg_loss": -8.50,
    "total_pnl": 125.50,
    "sharpe_ratio": 1.45
  }
}
```

#### 9. Get Bot Instance Trades

```
GET /api/v1/bots/:instance_id/trades?limit=100&offset=0&winning_only=false
Authorization: Bearer <TOKEN>
```

**Query Parameters:**

- `limit`: Max trades to return (default: 100)
- `offset`: Offset for pagination (default: 0)
- `winning_only`: Only return winning trades (default: false)

**Response:**

```json
{
  "success": true,
  "data": {
    "trades": [
      {
        "id": 1,
        "trade_id": "trade_001",
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "entry_timestamp": "2025-11-03T10:15:00Z",
        "entry_price_1": 42000.50,
        "entry_price_2": 2250.75,
        "side_1": "BUY",
        "side_2": "SELL",
        "size_1": 0.05,
        "size_2": 2.00,
        "hedge_ratio": 0.05,
        "exit_timestamp": "2025-11-03T11:30:00Z",
        "exit_price_1": 42100.00,
        "exit_price_2": 2240.00,
        "pnl": 125.50,
        "pnl_pct": 2.15,
        "duration_hours": 1.25
      }
    ]
  }
}
```

#### 10. Get Bot Instance Positions

```
GET /api/v1/bots/:instance_id/positions?status=open&limit=50&offset=0
Authorization: Bearer <TOKEN>
```

**Query Parameters:**

- `status`: Filter by status (open, closed, error) - optional
- `limit`: Max positions to return (default: 50)
- `offset`: Offset for pagination (default: 0)

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "position_id": "pos_001",
      "market_1": "BTC-USD",
      "market_2": "ETH-USD",
      "status": "open",
      "entry_timestamp": "2025-11-03T10:15:00Z",
      "entry_price_1": 42000.50,
      "entry_price_2": 2250.75,
      "current_price_1": 42100.00,
      "current_price_2": 2240.00,
      "current_zscore": 1.25,
      "unrealized_pnl": 125.50,
      "unrealized_pnl_pct": 2.15
    }
  ]
}
```

### Backtest Management

#### 1. Create Backtest

```
POST /api/v1/backtests
Authorization: Bearer <TOKEN>
Content-Type: application/json
```

**Request Body:**

```json
{
  "name": "Conservative Strategy",
  "start_date": "2024-09-01",
  "end_date": "2024-10-31",
  "strategy_params": {
    "zscore_threshold": 1.5,
    "usd_per_trade": 50.0,
    "close_at_zscore_cross": true,
    "stats_window": 21
  },
  "max_pairs": 5,
  "starting_balance": 1000.0,
  "description": "Optional description"
}
```

**Response:** (200 OK)

```json
{
  "success": true,
  "data": {
    "run_id": "bt_20251103_101530_abc123",
    "name": "Conservative Strategy",
    "status": "running",
    "progress_pct": 0.0,
    "created_at": "2025-11-03T10:15:30Z"
  }
}
```

#### 2. List Backtests

```
GET /api/v1/backtests?limit=50&offset=0&status=completed&days=30
Authorization: Bearer <TOKEN>
```

**Query Parameters:**

- `limit`: Max backtests to return (default: 50, max: 500)
- `offset`: Offset for pagination (default: 0)
- `status`: Filter by status (queued, running, completed, failed, cancelled)
- `days`: Filter by last N days

**Response:**

```json
{
  "success": true,
  "data": {
    "runs": [
      {
        "run_id": "bt_20251103_101530_abc123",
        "name": "Conservative Strategy",
        "status": "completed",
        "start_date": "2024-09-01T00:00:00Z",
        "end_date": "2024-10-31T23:59:59Z",
        "total_trades": 25,
        "win_rate": 0.68,
        "total_pnl": 250.75,
        "sharpe_ratio": 1.45,
        "max_drawdown_pct": -8.2
      }
    ],
    "total": 42
  }
}
```

#### 3. Get Backtest Details

```
GET /api/v1/backtests/:run_id
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "run_id": "bt_20251103_101530_abc123",
    "name": "Conservative Strategy",
    "status": "completed",
    "start_date": "2024-09-01T00:00:00Z",
    "end_date": "2024-10-31T23:59:59Z",
    "total_pnl": 250.75,
    "total_return_pct": 25.08,
    "total_trades": 25,
    "winning_trades": 17,
    "losing_trades": 8,
    "win_rate": 0.68,
    "sharpe_ratio": 1.45,
    "max_drawdown_pct": -8.2,
    "profit_factor": 2.15,
    "starting_balance": 1000.0,
    "ending_balance": 1250.75,
    "created_at": "2025-11-03T10:15:30Z",
    "completed_at": "2025-11-03T10:45:15Z"
  }
}
```

#### 4. Get Backtest Status

```
GET /api/v1/backtests/:run_id/status
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "run_id": "bt_20251103_101530_abc123",
    "status": "running",
    "progress_pct": 65.4,
    "eta_seconds": 180,
    "current_date": "2024-09-15T00:00:00Z",
    "pairs_analyzed": 15,
    "trades_executed": 8
  }
}
```

#### 5. Get Backtest Trades

```
GET /api/v1/backtests/:run_id/trades?limit=100&offset=0&winning_only=false
Authorization: Bearer <TOKEN>
```

**Query Parameters:**

- `limit`: Max trades to return (default: 100, max: 1000)
- `offset`: Offset for pagination (default: 0)
- `winning_only`: Only return winning trades (default: false)

**Response:**

```json
{
  "success": true,
  "data": {
    "trades": [
      {
        "id": 1,
        "backtest_run_id": 1,
        "trade_id": "trade_001",
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "entry_timestamp": "2024-09-05T08:30:00Z",
        "entry_price_1": 42000.50,
        "entry_price_2": 2250.75,
        "entry_zscore": 1.8,
        "side_1": "BUY",
        "side_2": "SELL",
        "size_1": 0.05,
        "size_2": 2.00,
        "hedge_ratio": 0.05,
        "exit_timestamp": "2024-09-05T12:15:00Z",
        "exit_price_1": 42150.00,
        "exit_price_2": 2240.00,
        "exit_zscore": -0.15,
        "pnl": 125.50,
        "pnl_pct": 2.15,
        "duration_hours": 3.75
      }
    ]
  }
}
```

#### 6. Cancel Backtest

```
POST /api/v1/backtests/:run_id/cancel
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "message": "Backtest cancelled successfully"
  }
}
```

#### 7. Delete Backtest

```
DELETE /api/v1/backtests/:run_id
Authorization: Bearer <TOKEN>
```

**Response:**

```json
{
  "success": true,
  "data": {
    "message": "Backtest deleted successfully"
  }
}
```

## Error Handling

All endpoints return consistent error responses:

### 400 Bad Request

```json
{
  "success": false,
  "error": "Invalid request parameters",
  "timestamp": "2025-11-03T10:15:30Z"
}
```

### 401 Unauthorized

```json
{
  "success": false,
  "error": "Missing or invalid authorization token",
  "timestamp": "2025-11-03T10:15:30Z"
}
```

### 404 Not Found

```json
{
  "success": false,
  "error": "Resource not found",
  "timestamp": "2025-11-03T10:15:30Z"
}
```

### 500 Internal Server Error

```json
{
  "success": false,
  "error": "Internal server error: [details]",
  "timestamp": "2025-11-03T10:15:30Z"
}
```

## Database Schema

### bot_instances

- `id`: Primary key
- `instance_id`: Unique instance identifier
- `instance_name`: Human-readable name
- `user_id`: Foreign key to users table
- `status`: running, stopped, error, paused
- `network`: testnet or mainnet
- `strategy`: Strategy name
- `config`: JSON configuration and credentials
- `trading_params`: JSON trading parameters
- `total_trades`: Counter of total trades
- `total_pnl`: Total profit/loss
- `current_balance`: Current account balance
- `starting_balance`: Initial balance
- `process_id`: Process ID of bot process
- `pid`: String process ID
- `host`: Bot API host
- `port`: Bot API port
- `error_message`: Last error message
- `last_error_at`: Timestamp of last error
- `started_at`: When bot was started
- `stopped_at`: When bot was stopped
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### bot_trades

- Tracks individual trades executed by bot instances
- Foreign key to `bot_instances`
- Stores entry/exit prices, sizes, P&L

### bot_positions

- Tracks current open positions
- Updates with unrealized P&L
- Closes when position exits

### bot_alerts

- Event notifications for bot instances
- Types: error, warning, info, trade_opened, trade_closed
- Severity levels: critical, high, medium, low, info

## Example Workflows

### 1. Create and Monitor a Bot Instance

```bash
# 1. Create bot instance
curl -X POST http://localhost:8888/api/v1/bots \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "btc-eth-001",
    "instance_name": "BTC-ETH Pair Trading",
    "network": "testnet"
  }'

# 2. Start the bot
curl -X POST http://localhost:8888/api/v1/bots/btc-eth-001/start \
  -H "Authorization: Bearer $TOKEN"

# 3. Check status
curl http://localhost:8888/api/v1/bots/btc-eth-001 \
  -H "Authorization: Bearer $TOKEN"

# 4. Get statistics
curl http://localhost:8888/api/v1/bots/btc-eth-001/stats \
  -H "Authorization: Bearer $TOKEN"

# 5. Get recent trades
curl http://localhost:8888/api/v1/bots/btc-eth-001/trades?limit=20 \
  -H "Authorization: Bearer $TOKEN"

# 6. Stop the bot
curl -X POST http://localhost:8888/api/v1/bots/btc-eth-001/stop \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Run and Monitor a Backtest

```bash
# 1. Create backtest
curl -X POST http://localhost:8888/api/v1/backtests \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Conservative Strategy",
    "start_date": "2024-09-01",
    "end_date": "2024-10-31",
    "strategy_params": {
      "zscore_threshold": 1.5,
      "usd_per_trade": 50.0
    }
  }'

# 2. Monitor progress (poll /status endpoint)
curl http://localhost:8888/api/v1/backtests/bt_20251103_101530_abc123/status \
  -H "Authorization: Bearer $TOKEN"

# 3. Get final results
curl http://localhost:8888/api/v1/backtests/bt_20251103_101530_abc123 \
  -H "Authorization: Bearer $TOKEN"

# 4. Get trades from backtest
curl http://localhost:8888/api/v1/backtests/bt_20251103_101530_abc123/trades?limit=100 \
  -H "Authorization: Bearer $TOKEN"
```

## Rate Limiting

- General endpoints: 100 requests/second per IP
- Burst: 200 requests

## WebSocket Support (Coming Soon)

- Real-time position updates
- Live trade notifications
- Performance metric streaming

## Performance Notes

- Bot instance operations are proxied to Python API (expect ~100-500ms latency)
- Database queries are optimized with indexes on frequently filtered columns
- Pagination recommended for large result sets (trades, positions)
- Timestamps in ISO 8601 format with Z (UTC) indicator
