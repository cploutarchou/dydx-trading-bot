# Complete Backend-to-Frontend API Integration Guide

## Overview

The Go backend now fully proxies ALL bot API functionality to the React frontend. This document covers every endpoint available and provides TypeScript/React examples for integration.

## Architecture

```
React Frontend (Port 3000)
    ↓ HTTP REST API
Go Backend (Port 8888)
    ├─ Direct endpoints (bot instances, settings)
    └─ Delegated proxy to Python Bot API (Port 8000)
         ├─ Backtests
         ├─ Real-time data (positions, alerts, market data)
         ├─ Bot history and jobs
         └─ Advanced analytics
```

## Base URL

```
http://localhost:8888/api/v1
```

All endpoints require authentication via Bearer token in `Authorization` header.

## 1. AUTHENTICATION

### Login (No token required)

```bash
POST /auth/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123",
  "totp_token": "123456"  // Optional if 2FA enabled
}
```

**Response:**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Frontend Implementation:**

```typescript
class ApiClient {
  async login(username: string, password: string, totp?: string): Promise<{
    access_token: string;
    refresh_token: string;
    expires_in: number;
  }> {
    const response = await fetch('http://localhost:8888/auth/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, totp_token: totp })
    });
    
    if (!response.ok) throw new Error('Login failed');
    const data = await response.json();
    
    // Store tokens in localStorage
    localStorage.setItem('auth_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    
    return data;
  }
}
```

### Refresh Token

```bash
POST /auth/auth/refresh
Content-Type: application/json
Authorization: Bearer {access_token}

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### Get Current User

```bash
GET /auth/auth/me
Authorization: Bearer {access_token}
```

---

## 2. BOT INSTANCE MANAGEMENT

### Create Bot Instance

```bash
POST /bots
Content-Type: application/json
Authorization: Bearer {access_token}

{
  "instance_id": "btc-eth-001",
  "instance_name": "BTC-ETH Arbitrage",
  "credentials": {
    "address": "dydx1...",
    "mnemonic": "word1 word2..."
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
    "usd_per_trade": 10.0,
    "usd_min_collateral": 100.0,
    "close_at_zscore_cross": true
  }
}
```

**Response:**

```json
{
  "success": true,
  "message": "Bot instance created",
  "instance_id": "btc-eth-001",
  "status": "stopped"
}
```

### List Bot Instances

```bash
GET /bots
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "instances": [
    {
      "instance_id": "btc-eth-001",
      "instance_name": "BTC-ETH Arbitrage",
      "status": "running",
      "network": "testnet",
      "created_at": "2024-01-15T10:00:00Z",
      "started_at": "2024-01-15T10:30:00Z",
      "total_trades": 45,
      "active_positions": 2,
      "total_pnl_usd": 250.50,
      "daily_pnl_usd": 15.25,
      "strategy": "cointegration",
      "usd_per_trade": 10.0,
      "zscore_threshold": 1.5
    }
  ],
  "total_instances": 1,
  "running_instances": 1,
  "stopped_instances": 0,
  "error_instances": 0
}
```

**Frontend Implementation:**

```typescript
interface BotInstance {
  instance_id: string;
  instance_name: string;
  status: 'stopped' | 'starting' | 'running' | 'stopping' | 'error';
  network: 'testnet' | 'mainnet';
  total_trades: number;
  active_positions: number;
  total_pnl_usd: number;
  daily_pnl_usd: number;
  created_at: string;
  started_at?: string;
}

