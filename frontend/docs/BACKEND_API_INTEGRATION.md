# Frontend Backend API Integration Guide

This document provides comprehensive guidance on how the React frontend integrates with the Go backend API to interact with all bot and backtest functionalities.

## Architecture Overview

```
Frontend (React @ localhost:5173)
    ↓
Backend API (Go @ localhost:8888)
    ↓
Bot API Proxy (FastAPI @ localhost:8000)
```

The backend acts as a **proxy and orchestration layer**:

- All frontend requests go to the backend first
- Backend authenticates requests via JWT middleware
- Backend proxies eligible requests to the bot API
- Backend manages database state and persistence
- Backend handles caching, rate limiting, and security

## Authentication

All API requests (except `/health` and `/auth/*`) require JWT authentication.

### Login Flow

```typescript
// 1. User logs in
const response = await api.post('/api/v1/auth/login', {
  username: 'user@example.com',
  password: 'password'
});

// Response contains access_token and refresh_token
const { access_token, refresh_token } = response.data;

// 2. Store tokens (typically in Zustand store with localStorage)
useAuthStore.setState({
  token: access_token,
  refreshToken: refresh_token
});

// 3. All subsequent requests automatically include Bearer token
// Headers: { Authorization: 'Bearer <access_token>' }
```

### Token Refresh

Access tokens expire after 30 minutes. Refresh tokens last 7 days.

```typescript
// Automatically called when access token expires
const refreshTokens = async () => {
  const response = await api.post('/api/v1/auth/refresh', {
    refresh_token: useAuthStore.getState().refreshToken
  });
  
  // Update both tokens
  useAuthStore.setState({
    token: response.data.access_token,
    refreshToken: response.data.refresh_token
  });
};
```

## API Endpoints Reference

### Base URL

```
http://localhost:8888/api/v1
```

### Authentication Endpoints

#### Register User

```http
POST /auth/register
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "secure_password",
  "email": "user@example.com"
}

Response 201:
{
  "id": "user-id",
  "username": "user@example.com",
  "email": "user@example.com",
  "created_at": "2025-11-03T20:15:00Z"
}
```

#### Login

```http
POST /auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "secure_password"
}

Response 200:
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### Refresh Token

```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGc..."
}

Response 200:
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "expires_in": 1800
}
```

#### Get Current User

```http
GET /users/me
Authorization: Bearer <access_token>

Response 200:
{
  "id": "user-id",
  "username": "user@example.com",
  "email": "user@example.com",
  "profile": {
    "first_name": "John",
    "last_name": "Doe"
  },
  "created_at": "2025-11-03T20:00:00Z"
}
```

#### Update Profile

```http
PUT /profile
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "first_name": "John",
  "last_name": "Doe",
  "email": "newemail@example.com"
}

Response 200:
{
  "success": true,
  "message": "Profile updated successfully"
}
```

---

### Bot Instance Management

#### Create Bot Instance

```http
POST /bots
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "instance_id": "btc-eth-bot-01",
  "name": "BTC-ETH Arbitrage Bot",
  "credentials": {
    "address": "dydx1...",
    "mnemonic": "word1 word2 ..."
  },
  "trading_params": {
    "is_testnet": false,
    "zscore_threshold": 1.5,
    "max_half_life": 24,
    "usd_per_trade": 100.0
  }
}

Response 201:
{
  "instance_id": "btc-eth-bot-01",
  "status": "CREATED",
  "created_at": "2025-11-03T20:15:00Z",
  "last_heartbeat": null
}
```

#### List Bot Instances

```http
GET /bots
Authorization: Bearer <access_token>

Optional Query Parameters:
  ?status=RUNNING,STOPPED    # Filter by status
  ?limit=50                  # Default 50, max 200
  ?offset=0                  # Pagination offset

Response 200:
{
  "success": true,
  "count": 3,
  "data": [
    {
      "instance_id": "btc-eth-bot-01",
      "name": "BTC-ETH Arbitrage Bot",
      "status": "RUNNING",
      "last_heartbeat": "2025-11-03T20:14:55Z",
      "uptime_seconds": 125,
      "total_trades": 42,
      "win_rate": 0.71,
      "pnl": 125.50,
      "created_at": "2025-11-03T20:15:00Z"
    }
  ]
}
```

#### Get Bot Instance Details

```http
GET /bots/:instance_id
Authorization: Bearer <access_token>

