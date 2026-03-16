# API Integration Guide

How to communicate with the dYdX Trading Bot API.

## API Overview

**Base URL (Development):** `http://localhost:8889`

**Base URL (Production):** Set via `VITE_API_URL` environment variable

**API Version:** `/api/v1/`

**Full URL Pattern:** `{BASE_URL}/api/v1/{endpoint}`

---

## Authentication

### JWT Token Flow

1. **Login** → POST `/api/v1/auth/login` → Receive JWT token
2. **Store Token** → localStorage (automatic via Zustand persist)
3. **Attach Token** → Axios interceptor adds `Authorization: Bearer {token}` header
4. **Token Expires** → 401 response → Auto-logout + redirect to `/login`

### Login Endpoint

**Request:**

```
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (Success):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "user-123",
    "email": "user@example.com",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

**Response (Error):**

```json
{
  "detail": "Invalid credentials"
}
```

### Usage in Code

```typescript
// In src/store/auth.ts
const useAuthStore = create(
  persist((set) => ({
    async login(email: string, password: string) {
      const response = await api.login(email, password);
      // Token automatically stored in localStorage
      // Axios interceptor automatically adds it to requests
      set({ user: response.user });
    },
  }))
);

// In component
const { login } = useAuthStore();
await login('user@example.com', 'password123');
```

---

## Backtest Endpoints

### List Backtests

**Request:**

```
GET /api/v1/backtests
Authorization: Bearer {token}
```

**Response:**

```json
{
  "data": {
    "backtests": [
      {
        "run_id": "backtest-001",
        "parameters": {
          "start_date": "2024-01-01",
          "end_date": "2024-12-31",
          "num_pairs": 5,
          "zscore_threshold": 2.0,
          "stats_window": 20,
          "usd_per_trade": 1000
        },
        "status": "completed",
        "results": {
          "total_pnl": 5250.75,
          "total_pnl_usd": 5250.75,
          "return_percentage": 5.25,
          "trades": [
            {
              "pair": "BTC/USDC",
              "entry_price": 42500,
              "exit_price": 42750,
              "entry_time": "2024-01-15T10:30:00Z",
              "exit_time": "2024-01-15T11:45:00Z",
              "pnl": 250,
              "z_score": 2.1
            }
          ],
          "metrics": {
            "win_rate": 0.65,
            "avg_win": 350,
            "avg_loss": 200,
            "max_drawdown": 0.12,
            "sharpe_ratio": 1.45
          }
        },
        "created_at": "2024-01-01T08:00:00Z",
        "updated_at": "2024-01-01T16:00:00Z"
      }
    ]
  }
}
```

**Usage in Code:**

```typescript
const BacktestList = () => {
  const [backtests, setBacktests] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBacktests = async () => {
      try {
        const response = await api.listBacktests();
        // Backend returns { data: { backtests: [...] } }
        setBacktests(response.data.backtests);
      } catch (error) {
        console.error('❌ Failed to fetch backtests:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchBacktests();
  }, []);

  return (
    <div>
      {backtests.map((backtest) => (
        <BacktestCard key={backtest.run_id} backtest={backtest} />
      ))}
    </div>
  );
};
```

---

### Get Single Backtest

**Request:**

```
GET /api/v1/backtests/{run_id}
Authorization: Bearer {token}
```

**Response:**

```json
{
  "run_id": "backtest-001",
  "status": "completed",
  "results": {
    "total_pnl": 5250.75,
    "trades": [...],
    "metrics": {...}
  }
}
```

**Usage in Code:**

```typescript
const BacktestDetails = ({ runId }: { runId: string }) => {
  const [backtest, setBacktest] = useState(null);

  useEffect(() => {
    const fetchBacktest = async () => {
      const response = await api.getBacktest(runId);
      setBacktest(response);
    };

    fetchBacktest();
  }, [runId]);

  if (backtest.status === 'running') {
    return <BacktestProgress runId={runId} />;
  }

  return <BacktestResults backtest={backtest} />;
};
```

---

### Run Backtest

**Request:**

```
POST /api/v1/backtests/run
Authorization: Bearer {token}
Content-Type: application/json

{
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "num_pairs": 5,
  "zscore_threshold": 2.0,
  "stats_window": 20,
  "usd_per_trade": 1000
}
```

**Response (Immediate):**

```json
{
  "run_id": "backtest-002",
  "status": "running"
}
```

**Key Points:**

- Request returns immediately
- Backtest runs asynchronously in backend
- Use WebSocket to track progress (see next section)

**Usage in Code:**

```typescript
const BacktestRunner = () => {
  const handleRun = async (params: BacktestParams) => {
    try {
      const response = await api.runBacktest(params);
      // backtest starts in background
      console.log('📊 Backtest started:', response.run_id);

      // Navigate to details page to track progress
      navigate(`/backtest/${response.run_id}`);
    } catch (error) {
      setError(error.message);
    }
  };

  return <BacktestRunnerForm onSubmit={handleRun} />;
};
```

---

### Delete Backtest

**Request:**

```
DELETE /api/v1/backtests/{run_id}
Authorization: Bearer {token}
```

**Response:**

```json
{
  "success": true,
  "message": "Backtest deleted"
}
```

**Usage in Code:**

```typescript
const handleDelete = async (runId: string) => {
  if (confirm('Delete backtest?')) {
    await api.deleteBacktest(runId);
    // Refresh list
    refreshBacktestList();
  }
};
```

---

## WebSocket Connection

### Real-time Backtest Progress

**Endpoint:** `/ws/backtest/{run_id}`

**Query Parameters:**

- `token` (required) - JWT token for authentication

**Full URL:**

```
ws://localhost:8889/ws/backtest/backtest-002?token=eyJhbGci...
```

### Connection Flow

```typescript
// In useBacktestProgress hook
const connectToBacktest = (runId: string, token: string) => {
  const ws = new WebSocket(
    `ws://localhost:8889/ws/backtest/${runId}?token=${token}`
  );

  ws.onopen = () => {
    console.log('🔌 Connected to backtest progress');
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Handle progress update
    updateProgress(data);
  };

  ws.onerror = (error) => {
    console.error('❌ WebSocket error:', error);
    // Attempt reconnection
  };

  ws.onclose = () => {
    console.log('🔌 Disconnected from backtest progress');
  };

  return ws;
};
```

### Message Format

**Progress Update:**

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
      "entry_price": 42500,
      "exit_price": 42750,
      "pnl": 250,
      "z_score": 2.1
    }
  }
}
```

**Completion Update:**

```json
{
  "progress": 100,
  "status": "completed",
  "message": "Backtest completed successfully",
  "details": {
    "total_trades": 150,
    "total_pnl": 5250.75,
    "return_percentage": 5.25
  }
}
```

**Error Update:**

```json
{
  "progress": 0,
  "status": "failed",
  "message": "Insufficient data for trading pairs",
  "error": "ValueError: Not enough historical data"
}
```

### Usage in Component

```typescript
const BacktestProgress = ({ runId }: { runId: string }) => {
  const { progress, status, message, error, isConnected } =
    useBacktestProgress(runId);

  return (
    <div>
      <div
        className={`indicator ${isConnected ? 'connected' : 'disconnected'}`}
      >
        {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
      </div>

      <ProgressBar value={progress} max={100} />
      <p>{message}</p>

      {error && <ErrorBox>{error}</ErrorBox>}

      {status === 'completed' && (
        <SuccessBox>Backtest completed! 🎉</SuccessBox>
      )}
    </div>
  );
};
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning      | Action                         |
| ---- | ------------ | ------------------------------ |
| 200  | OK           | Process response               |
| 201  | Created      | Process response               |
| 400  | Bad Request  | Show user error message        |
| 401  | Unauthorized | Clear token, redirect to login |
| 403  | Forbidden    | Show "Access Denied"           |
| 404  | Not Found    | Show "Not found"               |
| 500  | Server Error | Show "Server error, try again" |

### Error Response Format

**Error Response:**

```json
{
  "detail": "Invalid input parameters",
  "errors": [
    {
      "field": "start_date",
      "message": "Date must be in YYYY-MM-DD format"
    },
    {
      "field": "num_pairs",
      "message": "Must be between 1 and 100"
    }
  ]
}
```

### Error Handling Pattern

```typescript
const handleRequest = async () => {
  try {
    const response = await api.someMethod();
    setData(response);
  } catch (error) {
    let errorMessage = 'An error occurred';

    if (error.response?.status === 401) {
      // Token expired
      console.log('🔐 Token expired');
      logout();
      navigate('/login');
    } else if (error.response?.data?.detail) {
      errorMessage = error.response.data.detail;
    } else if (error.response?.data?.errors) {
      // Multiple field errors
      errorMessage = error.response.data.errors
        .map((e) => `${e.field}: ${e.message}`)
        .join(', ');
    } else if (error.message) {
      errorMessage = error.message;
    }

    console.error('❌ Request failed:', errorMessage);
    setError(errorMessage);
  }
};
```

---

## API Client Implementation

### Axios Configuration

**File:** `src/api.ts`

```typescript
import axios from 'axios';
import { useAuthStore } from './store/auth';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8889',
  timeout: 30000,
});

