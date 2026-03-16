# Data Flow Documentation

How data moves through the dYdX Trading Bot Frontend.

## Component Interaction Diagram

### High-Level View

```
User Interactions
      │
      ▼
┌─────────────────────────────────┐
│      Pages (Route Views)        │
│  ┌─────────────────────────────┐│
│  │ Dashboard / Details / Login ││
│  └──────┬──────────────────────┘│
└─────────┼─────────────────────────┘
          │
          ├──────────────────────────────┐
          │                              │
          ▼                              ▼
┌──────────────────────────┐   ┌────────────────────────┐
│   Reusable Components    │   │   Zustand Stores       │
│  ┌────────────────────┐ │   │  ┌────────────────────┐│
│  │ BacktestRunner    ││   │  │ auth.ts             ││
│  │ BacktestList      ││   │  │ (user, token, etc)  ││
│  │ BacktestProgress  ││   │  └────────────────────┘│
│  └────────┬───────────┘│   └──────────┬─────────────┘
└───────────┼─────────────┘             │
            │                           │
            └───────────────────────────┘
                      │
                      ▼
           ┌────────────────────┐
           │   API Client       │
           │   (Axios)          │
           │ (JWT interceptor)  │
           └────────┬───────────┘
                    │
         ┌──────────┼──────────┐
         │          │          │
         ▼          ▼          ▼
      HTTP      WebSocket    localStorage
       to          to          (tokens)
    Backend     Backend
```

## Page-Level Data Flows

### Login Flow

**File:** `src/pages/Login.tsx`

```
User fills login form
       │
       ├─ Email input
       ├─ Password input
       │
       ▼ (User clicks "Sign In")
handleSubmit()
       │
       ├─ Validate email format
       ├─ Validate password not empty
       │
       ├─ Call useAuthStore.login(email, password)
       │
       └─ auth.ts login() method:
              │
              ├─ api.login(email, password)
              │       │
              │       └─ POST /api/v1/auth/login
              │              │
              │              ├─ Request body:
              │              │  { email, password }
              │              │
              │              ├─ Response:
              │              │  { access_token, token_type }
              │              │
              │              └─ Store token in Axios headers
              │
              ├─ Update Zustand: user = response.user
              ├─ Save token to localStorage
              │
              └─ Navigate to /dashboard

If error:
       └─ Display error message to user
       └─ Stay on login page
```

**Components Involved:**

- Form validation
- API error handling
- Auth store persistence

---

### Dashboard Flow

**File:** `src/pages/Dashboard.tsx`

```
Page mounts
       │
       ├─ Check auth with useAuthStore.isAuthenticated()
       │  (If false → redirect to /login)
       │
       ├─ State setup:
       │  - backtests = []
       │  - loading = true
       │  - error = null
       │
       └─ useEffect (on mount):
              │
              ├─ Call api.listBacktests()
              │       │
              │       └─ GET /api/v1/backtests
              │              │
              │              ├─ Response:
              │              │  { data: { backtests: [...] } }
              │              │
              │              └─ Extract backtests array
              │
              ├─ Set state:
              │  - backtests = response
              │  - loading = false
              │
              └─ Render UI

Components visible:
       │
       ├─ BacktestRunner (child component)
       │       │
       │       └─ Emits onBacktestStarted event
       │              │
       │              └─ Triggers refresh of backtest list
       │
       └─ BacktestList (child component)
              │
              ├─ Receives backtests prop
              ├─ Displays table/cards
              │
              └─ On click row → navigate to /backtest/{id}
```

**Key State:**

```typescript
const [backtests, setBacktests] = useState<BacktestRun[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
```

**API Calls:**

- `GET /api/v1/backtests` (on mount)
- Called again when BacktestRunner completes

---

### Backtest Details Flow

**File:** `src/pages/BacktestDetails.tsx`