Response 200:
{
  "instance_id": "btc-eth-bot-01",
  "name": "BTC-ETH Arbitrage Bot",
  "status": "RUNNING",
  "credentials": { "address": "dydx1..." },
  "trading_params": { ... },
  "stats": {
    "total_trades": 42,
    "win_rate": 0.71,
    "pnl": 125.50,
    "open_positions": 2,
    "daily_volume": 5000.00,
    "uptime_seconds": 125
  },
  "last_heartbeat": "2025-11-03T20:14:55Z",
  "created_at": "2025-11-03T20:15:00Z"
}
```

#### Start Bot Instance

```http
POST /bots/:instance_id/start
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "strategy": "cointegration",
  "pairs": ["BTC-USD", "ETH-USD"]
}

Response 200:
{
  "success": true,
  "instance_id": "btc-eth-bot-01",
  "status": "RUNNING",
  "message": "Bot started successfully"
}
```

#### Stop Bot Instance

```http
POST /bots/:instance_id/stop
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "instance_id": "btc-eth-bot-01",
  "status": "STOPPED",
  "message": "Bot stopped successfully"
}
```

#### Restart Bot Instance

```http
POST /bots/:instance_id/restart
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "instance_id": "btc-eth-bot-01",
  "status": "RUNNING",
  "message": "Bot restarted successfully"
}
```

#### Delete Bot Instance

```http
DELETE /bots/:instance_id
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "message": "Bot instance deleted"
}
```

---

### Bot Statistics & History

#### Get Bot Statistics

```http
GET /bots/:instance_id/stats
Authorization: Bearer <access_token>

Response 200:
{
  "total_trades": 42,
  "win_rate": 0.71,
  "total_pnl": 125.50,
  "daily_pnl": 25.30,
  "open_positions": 2,
  "daily_volume": 5000.00,
  "uptime_seconds": 125,
  "average_trade_duration_minutes": 45,
  "sharpe_ratio": 1.2,
  "sortino_ratio": 1.8
}
```

#### Get Bot Instance Trades

```http
GET /bots/:instance_id/trades
Authorization: Bearer <access_token>

Optional Query Parameters:
  ?limit=50
  ?offset=0
  ?status=FILLED,PENDING
  ?start_date=2025-11-01
  ?end_date=2025-11-03

Response 200:
{
  "success": true,
  "count": 42,
  "data": [
    {
      "trade_id": "trade-001",
      "market_1": "BTC-USD",
      "market_2": "ETH-USD",
      "side_1": "BUY",
      "side_2": "SELL",
      "size_1": 0.5,
      "size_2": 8.0,
      "status": "FILLED",
      "entry_z_score": 1.5,
      "exit_z_score": -0.1,
      "pnl": 125.50,
      "pnl_percent": 2.3,
      "entry_time": "2025-11-03T10:30:00Z",
      "exit_time": "2025-11-03T11:15:00Z",
      "duration_minutes": 45
    }
  ]
}
```

#### Get Bot History

```http
GET /bots/:instance_id/history
Authorization: Bearer <access_token>

Optional Query Parameters:
  ?days=7            # Default 7
  ?granularity=hourly  # hourly, daily, weekly

Response 200:
{
  "success": true,
  "data": [
    {
      "timestamp": "2025-11-03T00:00:00Z",
      "pnl": 125.50,
      "trades_count": 6,
      "open_positions": 2,
      "daily_volume": 5000.00,
      "win_rate": 0.71
    }
  ]
}
```

#### Get Bot Jobs/Events

```http
GET /bots/:instance_id/jobs
Authorization: Bearer <access_token>

Optional Query Parameters:
  ?limit=50
  ?offset=0
  ?type=ERROR,WARNING,INFO

Response 200:
{
  "success": true,
  "count": 42,
  "data": [
    {
      "job_id": "job-001",
      "type": "TRADE_EXECUTED",
      "status": "COMPLETED",
      "message": "Successfully executed BTC-USD / ETH-USD pair",
      "timestamp": "2025-11-03T20:14:55Z",
      "duration_ms": 1250,
      "error": null
    }
  ]
}
```

---

### Real-Time Bot Data

#### Get Current Positions

```http
GET /bots/:instance_id/positions/current
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "data": [
    {
      "position_id": "pos-001",
      "market_1": "BTC-USD",
      "market_2": "ETH-USD",
      "side_1": "BUY",
      "side_2": "SELL",
      "size_1": 0.5,
      "size_2": 8.0,
      "entry_price_1": 45000.00,
      "entry_price_2": 2500.00,
      "current_price_1": 45100.00,
      "current_price_2": 2510.00,
      "unrealized_pnl": 50.00,
      "unrealized_pnl_percent": 0.91,
      "entry_time": "2025-11-03T10:30:00Z",
      "current_z_score": 0.5,
      "mark_price_1": 45100.00,
      "mark_price_2": 2510.00
    }
  ]
}
```

#### Get Specific Position

```http
GET /bots/:instance_id/positions/:position_id
Authorization: Bearer <access_token>

