# Backend-to-Bot API Coverage Checklist

This document verifies that the Go backend properly proxies all Python bot API endpoints.

## Boundary Rule

Frontend code must consume these routes through the Go backend only. Browser code must not call the bot service directly.

See [Backend-Only Integration Checklist](/home/chris/workspace/dydx-trading-bot/frontend/docs/architecture/BACKEND_ONLY_INTEGRATION_CHECKLIST.md).

## ✅ Endpoint Coverage Matrix

### Authentication Endpoints (Handled by Backend, not Bot API)

| Endpoint | Method | Backend | Bot API | Notes |
|----------|--------|---------|---------|-------|
| `/auth/register` | POST | ✅ | N/A | User registration |
| `/auth/login` | POST | ✅ | N/A | User authentication |
| `/auth/refresh` | POST | ✅ | N/A | Token refresh |
| `/users/me` | GET | ✅ | N/A | Current user profile |
| `/profile` | PUT | ✅ | N/A | Update profile |

### Bot Instance Management

#### Create & List

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/bots` | POST | ✅ | ✅ | **PROXIED** | Create bot instance |
| `/api/v1/bots` | GET | ✅ | ✅ | **PROXIED** | List all bot instances |
| `/api/v1/bots/:instance_id` | GET | ✅ | ✅ | **PROXIED** | Get specific bot details |
| `/api/v1/bots/:instance_id` | DELETE | ✅ | ✅ | **PROXIED** | Delete bot instance |

#### Bot Control

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/bots/:instance_id/start` | POST | ✅ | ✅ | **PROXIED** | Start trading |
| `/api/v1/bots/:instance_id/stop` | POST | ✅ | ✅ | **PROXIED** | Stop trading |
| `/api/v1/bots/:instance_id/restart` | POST | ✅ | ✅ | **PROXIED** | Restart bot |

#### Bot Statistics & History

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/bots/:instance_id/stats` | GET | ✅ | ✅ | **PROXIED** | Trading statistics |
| `/api/v1/bots/:instance_id/trades` | GET | ✅ | ✅ | **PROXIED** | Trade history |
| `/api/v1/bots/:instance_id/history` | GET | ✅ | ✅ | **PROXIED** | Daily history |
| `/api/v1/bots/:instance_id/jobs` | GET | ✅ | ✅ | **PROXIED** | Job/event logs |

### Real-Time Bot Data

#### Current State

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/bots/:instance_id/positions/current` | GET | ✅ | ✅ | **PROXIED** | Open positions |
| `/api/v1/bots/:instance_id/positions/:position_id` | GET | ✅ | ✅ | **PROXIED** | Single position |
| `/api/v1/bots/:instance_id/position-history/:position_id` | GET | ✅ | ✅ | **PROXIED** | Position history |
| `/api/v1/bots/:instance_id/market-data` | GET | ✅ | ✅ | **PROXIED** | Market prices |
| `/api/v1/bots/:instance_id/realtime-stats` | GET | ✅ | ✅ | **PROXIED** | Live stats |
| `/api/v1/bots/:instance_id/alerts` | GET | ✅ | ✅ | **PROXIED** | Alerts/warnings |
7890-=
### Control Plane & Recovery

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/capabilities` | GET | ✅ | ✅ | **PROXIED** | Bot service discovery surface |
| `/api/v1/runtime/db-config` | GET | ✅ | ✅ | **PROXIED** | Admin-only runtime DB diagnostics |
| `/api/v1/backtests/interrupted` | GET | ✅ | ✅ | **PROXIED** | Interrupted/orphaned run visibility |
| `/api/v1/backtests/interrupted/reconcile` | POST | ✅ | ✅ | **PROXIED** | Reconcile interrupted runs |
| `/api/v1/admin/backtests/interrupted` | GET | ✅ | ✅ | **PROXIED** | Admin alias for interrupted runs |
| `/api/v1/admin/backtests/interrupted/reconcile` | POST | ✅ | ✅ | **PROXIED** | Admin alias for reconcile |

### Quick Deploy

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/bots/quick-deploy` | POST | ✅ | ✅ | **PROXIED** | Create + start bot |

### Backtest Management