```
Page mounts with params: { id }
       │
       ├─ Check auth
       │
       └─ Extract run_id from URL params
              │
              ├─ useEffect (on mount):
              │       │
              │       └─ Fetch backtest details:
              │              │
              │              └─ api.getBacktest(run_id)
              │                     │
              │                     └─ GET /api/v1/backtests/{run_id}
              │                            │
              │                            └─ Response: BacktestRun object
              │                                   │
              │                                   ├─ status
              │                                   ├─ results
              │                                   │  ├─ P&L
              │                                   │  ├─ trades
              │                                   │  └─ metrics
              │                                   │
              │                                   └─ Set state.backtest
              │
              └─ If status === 'running':
                     │
                     └─ Initialize WebSocket connection:
                            │
                            └─ useBacktestProgress(run_id)
                                   │
                                   ├─ Connect to:
                                   │  /ws/backtest/{run_id}?token={jwt}
                                   │
                                   └─ Listen for messages:
                                          │
                                          ├─ progress (0-100%)
                                          ├─ status (running/completed/failed)
                                          ├─ message (friendly text)
                                          └─ details (trade-by-trade updates)
                                                 │
                                                 └─ Update UI in real-time

Page renders:
       │
       ├─ Header: Backtest info
       │
       ├─ Progress indicator (if running)
       │  ├─ Progress bar from WebSocket
       │  └─ Current trade count
       │
       ├─ Charts:
       │  ├─ Equity curve (cumulative P&L)
       │  ├─ P&L by pair (bar chart)
       │  └─ Trade visualization
       │
       └─ Trade table:
          ├─ Columns: Pair, Entry, Exit, P&L, Status
          └─ Sorted by trade time
```

**Real-time Updates:**

```
WebSocket message received
       │
       └─ parseMessage() in useBacktestProgress
              │
              ├─ Extract: progress, status, message, details
              │
              └─ Update React state
                     │
                     ├─ BacktestProgress component re-renders
                     ├─ Charts update with new trade data
                     └─ Trade table appends new rows
```

---

## Component Data Flows

### BacktestRunner Component

**File:** `src/components/BacktestRunner.tsx`

```
User fills form:
├─ Start date picker
├─ End date picker
├─ Number of pairs (slider)
├─ Z-score threshold (input)
├─ Stats window (input)
├─ USD per trade (input)

User clicks "Run Backtest"
       │
       ▼
handleRun()
       │
       ├─ Validate all fields
       │
       ├─ Build request object:
       │  {
       │    start_date: "YYYY-MM-DD",
       │    end_date: "YYYY-MM-DD",
       │    num_pairs: number,
       │    zscore_threshold: number,
       │    stats_window: number,
       │    usd_per_trade: number
       │  }
       │
       ├─ api.runBacktest(request)
       │       │
       │       └─ POST /api/v1/backtests/run
       │              │
       │              └─ Response: { run_id, status }
       │                     │
       │                     └─ Returns immediately (backtest runs async)
       │
       ├─ Set UI state:
       │  - isLoading = false
       │  - Show success message
       │  - Clear form
       │
       └─ Emit onBacktestStarted event
              │
              └─ Parent receives event
                     │
                     └─ Dashboard refreshes backtest list
                            │
                            ├─ Shows new backtest in list
                            └─ (or navigate to new backtest details)
```

**Form Validation:**

```
├─ Start date < End date
├─ Date range: minimum 30 days (configurable)
├─ num_pairs: 1-100
├─ zscore_threshold: 0-10
├─ stats_window: 5-500
└─ usd_per_trade: > 0
```

---

### BacktestList Component

**File:** `src/components/BacktestList.tsx`

