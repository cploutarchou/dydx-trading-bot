# Console Logs During BacktestDetails Flow

This document shows the expected console output when navigating to a backtest details page.

## Browser Console Logs (Frontend)

```
// 1. Component mounted
🔧 App.tsx: Component mounted, setting mounted=true
🔧 App.tsx: Rendering router

// 2. Navigation to backtest details page
// (Router detects /backtest/{runId} route)

// 3. BacktestDetailsPage component mounts
// useEffect triggers API call

🔌 api.ts: getCurrentUser() succeeded

// 4. API request sent
// (Axios interceptor adds Authorization header with JWT token)

// Network Request:
GET http://localhost:8000/api/v1/backtests/{run_id}
Headers:
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  Content-Type: application/json

// 5. API response received (~200-300ms)
XHR finished loading: GET "http://localhost:8000/api/v1/backtests/{run_id}"

// 6. Component receives data
// State updated with backtest data
// Data transformations triggered:
//   - generateEquityCurveData() called
//   - generatePnlByPairData() called
//   - generateTradeScatterData() called (for first pair)

// 7. Charts render
// (Recharts renders LineChart, BarChart, ScatterChart)
// No console output (silent rendering)

// 8. Component fully rendered
// All metrics displayed
// Table shows all trades for first selected pair
```

## Backend Console Logs (Python)

```
# 1. Request received
INFO: "GET /api/v1/backtests/{run_id} HTTP/1.1" 200 OK

# 2. Authentication check
# get_current_user() dependency validates JWT token

# 3. Database query
# BacktestRunService.get_run_by_run_id(db, run_id)
#   └─ Query: SELECT * FROM backtest_runs WHERE run_id = '{run_id}'
#   └─ Result: 1 row

# 4. Authorization check
# Verify current_user["user_id"] == run.user_id
#   └─ Result: Authorized ✓

# 5. Get pair results
# Query: SELECT * FROM backtest_results WHERE run_id_fk = {run.id}
#   └─ Result: 5-20 rows (one per pair)

# 6. Get trades for each result
# For each backtest_result:
#   Query: SELECT * FROM trade_logs WHERE result_id_fk = {result.id}
#   └─ Result: 10-50 rows per pair

# 7. Format response
# Build JSON response with all data
#   - BacktestRun metrics
#   - BacktestResult array (with formatted trades)
#   - Flattened all_trades array

# 8. Send response (typically ~50-100KB)
# Response time: 50-100ms (after initial query)

# Example response size:
# - Base metrics: ~1KB
# - 10 pairs × 5KB per pair: ~50KB
# - 100 total trades: ~10KB
# Total: ~61KB
```

## Network Timeline

```
┌─────────────────────────────────────────────────────────┐
│ BacktestDetailsPage Component Mounts                    │
│ (useEffect hook triggered)                              │
└───────────────┬─────────────────────────────────────────┘
                │
                ├─ [0ms] useEffect hook runs
                │
                ├─ [0-5ms] api.getBacktest() called
                │
                ├─ [5-10ms] Axios request created
                │         (interceptor adds JWT token)
                │
                ├─ [10-50ms] HTTP request over network
                │
                ├─ [50ms] Request arrives at backend
                │
                ├─ [50-70ms] Backend authentication
                │
                ├─ [70-150ms] Database queries
                │         (BacktestRun + BacktestResults + TradeLogs)
                │
                ├─ [150-200ms] Response formatting
                │         (JSON serialization)
                │
                ├─ [200-230ms] HTTP response sent
                │
                ├─ [230-250ms] Response received by browser
                │
                ├─ [250-260ms] Response parsed by Axios
                │
                ├─ [260-270ms] setBacktest() state update
                │
                ├─ [270-280ms] generateEquityCurveData() transformation
                ├─         generatePnlByPairData() transformation
                ├─         generateTradeScatterData() transformation
                │
                ├─ [280-350ms] React re-render triggered
                │
                ├─ [350-400ms] Recharts rendering
                │         (LineChart, BarChart, ScatterChart)
                │
                └─ [400-500ms] ✓ Component fully rendered

Total time: ~400-500ms typical
```

## State Transitions

```typescript
// Initial state
{
  backtest: null,
  loading: true,
  error: null,
  selectedResult: null
}

// After API call starts
{
  backtest: null,
  loading: true,
  error: null,
  selectedResult: null
}

// After API response received
{
  backtest: {
    id: 1,
    run_id: "abc-123...",
    status: "completed",
    total_trades: 45,
    total_pnl_usd: 1234.56,
    // ... all backtest data
  },
  loading: false,
  error: null,
  selectedResult: { market_1: "BTC-USD", market_2: "ETH-USD", trades: [...] }
}

// After user clicks different pair button
{
  backtest: { /* same as above */ },
  loading: false,
  error: null,
  selectedResult: { market_1: "ETH-USD", market_2: "SOL-USD", trades: [...] }
}
```