#### Create & List

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/backtests` | POST | ✅ | ✅ | **PROXIED** | Create backtest |
| `/api/v1/backtests` | GET | ✅ | ✅ | **PROXIED** | List backtests |
| `/api/v1/backtests/:run_id` | GET | ✅ | ✅ | **PROXIED** | Get backtest details |
| `/api/v1/backtests/:run_id` | DELETE | ✅ | ✅ | **PROXIED** | Delete backtest |

#### Backtest Monitoring & Control

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/backtests/:run_id/status` | GET | ✅ | ✅ | **PROXIED** | Progress status |
| `/api/v1/backtests/:run_id/cancel` | POST | ✅ | ✅ | **PROXIED** | Cancel running backtest |
| `/api/v1/backtests/:run_id/live-progress` | WS | ✅ | ✅ | **PROXIED** | WebSocket stream |

#### Backtest Results

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/backtests/:run_id/trades` | GET | ✅ | ✅ | **PROXIED** | Backtest trades |
| `/api/v1/backtests/:run_id/analytics` | GET | ✅ | ✅ | **PROXIED** | Analytics data |
| `/api/v1/backtests/:run_id/performance-metrics` | GET | ✅ | ✅ | **PROXIED** | Performance metrics |
| `/api/v1/backtests/:run_id/position-snapshots` | GET | ✅ | ✅ | **PROXIED** | Position snapshots |
| `/api/v1/backtests/:run_id/dydx-validation` | GET | ✅ | ✅ | **PROXIED** | dYdX validation |

#### Backtest Analysis

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/api/v1/backtests/stats/summary` | GET | ✅ | ✅ | **PROXIED** | Summary stats |
| `/api/v1/backtests/compare` | POST | ✅ | ✅ | **PROXIED** | Compare multiple |

### System Endpoints

| Endpoint | Method | Backend | Bot API | Status | Notes |
|----------|--------|---------|---------|--------|-------|
| `/health` | GET | ✅ | ✅ | **PROXIED** | Health check |
| `/api/v1/system/status` | GET | ✅ | ✅ | **PROXIED** | System status |
| `/ready` | GET | ✅ | ✅ | **COMPOSITE** | Backend readiness includes bot readiness |

---

## 📊 Coverage Summary

```
Total Bot API Endpoints: 38
Total Backend Proxied: 38
Coverage: 100% ✅

Breakdown:
- Bot Instance Management: 7/7 (100%)
- Real-Time Data: 6/6 (100%)
- Backtest Management: 13/13 (100%)
- Control Plane & Recovery: 6/6 (100%)
- System Status: 3/3 (100%)
- Other: 3/3 (100%)
```

---

## 🔄 Proxy Implementation Pattern

All proxied endpoints follow this pattern in `bot_api_delegate_routes.go`:

```go
// Example: GET /api/v1/bots
botGroup.GET("/:instance_id/positions/current", func(c *gin.Context) {
    botID := c.Param("instance_id")
    
    // Call Bot API
    result, err := apiClient.GetCurrentPositions(botID)
    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }
    
    // Return to frontend
    c.JSON(200, result)
})
```

### Key Features of Proxy Implementation

✅ **Full Transparency**: All parameters passed through  
✅ **Error Handling**: Proper HTTP status codes  
✅ **Authentication**: JWT middleware on all endpoints  
✅ **Rate Limiting**: Backend rate limits applied  
✅ **Caching**: Intelligent caching for expensive operations  
✅ **Logging**: All requests logged for audit trail  

---

## 🚀 Frontend Integration Checklist

When building frontend components, use this checklist:

### Before Starting Component

- [ ] Identify which backend endpoint is needed
- [ ] Check this coverage matrix for endpoint availability
- [ ] Review API client method in `src/api/client.ts`
- [ ] Check authentication requirements (all require Bearer token)

### During Development

- [ ] Handle loading state
- [ ] Handle error state with user-friendly messages
- [ ] Handle empty data state
- [ ] Add retry logic for transient failures
- [ ] Implement pagination for list endpoints
- [ ] Add debouncing for rapid requests

### Error Handling

- [ ] 401: Redirect to login
- [ ] 403: Show permission denied
- [ ] 400: Show validation errors
- [ ] 429: Show rate limit message with retry-after
- [ ] 500: Show generic error with trace ID

### Performance

- [ ] Use caching where appropriate
- [ ] Implement request deduplication
- [ ] Use React.memo for expensive components
- [ ] Use custom hooks for data fetching
- [ ] Implement WebSocket for real-time updates

---

## 📡 WebSocket Endpoints

Real-time updates via WebSocket:

```typescript
// Backtest Progress Updates
ws://localhost:8888/api/v1/backtests/:run_id/live?access_token=<JWT>
ws://localhost:8888/ws/backtests/:run_id?access_token=<JWT>

// Bot Instance Updates
ws://localhost:8888/ws/bots/:instance_id?access_token=<JWT>

// Strategy Runtime Updates
ws://localhost:8888/ws/strategies?access_token=<JWT>
```

Message Types from WebSocket:

```json
// Backtest Progress
{
  "type": "PROGRESS",
  "progress_percent": 75,
  "trades_completed": 30,
  "trades_total": 40,
  "current_date": "2024-01-15"
}

// Bot Trade Executed
{
  "type": "TRADE_EXECUTED",
  "trade": { ... }
}

// Bot Position Opened
{
  "type": "POSITION_OPENED",
  "position": { ... }
}

// Bot Position Closed
{
  "type": "POSITION_CLOSED",
  "position": { ... }
}

// Bot Alert
{
  "type": "ALERT",
  "severity": "WARNING",
  "message": "..."
}
```

---

## 🔐 Authentication Flow

```
Frontend (React)
    ↓
POST /api/v1/auth/login (credentials)
    ↓
Backend (Go)
    ↓
Generates JWT Token
    ↓
Returns access_token + refresh_token
    ↓
Frontend stores in localStorage + Zustand
    ↓
All subsequent requests include Authorization: Bearer <token>
```

Token Refresh Flow:

```
Token expires (30 min)
    ↓
Frontend detects 401 response
    ↓
Calls POST /api/v1/auth/refresh with refresh_token
    ↓
Backend validates and issues new access_token
    ↓
Retry original request
    ↓
Success
```

---

## 📝 Database Sync

The backend maintains synchronization with bot API:

1. **Bot Instance Creation**
   - Frontend → Backend POST /bots
   - Backend → Bot API proxy
   - Backend stores in database
   - Frontend receives confirmation

2. **Real-Time Data**
   - Frontend → Backend GET /bots/:instance_id/positions/current
   - Backend → Bot API (no DB cache, always fresh)
   - Backend → Frontend

3. **Historical Data**
   - Frontend → Backend GET /bots/:instance_id/trades
   - Backend → Database (cached)
   - Backend → Frontend

4. **Backtest Results**
   - Frontend → Backend POST /backtests
   - Backend → Bot API (starts backtest)
   - Backend stores result in database
   - Frontend polls GET /backtests/:run_id/status
   - WebSocket sends live progress

---

## 🎯 Frontend API Client Usage

### Import and Initialize

```typescript
import { apiClient } from '@/api/client';

// Load saved auth from localStorage
apiClient.loadAuthFromStorage();

// Or set manually after login
apiClient.setAuth(accessToken, refreshToken);
```

### Common Operations

```typescript
// Login
await apiClient.login('user@example.com', 'password');

// List bots
const { data: bots } = await apiClient.listBotInstances();

// Get real-time stats
const stats = await apiClient.getRealtimeStats('bot-id');

// Get current positions
const positions = await apiClient.getCurrentPositions('bot-id');

// Create backtest
const backtest = await apiClient.createBacktest({...});

// Monitor backtest progress
const progress = await apiClient.getBacktestStatus('run-id');

// WebSocket for live updates
const ws = apiClient.connectBacktestProgress('run-id', (progress) => {
  console.log(`Progress: ${progress.progress_percent}%`);
});
```

---

## 🐛 Common Integration Issues

### Issue: 401 Unauthorized on first request

**Cause**: Token not loaded from localStorage  
**Solution**: Call `apiClient.loadAuthFromStorage()` on app initialization

### Issue: CORS errors

**Cause**: Backend CORS middleware not configured  
**Solution**: Frontend is on 5173, Backend on 8888 - ensure CORS allows both

### Issue: WebSocket connection fails

**Cause**: Token not included in WebSocket URL  
**Solution**: Pass `?access_token=<JWT>` in the backend websocket URL

### Issue: Cached data is stale

**Cause**: Default caching enabled  
**Solution**: Add cache-busting header: `Cache-Control: no-cache`

### Issue: Rate limit exceeded

**Cause**: Too many requests per minute  
**Solution**: Implement request queuing or increase time between calls

---

## 📚 Additional Resources

- See `BACKEND_API_INTEGRATION.md` for complete API reference
- See `REACT_COMPONENT_EXAMPLES.tsx` for component patterns
- See `frontend/src/api/client.ts` for full client implementation
- See `backend/internal/routes/bot_api_delegate_routes.go` for proxy implementation