async function listBotInstances(): Promise<BotInstance[]> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch('http://localhost:8888/api/v1/bots', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const data = await response.json();
  return data.instances;
}
```

### Get Bot Instance Details

```bash
GET /bots/:instance_id
Authorization: Bearer {access_token}
```

### Start Bot Instance

```bash
POST /bots/:instance_id/start
Authorization: Bearer {access_token}
```

### Stop Bot Instance

```bash
POST /bots/:instance_id/stop?force=false
Authorization: Bearer {access_token}
```

### Restart Bot Instance

```bash
POST /bots/:instance_id/restart
Authorization: Bearer {access_token}
```

### Delete Bot Instance

```bash
DELETE /bots/:instance_id
Authorization: Bearer {access_token}
```

### Get Bot Stats

```bash
GET /bots/:instance_id/stats
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "total_trades": 45,
  "winning_trades": 32,
  "losing_trades": 13,
  "win_rate": 0.71,
  "total_pnl": 250.50,
  "daily_pnl": 15.25,
  "max_drawdown": -50.0,
  "sharpe_ratio": 1.45,
  "current_balance": 1250.50,
  "active_positions": 2
}
```

### Get Bot History (Events)

```bash
GET /bots/:instance_id/history?days=7
Authorization: Bearer {access_token}
```

### Get Bot Jobs

```bash
GET /bots/:instance_id/jobs?days=7
Authorization: Bearer {access_token}
```

### Get Bot Trades

```bash
GET /bots/:instance_id/trades?status=active
Authorization: Bearer {access_token}
```

---

## 3. REAL-TIME DATA ENDPOINTS

### Get Current Positions

```bash
GET /bots/:bot_instance_id/positions/current
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "positions": [
    {
      "position_id": "pos-123",
      "market_1": "BTC-USD",
      "market_2": "ETH-USD",
      "entry_price_1": 42000.0,
      "entry_price_2": 2500.0,
      "current_price_1": 42500.0,
      "current_price_2": 2600.0,
      "unrealized_pnl": 125.50,
      "unrealized_pnl_pct": 2.15,
      "entry_timestamp": "2024-01-15T10:00:00Z",
      "entry_zscore": 1.8,
      "current_zscore": 0.5,
      "hedge_ratio": 0.0595
    }
  ]
}
```

### Get Specific Position

```bash
GET /bots/:bot_instance_id/positions/:position_id
Authorization: Bearer {access_token}
```

### Get Position History

```bash
GET /bots/:bot_instance_id/position-history/:position_id?hours=24
Authorization: Bearer {access_token}
```

### Get Market Data

```bash
GET /bots/:bot_instance_id/market-data
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "BTC-USD": {
    "price": 42500.0,
    "change_24h": 2.5,
    "high_24h": 43000.0,
    "low_24h": 41500.0,
    "volume_24h": 25000000
  },
  "ETH-USD": {
    "price": 2600.0,
    "change_24h": 3.2,
    "high_24h": 2700.0,
    "low_24h": 2550.0,
    "volume_24h": 15000000
  }
}
```

### Get Realtime Stats

```bash
GET /bots/:bot_instance_id/realtime-stats
Authorization: Bearer {access_token}
```

### Get Alerts

```bash
GET /bots/:bot_instance_id/alerts?limit=50
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "alerts": [
    {
      "id": "alert-123",
      "type": "trade_opened",
      "severity": "info",
      "title": "Trade Opened",
      "message": "Position BTC-ETH opened with Z-score 1.8",
      "timestamp": "2024-01-15T10:00:00Z",
      "read": false
    },
    {
      "id": "alert-124",
      "type": "error",
      "severity": "high",
      "title": "Order Failed",
      "message": "Failed to place order: insufficient balance",
      "timestamp": "2024-01-15T10:05:00Z",
      "read": true
    }
  ]
}
```

---

## 4. BACKTEST MANAGEMENT

### Create Backtest

```bash
POST /backtests
Content-Type: application/json
Authorization: Bearer {access_token}

{
  "name": "BTC-ETH Strategy Test",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "strategy_params": {
    "zscore_threshold": 1.5,
    "max_half_life": 24,
    "stats_window": 21
  },
  "max_pairs": 10,
  "starting_balance": 1000.0
}
```

**Response:**

```json
{
  "id": 123,
  "run_id": "bt-2024-01-15-abc123",
  "name": "BTC-ETH Strategy Test",
  "status": "running",
  "progress_pct": 0,
  "created_at": "2024-01-15T10:00:00Z"
}
```

### List Backtests

```bash
GET /backtests?limit=50&offset=0&status=completed&days=30
Authorization: Bearer {access_token}
```

### Get Backtest Details

```bash
GET /backtests/:run_id
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "id": 123,
  "run_id": "bt-2024-01-15-abc123",
  "name": "BTC-ETH Strategy Test",
  "status": "completed",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "total_days": 31,
  "starting_balance": 1000.0,
  "ending_balance": 1250.50,
  "total_pnl": 250.50,
  "total_return_pct": 25.05,
  "total_trades": 45,
  "winning_trades": 32,
  "losing_trades": 13,
  "win_rate": 0.71,
  "sharpe_ratio": 1.45,
  "max_drawdown": -50.0,
  "max_drawdown_pct": 4.5,
  "profit_factor": 2.1,
  "progress_pct": 100,
  "created_at": "2024-01-15T10:00:00Z",
  "started_at": "2024-01-15T10:01:00Z",
  "completed_at": "2024-01-31T18:00:00Z"
}
```

### Get Backtest Status

```bash
GET /backtests/:run_id/status
Authorization: Bearer {access_token}
```

Returns real-time progress while backtest is running.

### Get Backtest Trades

```bash
GET /backtests/:run_id/trades?limit=100&offset=0&winning_only=false
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "trades": [
    {
      "trade_id": "trade-001",
      "market_1": "BTC-USD",
      "market_2": "ETH-USD",
      "entry_timestamp": "2024-01-15T10:00:00Z",
      "exit_timestamp": "2024-01-15T14:00:00Z",
      "entry_zscore": 1.8,
      "exit_zscore": -0.1,
      "pnl": 125.50,
      "duration_hours": 4.0
    }
  ],
  "total": 45
}
```

### Get Backtest Analytics

```bash
GET /backtests/:run_id/analytics
Authorization: Bearer {access_token}
```

Comprehensive analytics including monthly breakdown, pair analysis, etc.

### Get Position Snapshots

```bash
GET /backtests/:run_id/position-snapshots?limit=100&offset=0&market_pair=BTC-USD
Authorization: Bearer {access_token}
```

Real-time position snapshots during backtest execution.

### Compare Backtests

```bash
POST /backtests/compare
Content-Type: application/json
Authorization: Bearer {access_token}