Response 200:
{
  "position_id": "pos-001",
  "market_1": "BTC-USD",
  "market_2": "ETH-USD",
  "side_1": "BUY",
  "side_2": "SELL",
  "size_1": 0.5,
  "size_2": 8.0,
  "entry_price_1": 45000.00,
  "entry_price_2": 2500.00,
  "current_price_1": 45100.00,
  "current_price_2": 2510.00,
  "unrealized_pnl": 50.00,
  "unrealized_pnl_percent": 0.91,
  "entry_time": "2025-11-03T10:30:00Z",
  "current_z_score": 0.5,
  "hedge_ratio": 16.0,
  "status": "LIVE",
  "history": [...]
}
```

#### Get Position History

```http
GET /bots/:instance_id/position-history/:position_id
Authorization: Bearer <access_token>

Optional Query Parameters:
  ?hours=24        # Default 24

Response 200:
{
  "success": true,
  "position_id": "pos-001",
  "market_1": "BTC-USD",
  "market_2": "ETH-USD",
  "data": [
    {
      "timestamp": "2025-11-03T20:00:00Z",
      "price_1": 45000.00,
      "price_2": 2500.00,
      "z_score": 1.2,
      "unrealized_pnl": 30.00,
      "unrealized_pnl_percent": 0.55
    }
  ]
}
```

#### Get Market Data

```http
GET /bots/:instance_id/market-data
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "data": {
    "BTC-USD": {
      "symbol": "BTC-USD",
      "last_price": 45100.00,
      "bid": 45095.00,
      "ask": 45105.00,
      "24h_volume": 15000000.00,
      "24h_change_percent": 2.3,
      "market_cap_rank": 1,
      "liquidity_score": 9.8
    },
    "ETH-USD": {
      "symbol": "ETH-USD",
      "last_price": 2510.00,
      "bid": 2509.00,
      "ask": 2511.00,
      "24h_volume": 8000000.00,
      "24h_change_percent": 1.5,
      "market_cap_rank": 2,
      "liquidity_score": 9.6
    }
  }
}
```

#### Get Real-Time Stats

```http
GET /bots/:instance_id/realtime-stats
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "uptime_seconds": 125,
  "total_trades": 42,
  "trades_today": 6,
  "open_positions": 2,
  "total_pnl": 125.50,
  "daily_pnl": 25.30,
  "pnl_percent": 2.3,
  "win_rate": 0.71,
  "average_trade_duration_minutes": 45,
  "last_trade_time": "2025-11-03T20:14:55Z",
  "last_error": null,
  "last_error_time": null,
  "api_latency_ms": 45,
  "db_latency_ms": 12
}
```

#### Get Alerts

```http
GET /bots/:instance_id/alerts
Authorization: Bearer <access_token>

Optional Query Parameters:
  ?limit=50
  ?severity=ERROR,WARNING,INFO

Response 200:
{
  "success": true,
  "count": 5,
  "data": [
    {
      "alert_id": "alert-001",
      "severity": "WARNING",
      "message": "High Z-score detected: 2.1 (threshold: 1.5)",
      "timestamp": "2025-11-03T20:14:55Z",
      "acknowledged": false
    }
  ]
}
```

---

### Backtest Management

#### Create Backtest

```http
POST /backtests
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "BTC-ETH Jan 2024",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "initial_capital": 10000.00,
  "strategy": "cointegration",
  "pairs": [
    {
      "base_market": "BTC-USD",
      "quote_market": "ETH-USD",
      "hedge_ratio": 0.05,
      "half_life": 12
    }
  ],
  "trading_params": {
    "zscore_threshold": 1.5,
    "usd_per_trade": 100.0,
    "max_half_life": 24,
    "slippage_percent": 0.05
  }
}

