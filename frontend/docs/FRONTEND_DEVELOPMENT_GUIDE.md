# Frontend Development Complete Guide

## 🎯 Overview

This is your complete guide for building React components that interact with the dYdX Trading Bot backend. The backend provides a complete proxy to the Python bot API with additional database persistence, authentication, and rate limiting.

---

## 🏗️ Architecture

```
┌─────────────────────┐
│  React Frontend     │  Port: 5173
│  (Dashboard, UI)    │
└──────────┬──────────┘
           │
           │ HTTP/WebSocket
           │ Bearer JWT Token
           │
┌──────────▼──────────┐
│   Go Backend API    │  Port: 8888
│  - Authentication   │
│  - Proxy Layer      │
│  - Database Sync    │
│  - Rate Limiting    │
└──────────┬──────────┘
           │
           │ HTTP
           │ No Auth (Internal)
           │
┌──────────▼──────────┐
│  Python Bot API     │  Port: 8000
│  - Trading Logic    │
│  - Position Mgmt    │
│  - Backtest Engine  │
└─────────────────────┘
```

### Data Flow Example: Creating a Bot

```
1. User clicks "Create Bot" button
   ↓
2. Frontend calls: apiClient.createBotInstance({...})
   ↓
3. POST /api/v1/bots (with Bearer token)
   ↓
4. Backend verifies JWT token
   ↓
5. Backend stores bot config in database
   ↓
6. Backend proxies request to Bot API
   ↓
7. Bot API creates bot instance
   ↓
8. Backend returns confirmation to Frontend
   ↓
9. Frontend updates UI with new bot
```

---

## 📦 Getting Started

### 1. Set Up API Client

Create `frontend/src/api/index.ts`:

```typescript
import { DydxBotAPIClient } from './client';

// Initialize the API client
export const apiClient = new DydxBotAPIClient('http://localhost:8888');

// Load saved auth on app startup
export const initializeAuth = async () => {
  if (apiClient.loadAuthFromStorage()) {
    try {
      // Verify token is still valid
      await apiClient.getCurrentUser();
      return true;
    } catch {
      // Token invalid, clear auth
      return false;
    }
  }
  return false;
};
```

### 2. Set Up Auth Store (Zustand)

Create `frontend/src/store/auth.ts`:

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient, User } from '@/api/client';

interface AuthStore {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      loading: false,
      isAuthenticated: false,

      login: (user: User) => {
        set({ user, isAuthenticated: true });
      },

      logout: () => {
        apiClient.loadAuthFromStorage = () => false;
        set({ user: null, isAuthenticated: false });
      },
    }),
    {
      name: 'auth-store',
    }
  )
);
```

### 3. Create Protected Route Wrapper

Create `frontend/src/components/ProtectedRoute.tsx`:

```typescript
import { ReactNode } from 'react';
import { useAuthStore } from '@/store/auth';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  return <>{children}</>;
}
```

### 4. Initialize on App Start

Create `frontend/src/App.tsx`:

```typescript
import { useEffect, useState } from 'react';
import { initializeAuth } from '@/api';
import { useAuthStore } from '@/store/auth';

export function App() {
  const [initialized, setInitialized] = useState(false);
  const login = useAuthStore((state) => state.login);

  useEffect(() => {
    const init = async () => {
      const isValid = await initializeAuth();
      if (isValid) {
        const user = await apiClient.getCurrentUser();
        login(user);
      }
      setInitialized(true);
    };

    init();
  }, [login]);

  if (!initialized) {
    return <div>Loading...</div>;
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        {/* ... more routes */}
      </Routes>
    </Router>
  );
}
```

---

## 📋 Common Component Patterns

### Pattern 1: Simple Data Fetch

```typescript
import { useEffect, useState } from 'react';
import { apiClient, BotInstance } from '@/api/client';