```
Component receives backtests prop (array)
       │
       ├─ If empty:
       │  └─ Show "No backtests yet" message
       │
       ├─ If loading:
       │  └─ Show loading spinner
       │
       ├─ If error:
       │  └─ Show error message
       │
       └─ Render backtest table/cards:
              │
              ├─ Columns:
              │  ├─ Name/ID
              │  ├─ Date range
              │  ├─ Status (badge: completed/running/failed)
              │  ├─ P&L (green if >, red if <)
              │  ├─ Return % (green/red)
              │  └─ Actions (View, Delete)
              │
              └─ User interactions:
                     │
                     ├─ Click row → navigate to /backtest/{id}
                     │       │
                     │       └─ Route params: { id: run_id }
                     │
                     └─ Click delete → api.deleteBacktest(id)
                            │
                            └─ DELETE /api/v1/backtests/{id}
                                   │
                                   └─ Refresh list
```

**Data Structure (BacktestRun):**

```typescript
{
  run_id: string;
  parameters: {
    start_date: string;
    end_date: string;
    num_pairs: number;
    zscore_threshold: number;
    stats_window: number;
    usd_per_trade: number;
  };
  status: "completed" | "running" | "failed";
  results?: {
    total_pnl: number;
    total_pnl_usd: number;
    return_percentage: number;
    trades: Trade[];
    metrics: {
      win_rate: number;
      avg_win: number;
      avg_loss: number;
      // ... other metrics
    };
  };
  created_at: string;
  updated_at: string;
}
```

---

### BacktestProgress Component

**File:** `src/components/BacktestProgress.tsx`

```
Component receives run_id prop
       │
       └─ useBacktestProgress(run_id) hook called
              │
              ├─ Initializes WebSocket
              │
              └─ Returns state:
                     {
                       progress: 0-100,
                       status: "running" | "completed" | "failed",
                       message: "Processing trade 45 of 150...",
                       details: { current_trade, total_trades },
                       error: null | string,
                       isConnected: boolean
                     }

Component renders:
       │
       ├─ Connection status indicator
       │  └─ Green dot if connected, red if disconnected
       │
       ├─ Progress bar: {progress}%
       │
       ├─ Status message: {message}
       │  └─ e.g., "Processing trade 45 of 150..."
       │
       ├─ Details:
       │  └─ "Z-score: 2.1 | P&L: +$1,250"
       │
       └─ Error display (if any):
          └─ "Connection lost. Reconnecting..."
```

---

## Zustand Store Data Flow

### Auth Store

**File:** `src/store/auth.ts`

```typescript
const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      // State
      user: null,
      loading: false,
      error: null,

      // Methods
      login: async (email, password) => {
        // 1. Set loading state
        set({ loading: true, error: null });

        try {
          // 2. Call API
          const response = await api.login(email, password);

          // 3. Update store
          set({
            user: response.user,
            loading: false,
            error: null
          });
        } catch (error) {
          // 4. Set error
          set({
            loading: false,
            error: error.message
          });
        }
      },

      logout: () => {
        set({ user: null });
        // Token removed from Axios headers
      }
    }),
    { name: 'auth-store' } // localStorage key
  )
);
```

**Persistence:**

```
On app load:
┌──────────────────────────────────────┐
│ Check localStorage for 'auth-store'  │
├──────────────────────────────────────┤
│ If found:                            │
│ - Restore user state                 │
│ - Restore token                      │
│ - Inject into Axios headers          │
│ - User stays logged in               │
│                                      │
│ If not found:                        │
│ - user = null                        │
│ - User redirected to /login          │
└──────────────────────────────────────┘
```

---

## WebSocket Connection Flow

### useBacktestProgress Hook

**File:** `src/hooks/useBacktestProgress.ts`