Response 201:
{
  "run_id": "backtest-001",
  "status": "PENDING",
  "name": "BTC-ETH Jan 2024",
  "created_at": "2025-11-03T20:15:00Z",
  "estimated_completion": "2025-11-03T20:30:00Z"
}
```

#### List Backtests

```http
GET /backtests
Authorization: Bearer <access_token>

Optional Query Parameters:
  ?limit=50
  ?offset=0
  ?status=COMPLETED,RUNNING,FAILED
  ?days=30          # Show backtests from last 30 days
  ?start_date=2025-11-01

Response 200:
{
  "success": true,
  "count": 15,
  "data": [
    {
      "run_id": "backtest-001",
      "name": "BTC-ETH Jan 2024",
      "status": "COMPLETED",
      "start_date": "2024-01-01",
      "end_date": "2024-01-31",
      "total_pnl": 500.25,
      "total_pnl_percent": 5.0,
      "total_trades": 42,
      "win_rate": 0.71,
      "sharpe_ratio": 1.2,
      "max_drawdown_percent": 3.5,
      "created_at": "2025-11-03T20:15:00Z",
      "completed_at": "2025-11-03T20:30:00Z"
    }
  ]
}
```

#### Get Backtest Details

```http
GET /backtests/:run_id
Authorization: Bearer <access_token>

Response 200:
{
  "run_id": "backtest-001",
  "name": "BTC-ETH Jan 2024",
  "status": "COMPLETED",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "total_pnl": 500.25,
  "total_pnl_percent": 5.0,
  "total_trades": 42,
  "win_rate": 0.71,
  "sharpe_ratio": 1.2,
  "sortino_ratio": 1.8,
  "max_drawdown_percent": 3.5,
  "calmar_ratio": 1.4,
  "pairs": [
    {
      "base_market": "BTC-USD",
      "quote_market": "ETH-USD",
      "trades": 42,
      "pnl": 500.25,
      "win_rate": 0.71
    }
  ],
  "created_at": "2025-11-03T20:15:00Z",
  "completed_at": "2025-11-03T20:30:00Z"
}
```

#### Get Backtest Status

```http
GET /backtests/:run_id/status
Authorization: Bearer <access_token>

Response 200:
{
  "run_id": "backtest-001",
  "status": "RUNNING",
  "progress_percent": 65,
  "trades_completed": 27,
  "trades_total": 42,
  "current_date": "2024-01-20",
  "estimated_completion_seconds": 300
}
```

#### Get Backtest Trades

```http
GET /backtests/:run_id/trades
Authorization: Bearer <access_token>

Optional Query Parameters:
  ?limit=50
  ?offset=0

Response 200:
{
  "success": true,
  "count": 42,
  "data": [
    {
      "trade_id": "trade-001",
      "base_market": "BTC-USD",
      "quote_market": "ETH-USD",
      "entry_z_score": 1.5,
      "exit_z_score": -0.1,
      "entry_time": "2024-01-10T10:30:00Z",
      "exit_time": "2024-01-10T11:15:00Z",
      "entry_price_1": 42000.00,
      "entry_price_2": 2300.00,
      "exit_price_1": 42100.00,
      "exit_price_2": 2310.00,
      "pnl": 50.00,
      "pnl_percent": 0.91
    }
  ]
}
```

#### Get Backtest Analytics

```http
GET /backtests/:run_id/analytics
Authorization: Bearer <access_token>

Response 200:
{
  "run_id": "backtest-001",
  "daily_pnl": [
    { "date": "2024-01-01", "pnl": 10.00, "trades": 1 },
    { "date": "2024-01-02", "pnl": 15.50, "trades": 2 }
  ],
  "drawdown_analysis": {
    "max_drawdown": -175.00,
    "max_drawdown_percent": 3.5,
    "max_drawdown_duration_days": 5
  },
  "monthly_returns": [
    { "month": "2024-01", "return_percent": 5.0 }
  ],
  "trade_distribution": {
    "by_hour": {...},
    "by_day": {...}
  }
}
```

#### Get Backtest Performance Metrics

```http
GET /backtests/:run_id/performance-metrics
Authorization: Bearer <access_token>