## React Render Cycles

### First Render (Loading State)

```
BacktestDetailsPage
├─ Condition: loading === true
├─ Render: <Loader /> spinner
└─ Output: Centered spinning icon
```

### Second Render (After Data Loaded)

```
BacktestDetailsPage
├─ Condition: backtest !== null
├─ Render Structure:
│  ├─ Header section
│  ├─ Top metrics grid (4 cards)
│  ├─ Charts section (2 columns)
│  │  ├─ EquityCurveChart (LineChart)
│  │  └─ PnlByPairChart (BarChart)
│  ├─ Risk metrics grid (4 cards)
│  ├─ Pair selection buttons
│  ├─ TradePerformanceChart (ScatterChart)
│  └─ TradeBreakdownTable
└─ Output: Full page with all visualizations
```

### Third Render (After Pair Selection)

```
BacktestDetailsPage
├─ Condition: selectedResult changed
├─ Update: TradeScatterData recalculated
├─ Render: ScatterChart and Table only re-render
├─ Components NOT re-rendering: Header, metrics, top charts
└─ Performance: ~50-100ms (only partial re-render)
```

## Error Handling Flow

### Scenario 1: Unauthorized User (403 Forbidden)

```
Response Status: 403
Response Body: { "detail": "Not authorized" }

Frontend Handling:
├─ api.getBacktest() throws error
├─ catch block in useEffect
├─ setError("Not authorized")
├─ Render: <div className="text-red-600">Not authorized</div>
└─ Console: No visible error (handled gracefully)
```

### Scenario 2: Token Expired (401 Unauthorized)

```
Response Status: 401
Response Body: { "detail": "Invalid token" }

Frontend Handling:
├─ Response interceptor detects 401
├─ localStorage.removeItem('access_token')
├─ window.location.href = '/login'
├─ Browser redirects to login page
└─ User must re-authenticate
```

### Scenario 3: Backtest Not Found (404 Not Found)

```
Response Status: 404
Response Body: { "detail": "Backtest not found" }

Frontend Handling:
├─ api.getBacktest() throws error
├─ catch block catches error
├─ setError("Failed to fetch backtest")
├─ Render: <div className="text-red-600">Backtest not found</div>
└─ Console: Error visible in catch block
```

## Performance Monitoring

### Network Tab (Chrome DevTools)

```
Request:   GET /api/v1/backtests/{run_id}
Status:    200 OK
Type:      fetch (XMLHttpRequest)
Size:      61 KB (transferred)
Time:      285ms (duration)

Breakdown:
  Queued:       3ms
  DNS Lookup:   0ms (localhost)
  Initial conn: 0ms
  SSL:          0ms
  Request:      2ms
  Waiting:      250ms ← Backend processing time
  Download:     30ms ← Response transfer time
```

### React DevTools Profiler

```
Component:      BacktestDetailsPage
Render cause:   State update (backtest)
Render time:    ~45ms (total component)
  - Header:     ~2ms
  - Metrics:    ~3ms
  - Charts:     ~25ms ← Most expensive
  - Table:      ~10ms
  - UI:         ~5ms

Memoization opportunities:
  - Charts could use React.memo to avoid re-renders
  - Table rows could be virtualized for 1000+ trades
```

## Browser Storage

### LocalStorage After Login

```
Key: access_token
Value: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwibmFtZSI6ImFkbWluIiwiaWF0IjoxNzI5MTcyMjU5LCJleHAiOjE3MjkxNzQwNTl9.ivrui7PmW-wJkM17h9uamFFqHjNBLLfmLp68noJZfvk

Key: refresh_token
Value: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwibmFtZSI6ImFkbWluIiwiaWF0IjoxNzI5MTcyMjU5LCJleHAiOjE3MjkyNTg2NTl9.voDK59l-sMvmcmSpySxxJSfHYnZXBFmBOMxWx9NHpSw

// Used in Authorization header for all API requests:
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Summary

**Typical Success Flow** (100% happy path):

1. ✅ Login page → admin/admin123
2. ✅ Dashboard displays
3. ✅ Click "View Details" on backtest
4. ✅ Router navigates to `/backtest/{runId}`
5. ✅ Component mounts, fetches data
6. ✅ Charts and table render
7. ✅ User can interact (click pair buttons)
8. ✅ No console errors

**Total Time**: 400-500ms from click to fully rendered

**No manual intervention needed** - all errors handled gracefully with user-friendly messages.