// Request interceptor - add JWT token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth-store');
    if (token) {
      const authState = JSON.parse(token).state;
      if (authState.token) {
        config.headers.Authorization = `Bearer ${authState.token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle 401
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear auth store
      const store = useAuthStore();
      store.logout();
      // Redirect handled by ProtectedRoute
    }
    return Promise.reject(error);
  }
);

export const api = {
  login: (email: string, password: string) =>
    apiClient.post('/api/v1/auth/login', { email, password }),

  listBacktests: () =>
    apiClient.get('/api/v1/backtests'),

  getBacktest: (runId: string) =>
    apiClient.get(`/api/v1/backtests/${runId}`),

  runBacktest: (params: BacktestParams) =>
    apiClient.post('/api/v1/backtests/run', params),

  deleteBacktest: (runId: string) =>
    apiClient.delete(`/api/v1/backtests/${runId}`),
};
```

---

## Environment Variables

### Development (.env.local)

```bash
VITE_API_URL=http://localhost:8889
```

### Production (.env.production)

```bash
VITE_API_URL=https://api.your-domain.com
```

### Usage in Code

```typescript
const baseUrl = import.meta.env.VITE_API_URL;
console.log('📊 API Base URL:', baseUrl);
```

---

## Common Patterns

### Fetching Data with Loading State

```typescript
const Component = ({ id }: { id: string }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.getData(id);
        setData(response);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!data) return <EmptyState />;

  return <DataDisplay data={data} />;
};
```

### Polling for Updates

```typescript
useEffect(() => {
  const interval = setInterval(async () => {
    try {
      const response = await api.getBacktest(runId);
      setBacktest(response);

      if (response.status === 'completed' || response.status === 'failed') {
        clearInterval(interval); // Stop polling
      }
    } catch (error) {
      console.error('❌ Poll failed:', error);
    }
  }, 5000); // Poll every 5 seconds

  return () => clearInterval(interval);
}, [runId]);
```

### Refetching Data

```typescript
const [refetch, setRefetch] = useState(0);

const handleRefresh = () => {
  setRefetch((prev) => prev + 1);
};

useEffect(() => {
  // Runs when refetch changes
  fetchData();
}, [refetch]);

return <button onClick={handleRefresh}>Refresh</button>;
```

---

## Testing API Calls

### Manual Testing with cURL

```bash
# Login
curl -X POST http://localhost:8889/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'

# List backtests
curl -X GET http://localhost:8889/api/v1/backtests \
  -H "Authorization: Bearer {token}"

# Run backtest
curl -X POST http://localhost:8889/api/v1/backtests/run \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "num_pairs": 5,
    "zscore_threshold": 2.0,
    "stats_window": 20,
    "usd_per_trade": 1000
  }'
```

### Testing in Browser DevTools

```javascript
// Open browser console and test API calls

// Get auth token
const authStore = JSON.parse(localStorage.getItem('auth-store'));
const token = authStore.state.token;

// Make test request
fetch('http://localhost:8889/api/v1/backtests', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
}).then(r => r.json()).then(console.log);
```

---

## Troubleshooting

### 401 Unauthorized

**Problem:** All API calls return 401

**Solutions:**

1. Check token exists: `console.log(localStorage.getItem('auth-store'))`
2. Login again to get new token
3. Check token hasn't expired
4. Verify backend accepting tokens

### CORS Errors

**Problem:** Request blocked by CORS

**Solution:** Verify `VITE_API_URL` matches backend URL

- Development: `http://localhost:8889`
- Production: Your production backend URL

### WebSocket Connection Fails

**Problem:** WebSocket connection refused

**Solutions:**

1. Check API is running: `curl http://localhost:8889`
2. Check token is valid
3. Check run_id exists
4. Check WebSocket endpoint is implemented

### Connection Timeouts

**Problem:** API calls timeout

**Solutions:**

1. Check backend is running
2. Increase timeout in axios config: `timeout: 60000`
3. Check network connection
4. Check backend isn't overloaded

---

## See Also

- [README.md](README.md) - Architecture overview
- [DATA_FLOW.md](DATA_FLOW.md) - Component interactions
- [PATTERNS.md](PATTERNS.md) - Code patterns