export function BotList() {
  const [bots, setBots] = useState<BotInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchBots = async () => {
      try {
        const result = await apiClient.listBotInstances();
        setBots(result.data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchBots();
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      {bots.map((bot) => (
        <div key={bot.instance_id}>
          <h3>{bot.name}</h3>
          <p>Status: {bot.status}</p>
        </div>
      ))}
    </div>
  );
}
```

### Pattern 2: Real-Time Updates with WebSocket

```typescript
import { useEffect, useState } from 'react';
import { apiClient } from '@/api/client';

export function BotLiveStats({ instanceId }: { instanceId: string }) {
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let isMounted = true;

    const connect = async () => {
      // Initial data fetch
      const initialStats = await apiClient.getRealtimeStats(instanceId);
      if (isMounted) setStats(initialStats);

      // WebSocket for real-time updates
      ws = apiClient.connectBotUpdates(instanceId, (update) => {
        if (!isMounted) return;

        if (update.type === 'STATS_UPDATE') {
          setStats((prev) => ({ ...prev, ...update.stats }));
        }
      });
    };

    connect();

    return () => {
      isMounted = false;
      if (ws) ws.close();
    };
  }, [instanceId]);

  return (
    <div>
      {stats && (
        <>
          <p>P&L: ${stats.total_pnl.toFixed(2)}</p>
          <p>Win Rate: {(stats.win_rate * 100).toFixed(1)}%</p>
          <p>Open Positions: {stats.open_positions}</p>
        </>
      )}
    </div>
  );
}
```

### Pattern 3: Form Submission

```typescript
import { useState } from 'react';
import { apiClient } from '@/api/client';