Response 200:
{
  "total_return": 5.0,
  "annualized_return": 60.0,
  "sharpe_ratio": 1.2,
  "sortino_ratio": 1.8,
  "calmar_ratio": 1.4,
  "max_drawdown": -175.00,
  "max_drawdown_percent": 3.5,
  "win_rate": 0.71,
  "profit_factor": 2.1,
  "recovery_factor": 2.85,
  "trade_count": 42,
  "average_trade_pnl": 11.91,
  "average_winning_trade": 22.50,
  "average_losing_trade": -10.75,
  "consecutive_wins": 5,
  "consecutive_losses": 3
}
```

#### Compare Backtests

```http
POST /backtests/compare
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "run_ids": ["backtest-001", "backtest-002", "backtest-003"],
  "metrics": ["total_return", "sharpe_ratio", "max_drawdown", "win_rate"]
}

Response 200:
{
  "success": true,
  "comparison": [
    {
      "run_id": "backtest-001",
      "total_return": 5.0,
      "sharpe_ratio": 1.2,
      "max_drawdown": -3.5,
      "win_rate": 0.71
    },
    {
      "run_id": "backtest-002",
      "total_return": 6.5,
      "sharpe_ratio": 1.4,
      "max_drawdown": -2.8,
      "win_rate": 0.75
    }
  ],
  "best": {
    "total_return": "backtest-002",
    "sharpe_ratio": "backtest-002",
    "max_drawdown": "backtest-002"
  }
}
```

#### Cancel Backtest

```http
POST /backtests/:run_id/cancel
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "run_id": "backtest-001",
  "status": "CANCELLED",
  "message": "Backtest cancelled successfully"
}
```

#### Get Backtest Summary Stats

```http
GET /backtests/stats/summary
Authorization: Bearer <access_token>

Optional Query Parameters:
  ?days=30

Response 200:
{
  "success": true,
  "total_backtests": 15,
  "completed_backtests": 13,
  "running_backtests": 1,
  "failed_backtests": 1,
  "average_return": 3.5,
  "average_sharpe_ratio": 1.1,
  "best_return": 8.2,
  "worst_return": -2.1,
  "total_trades": 500,
  "average_win_rate": 0.68
}
```

#### Get Backtest Position Snapshots

```http
GET /backtests/:run_id/position-snapshots
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "snapshots": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "positions": [
        {
          "market_1": "BTC-USD",
          "market_2": "ETH-USD",
          "side_1": "BUY",
          "side_2": "SELL",
          "size_1": 0.5,
          "size_2": 8.0,
          "unrealized_pnl": 25.00
        }
      ]
    }
  ]
}
```

#### Get Backtest dYdX Validation

```http
GET /backtests/:run_id/dydx-validation
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "run_id": "backtest-001",
  "validation": {
    "orderability": {
      "status": "VALID",
      "message": "All orders would be orderable on mainnet"
    },
    "market_availability": {
      "status": "VALID",
      "message": "All markets were available during backtest period"
    },
    "liquidity": {
      "status": "WARNING",
      "message": "Some periods had low liquidity, real execution may differ"
    },
    "fees": {
      "total_fees": 50.00,
      "fee_impact_percent": 1.0
    }
  }
}
```

#### Get Live Backtest Progress (WebSocket)

```typescript
// Real-time updates via WebSocket
const socket = new WebSocket(`ws://localhost:8888/api/v1/backtests/:run_id/live-progress?token=${accessToken}`);

socket.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(`Progress: ${progress.progress_percent}%`);
  console.log(`Current date: ${progress.current_date}`);
  console.log(`Trades completed: ${progress.trades_completed}/${progress.trades_total}`);
};
```

#### Delete Backtest

```http
DELETE /backtests/:run_id
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "message": "Backtest deleted successfully"
}
```

---

### Quick Deploy

#### Quick Deploy (Create and Start Bot)

```http
POST /bots/quick-deploy
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "instance_id": "quick-bot-001",
  "credentials": {
    "address": "dydx1...",
    "mnemonic": "word1 word2 ..."
  },
  "pairs": ["BTC-USD|ETH-USD", "SOL-USD|AVAX-USD"],
  "trading_params": {
    "is_testnet": false,
    "zscore_threshold": 1.5,
    "usd_per_trade": 100.0
  }
}

Response 201:
{
  "success": true,
  "instance_id": "quick-bot-001",
  "status": "RUNNING",
  "message": "Bot deployed and started successfully"
}
```

---

### System Status

#### Health Check

```http
GET /health