{
  "run_ids": ["bt-001", "bt-002", "bt-003"]
}
```

### Get Backtest Summary Stats

```bash
GET /backtests/stats/summary?days=30
Authorization: Bearer {access_token}
```

System-wide backtest statistics and trends.

### Validate Against dYdX Data

```bash
GET /backtests/:run_id/dydx-validation
Authorization: Bearer {access_token}
```

Validates backtest results against real dYdX market data.

### Get Advanced Performance Metrics

```bash
GET /backtests/:run_id/performance-metrics?benchmark=BTC-USD
Authorization: Bearer {access_token}
```

Advanced metrics with market benchmarking.

### Get Live Progress

```bash
GET /backtests/:run_id/live-progress
Authorization: Bearer {access_token}
```

Real-time backtest progress with current positions and P&L.

### Cancel Backtest

```bash
POST /backtests/:run_id/cancel
Authorization: Bearer {access_token}
```

### Delete Backtest

```bash
DELETE /backtests/:run_id
Authorization: Bearer {access_token}
```

---

## 5. QUICK DEPLOY BOT

### Quick Deploy Bot Instance

```bash
POST /bots/quick-deploy?instance_name=MyBot&auto_start=true
Content-Type: application/json
Authorization: Bearer {access_token}

{
  "credentials": {
    "address": "dydx1...",
    "mnemonic": "word1 word2..."
  },
  "trading_params": {
    "is_testnet": true,
    "zscore_threshold": 1.5,
    "usd_per_trade": 10.0
  }
}
```

Creates and optionally starts a bot instance in one call.

---

## 6. SYSTEM ENDPOINTS

### Health Check

```bash
GET /health
```

### System Status

```bash
GET /api/v1/system/status
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "healthy",
  "uptime_seconds": 12345,
  "active_bots": 3,
  "running_backtests": 1,
  "total_trades_today": 45,
  "pnl_today": 250.50,
  "memory_usage_mb": 512,
  "cpu_usage_percent": 25
}
```

---

## Frontend Zustand Store Example

```typescript
import create from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthStore {
  token: string | null;
  refreshToken: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      login: async (username: string, password: string) => {
        const response = await fetch('http://localhost:8888/auth/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        set({ token: data.access_token, refreshToken: data.refresh_token });
      },
      logout: () => {
        set({ token: null, refreshToken: null });
      },
      isAuthenticated: () => !!get().token
    }),
    { name: 'auth-store' }
  )
);

interface BotStore {
  bots: BotInstance[];
  selectedBot: BotInstance | null;
  loadBots: () => Promise<void>;
  selectBot: (bot: BotInstance) => void;
  startBot: (instanceId: string) => Promise<void>;
  stopBot: (instanceId: string) => Promise<void>;
}

export const useBotStore = create<BotStore>((set, get) => ({
  bots: [],
  selectedBot: null,
  loadBots: async () => {
    const token = useAuthStore.getState().token;
    const response = await fetch('http://localhost:8888/api/v1/bots', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await response.json();
    set({ bots: data.instances });
  },
  selectBot: (bot: BotInstance) => {
    set({ selectedBot: bot });
  },
  startBot: async (instanceId: string) => {
    const token = useAuthStore.getState().token;
    await fetch(`http://localhost:8888/api/v1/bots/${instanceId}/start`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    get().loadBots();
  },
  stopBot: async (instanceId: string) => {
    const token = useAuthStore.getState().token;
    await fetch(`http://localhost:8888/api/v1/bots/${instanceId}/stop`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    get().loadBots();
  }
}));
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "error": "Descriptive error message",
  "status": 400,
  "timestamp": "2024-01-15T10:00:00Z"
}
```

HTTP Status Codes:

- `200` - Success
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error

---

## Rate Limiting

All endpoints are rate-limited to **100 requests/second per IP address** with a burst capacity of **200 requests**.

---

## Environment Variables

Add these to your `.env` file:

```bash
# Backend Server
API_PORT=8888
API_HOST=localhost

# Bot API Configuration
BOT_API_URL=http://localhost:8000
BOT_API_TOKEN=

# Database
DATABASE_URL=postgresql://user:pass@localhost/db

# JWT
JWT_SECRET=your-secret-key
JWT_EXPIRY=1800
```

---

## Testing Endpoints with cURL

```bash
# Login
curl -X POST http://localhost:8888/auth/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# List bots
curl -X GET http://localhost:8888/api/v1/bots \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create backtest
curl -X POST http://localhost:8888/api/v1/backtests \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Test",
    "start_date":"2024-01-01",
    "end_date":"2024-01-31",
    "starting_balance":1000
  }'
```

---

This comprehensive guide provides everything needed to integrate the Go backend with the React frontend. All 50+ endpoints are now available through the unified Go backend!