export function CreateBotForm() {
  const [formData, setFormData] = useState({
    instance_id: '',
    name: '',
    address: '',
    mnemonic: '',
    zscore_threshold: 1.5,
    usd_per_trade: 100,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const bot = await apiClient.createBotInstance({
        instance_id: formData.instance_id,
        name: formData.name,
        credentials: {
          address: formData.address,
          mnemonic: formData.mnemonic,
        },
        trading_params: {
          is_testnet: false,
          zscore_threshold: formData.zscore_threshold,
          usd_per_trade: formData.usd_per_trade,
        },
      });

      setSuccess(true);
      setTimeout(() => {
        window.location.href = `/bots/${bot.instance_id}`;
      }, 1500);
    } catch (err: any) {
      setError(err.response?.data?.message || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={formData.instance_id}
        onChange={(e) =>
          setFormData((p) => ({ ...p, instance_id: e.target.value }))
        }
        placeholder="Bot ID"
        required
      />
      {/* More fields... */}
      <button type="submit" disabled={loading}>
        {loading ? 'Creating...' : 'Create Bot'}
      </button>
      {error && <p className="error">{error}</p>}
      {success && <p className="success">Bot created!</p>}
    </form>
  );
}
```

### Pattern 4: Polling for Status

```typescript
import { useEffect, useState } from 'react';
import { apiClient } from '@/api/client';

export function BacktestMonitor({ runId }: { runId: string }) {
  const [progress, setProgress] = useState<any>(null);

  useEffect(() => {
    let intervalId: NodeJS.Timer | null = null;

    const pollProgress = async () => {
      try {
        const status = await apiClient.getBacktestStatus(runId);
        setProgress(status);

        // Stop polling when complete
        if (
          ['COMPLETED', 'FAILED', 'CANCELLED'].includes(status.status) &&
          intervalId
        ) {
          clearInterval(intervalId);
        }
      } catch (err) {
        console.error('Poll failed:', err);
      }
    };

    // Poll every 2 seconds
    pollProgress();
    intervalId = setInterval(pollProgress, 2000);

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [runId]);

  if (!progress) return <div>Loading...</div>;

  return (
    <div>
      <div className="progress-bar">
        <div style={{ width: `${progress.progress_percent}%` }} />
      </div>
      <p>
        {progress.trades_completed}/{progress.trades_total} trades completed
      </p>
      <p>Current date: {progress.current_date}</p>
    </div>
  );
}
```

### Pattern 5: Custom Hook for Reusability

```typescript
import { useEffect, useState, useCallback } from 'react';

interface UseApiOptions {
  skip?: boolean;
  retryCount?: number;
  retryDelay?: number;
}

function useApiCall<T>(
  fetchFn: () => Promise<T>,
  dependencies: any[] = [],
  options: UseApiOptions = {}
) {
  const { skip = false, retryCount = 3, retryDelay = 1000 } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!skip);
  const [error, setError] = useState<string | null>(null);
  const [retries, setRetries] = useState(0);

  const refetch = useCallback(async () => {
    if (skip) return;

    try {
      setLoading(true);
      const result = await fetchFn();
      setData(result);
      setError(null);
      setRetries(0);
    } catch (err: any) {
      if (retries < retryCount) {
        setTimeout(() => setRetries((r) => r + 1), retryDelay);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [fetchFn, skip, retries, retryCount, retryDelay]);

  useEffect(() => {
    refetch();
  }, dependencies);

  return { data, loading, error, refetch, retries };
}

// Usage
export function BotStatsWithHook({ instanceId }: { instanceId: string }) {
  const { data: stats, loading, error, refetch } = useApiCall(
    () => apiClient.getBotStats(instanceId),
    [instanceId]
  );

  return (
    <div>
      {loading && <div>Loading...</div>}
      {error && (
        <div>
          Error: {error}
          <button onClick={refetch}>Retry</button>
        </div>
      )}
      {stats && <div>P&L: ${stats.total_pnl.toFixed(2)}</div>}
    </div>
  );
}
```

---

## 🛠️ Debugging Tips

### Check Network Requests

Open browser DevTools → Network tab to see all API requests:

1. Filter by XHR/Fetch
2. Look for requests to `http://localhost:8888`
3. Check request headers for `Authorization: Bearer ...`
4. Check response status and body

### Debug Auth Issues

```typescript
// Check if auth is loaded
console.log(apiClient.token);
console.log(localStorage.getItem('auth_token'));

// Check token expiration
const decoded = jwtDecode(apiClient.token);
console.log('Expires:', new Date(decoded.exp * 1000));
```

### Check Backend Connectivity

```bash
# Terminal: Test backend health
curl http://localhost:8888/health

# Test bot API health
curl http://localhost:8888/api/v1/system/status \
  -H "Authorization: Bearer <your-token>"
```

### Monitor WebSocket

```typescript
const ws = apiClient.connectBotUpdates('bot-id', (msg) => {
  console.log('WebSocket message:', msg);
});

ws.onopen = () => console.log('WebSocket connected');
ws.onerror = (err) => console.error('WebSocket error:', err);
ws.onclose = () => console.log('WebSocket disconnected');
```

---

## 🔒 Security Best Practices

### 1. Never Store Credentials

```typescript
// ❌ WRONG
localStorage.setItem('mnemonic', userMnemonic);

// ✅ RIGHT
// User pastes mnemonic only when creating bot
// Backend handles encryption and storage
```

### 2. Always Use HTTPS in Production

```typescript
// Development
const apiClient = new DydxBotAPIClient('http://localhost:8888');

// Production
const apiClient = new DydxBotAPIClient('https://api.yoursite.com');
```

### 3. Validate Tokens

```typescript
// Before sending requests
if (!apiClient.token) {
  // Redirect to login
  window.location.href = '/login';
}
```

### 4. Handle Token Expiration

The API client handles this automatically, but you can also:

```typescript
// Manual refresh
try {
  await apiClient.refreshAccessToken();
} catch (err) {
  // Refresh failed, logout user
  window.location.href = '/login';
}
```

---

## 📊 Performance Optimization

### 1. Use React.memo for Expensive Components

```typescript
const BotCard = React.memo(({ bot }: { bot: BotInstance }) => (
  <div>
    <h3>{bot.name}</h3>
    <p>Status: {bot.status}</p>
  </div>
));
```

### 2. Debounce Search/Filter

```typescript
import { useCallback, useState, useEffect } from 'react';

export function BotSearch() {
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<BotInstance[]>([]);

  const debouncedSearch = useCallback(
    debounce(async (query: string) => {
      const result = await apiClient.listBotInstances(query);
      setResults(result.data);
    }, 500),
    []
  );

  useEffect(() => {
    debouncedSearch(search);
  }, [search]);

  return <input onChange={(e) => setSearch(e.target.value)} />;
}
```

### 3. Use Pagination

Always paginate large lists:

```typescript
const [page, setPage] = useState(0);
const LIMIT = 50;

const { data: bots } = await apiClient.listBotInstances(
  undefined,
  LIMIT,
  page * LIMIT
);
```

### 4. Cache Results with React Query

```typescript
import { useQuery } from '@tanstack/react-query';

function useBotStats(instanceId: string) {
  return useQuery({
    queryKey: ['botStats', instanceId],
    queryFn: () => apiClient.getBotStats(instanceId),
    staleTime: 30000, // 30 seconds
  });
}
```

---

## 📈 State Management

### Zustand Store Example

```typescript
import { create } from 'zustand';

interface BotStore {
  selectedBotId: string | null;
  bots: BotInstance[];
  setSelectedBot: (id: string) => void;
  setBots: (bots: BotInstance[]) => void;
}

export const useBotStore = create<BotStore>((set) => ({
  selectedBotId: null,
  bots: [],
  setSelectedBot: (id) => set({ selectedBotId: id }),
  setBots: (bots) => set({ bots }),
}));
```

Usage in components:

```typescript
export function BotSelector() {
  const { bots, selectedBotId, setSelectedBot } = useBotStore();

  return (
    <select value={selectedBotId || ''} onChange={(e) => setSelectedBot(e.target.value)}>
      {bots.map((bot) => (
        <option key={bot.instance_id} value={bot.instance_id}>
          {bot.name}
        </option>
      ))}
    </select>
  );
}
```

---

## 🧪 Testing Components

### Example Test

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { BotList } from './BotList';

jest.mock('@/api/client', () => ({
  apiClient: {
    listBotInstances: jest.fn(() =>
      Promise.resolve({
        count: 1,
        data: [{ instance_id: 'bot-1', name: 'Test Bot', status: 'RUNNING' }],
      })
    ),
  },
}));

describe('BotList', () => {
  it('displays bot list', async () => {
    render(<BotList />);

    await waitFor(() => {
      expect(screen.getByText('Test Bot')).toBeInTheDocument();
    });
  });
});
```

---

## 📚 Key Files Reference

| File | Purpose |
|------|---------|
| `src/api/client.ts` | Full API client implementation |
| `src/store/auth.ts` | Authentication store (Zustand) |
| `docs/BACKEND_API_INTEGRATION.md` | Complete API reference |
| `docs/API_COVERAGE_CHECKLIST.md` | Endpoint availability matrix |
| `docs/REACT_COMPONENT_EXAMPLES.tsx` | Component patterns and examples |

---

## 🚀 Deployment Checklist

- [ ] Update API base URL to production backend
- [ ] Enable HTTPS for all API calls
- [ ] Set environment variables for API endpoint
- [ ] Test auth flow in production
- [ ] Verify WebSocket connections work
- [ ] Test error handling with simulated failures
- [ ] Monitor API rate limits
- [ ] Set up error logging (Sentry, etc.)

---

## 🤝 Support

For issues or questions:

1. Check `API_COVERAGE_CHECKLIST.md` for endpoint availability
2. Review `REACT_COMPONENT_EXAMPLES.tsx` for pattern usage
3. Check browser DevTools Network tab for API responses
4. Verify backend is running: `curl http://localhost:8888/health`
5. Check backend logs for error details