Response 200:
{
  "status": "healthy",
  "timestamp": "2025-11-03T20:15:00Z",
  "version": "1.0.0"
}
```

#### System Status

```http
GET /api/v1/system/status
Authorization: Bearer <access_token>

Response 200:
{
  "success": true,
  "status": "operational",
  "components": {
    "database": "healthy",
    "bot_api": "healthy",
    "cache": "healthy",
    "indexer": "healthy"
  },
  "metrics": {
    "active_bots": 3,
    "active_backtests": 1,
    "total_trades_24h": 42,
    "api_requests_1h": 1250,
    "average_latency_ms": 45
  }
}
```

---

## Error Handling

### Common Error Responses

#### 400 Bad Request

```json
{
  "success": false,
  "error": "Invalid request parameters",
  "details": {
    "field": "zscore_threshold",
    "message": "Must be between 0.1 and 5.0"
  }
}
```

#### 401 Unauthorized

```json
{
  "success": false,
  "error": "Unauthorized",
  "message": "Invalid or expired token"
}
```

#### 403 Forbidden

```json
{
  "success": false,
  "error": "Forbidden",
  "message": "You don't have permission to access this resource"
}
```

#### 404 Not Found

```json
{
  "success": false,
  "error": "Not found",
  "message": "Bot instance not found",
  "resource": "instance_id",
  "value": "non-existent-bot"
}
```

#### 429 Too Many Requests

```json
{
  "success": false,
  "error": "Rate limit exceeded",
  "retry_after_seconds": 60
}
```

#### 500 Internal Server Error

```json
{
  "success": false,
  "error": "Internal server error",
  "trace_id": "abc-123-def",
  "message": "An unexpected error occurred"
}
```

### Frontend Error Handling Pattern

```typescript
// Recommended error handling in TypeScript
async function apiCall() {
  try {
    const response = await fetch('/api/v1/bots', {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (!response.ok) {
      const errorData = await response.json();
      
      switch (response.status) {
        case 401:
          // Handle token expiration
          await refreshTokens();
          // Retry request
          break;
        
        case 429:
          // Handle rate limiting
          await wait(errorData.retry_after_seconds * 1000);
          // Retry request
          break;
        
        case 400:
          // Handle validation error
          console.error('Validation error:', errorData.details);
          break;
        
        default:
          console.error('API Error:', errorData.error);
      }
      
      throw new Error(errorData.message || 'API request failed');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Request failed:', error);
    throw error;
  }
}
```

---

## Rate Limiting

All endpoints are subject to rate limiting:

- **Public endpoints** (health, auth): 100 requests/minute
- **Authenticated endpoints**: 1000 requests/minute per user
- **Backtest endpoints**: 50 concurrent backtests per user
- **WebSocket connections**: 10 concurrent connections per user

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1667500200
```

---

## WebSocket Connections

### Real-Time Bot Updates

```typescript
const socket = new WebSocket(
  `ws://localhost:8888/api/v1/bots/:instance_id/updates?token=${accessToken}`
);

socket.onmessage = (event) => {
  const update = JSON.parse(event.data);
  
  switch (update.type) {
    case 'TRADE_EXECUTED':
      console.log('New trade:', update.trade);
      break;
    case 'POSITION_OPENED':
      console.log('Position opened:', update.position);
      break;
    case 'POSITION_CLOSED':
      console.log('Position closed:', update.position);
      break;
    case 'ALERT':
      console.log('Alert:', update.alert);
      break;
  }
};

socket.onerror = (error) => {
  console.error('WebSocket error:', error);
};

socket.onclose = () => {
  console.log('WebSocket disconnected');
  // Attempt to reconnect
};
```

---

## Caching Strategy

The backend implements intelligent caching:

- **Bot stats**: Cached for 60 seconds
- **Backtest results**: Cached for 24 hours
- **Market data**: Cached for 30 seconds
- **Position snapshots**: Cached for 5 seconds
- **User profile**: Cached for 1 hour

Cache headers in responses:

```
Cache-Control: max-age=60, must-revalidate
ETag: "abc123def456"
```

---

## Next Steps

- See [FRONTEND_DEVELOPMENT_GUIDE.md](./FRONTEND_DEVELOPMENT_GUIDE.md) for component patterns
- See [API_CLIENT_EXAMPLES.md](./API_CLIENT_EXAMPLES.md) for TypeScript implementation examples
- See [WEBSOCKET_GUIDE.md](./WEBSOCKET_GUIDE.md) for real-time updates