```
Hook called with run_id
       │
       ├─ Retrieve token from localStorage
       │
       └─ useEffect on mount:
              │
              ├─ Create WebSocket:
              │  const ws = new WebSocket(
              │    `ws://localhost:8889/ws/backtest/${runId}?token=${token}`
              │  )
              │
              ├─ ws.onopen:
              │  └─ console.log("🔌 Connected")
              │  └─ setIsConnected(true)
              │
              ├─ ws.onmessage:
              │  │
              │  └─ const data = JSON.parse(event.data)
              │     │
              │     ├─ progress: number (0-100)
              │     ├─ status: string
              │     ├─ message: string
              │     └─ details: object
              │     │
              │     └─ setState({ progress, status, message, details })
              │
              ├─ ws.onerror:
              │  └─ setState({ error, isConnected: false })
              │  └─ Attempt reconnect with exponential backoff
              │
              └─ Cleanup on unmount:
                 └─ ws.close()

Return state to component:
       │
       └─ { progress, status, message, details, error, isConnected }
```

**Message Format:**

```json
{
  "progress": 45,
  "status": "running",
  "message": "Processing trade 45 of 150",
  "details": {
    "current_trade": 45,
    "total_trades": 150,
    "last_trade": {
      "pair": "BTC/USDC",
      "entry": 42500,
      "exit": 42750,
      "pnl": 250,
      "z_score": 2.1
    }
  }
}
```

---

## API Client Request/Response Flow

### Request Lifecycle

**File:** `src/api.ts`

```
Component calls api.getBacktest(runId)
       │
       ├─ Axios GET request:
       │  GET http://localhost:8889/api/v1/backtests/{runId}
       │
       ├─ Request interceptor runs:
       │  ├─ Retrieve token from localStorage
       │  ├─ Add header: Authorization: Bearer {token}
       │  └─ Pass request to backend
       │
       ├─ Backend processes request
       │  └─ Returns response
       │
       ├─ Response interceptor runs:
       │  ├─ If status 401:
       │  │  └─ logout() + redirect to /login
       │  │
       │  └─ If status 2xx:
       │     └─ Return response.data
       │
       └─ Component receives data:
              │
              └─ setState({ backtest: data, loading: false })
```

### Error Handling

```
Request fails
       │
       ├─ If no response:
       │  └─ Network error → error.message
       │
       ├─ If 401:
       │  └─ Unauthorized → logout + redirect to /login
       │
       ├─ If 4xx:
       │  └─ Client error → extract error.response.data.message
       │
       ├─ If 5xx:
       │  └─ Server error → "Server error. Try again later"
       │
       └─ Component shows error UI
```

---

## State Persistence

### localStorage Structure

```
localStorage
├─ key: 'auth-store'
│  └─ value: {
│       "state": {
│         "user": { id, email, ... },
│         "token": "jwt-token-here",
│         "loading": false,
│         "error": null
│       },
│       "version": 0
│     }
│
└─ (other stores as needed)
```

**Restore on App Load:**

```
App.tsx mounts
       │
       └─ Zustand persist middleware runs:
              │
              ├─ Check localStorage for 'auth-store'
              ├─ If found: restore state
              ├─ If not: use default state
              │
              └─ App ready to render
```

---

## Data Validation

### Client-Side Validation

```
Form submission → validate input
├─ Email: valid email format (regex)
├─ Password: not empty
├─ Backtest dates: start < end
├─ Numbers: within acceptable ranges
└─ Show error to user if invalid

Valid input → API call
```

### Server-Side Validation

```
API receives request
├─ Re-validate all inputs
├─ Check permissions
├─ Verify user ownership
└─ Database constraints

Invalid → return 400 with message
Valid → process request
```

---

## Performance Optimizations

### Memoization

- Components wrapped with `React.memo()` to prevent unnecessary re-renders
- `useMemo()` for expensive calculations
- `useCallback()` for event handlers passed to children

### Code Splitting

- React Router auto-splits pages
- Each page lazy-loaded on first visit

### Caching

- Backtest list cached in component state (not refetched unless triggered)
- Individual backtest cached after fetch

---

## See Also

- [README.md](README.md) - Architecture overview
- [PATTERNS.md](PATTERNS.md) - Code patterns
- [API_INTEGRATION.md](API_INTEGRATION.md) - API details
