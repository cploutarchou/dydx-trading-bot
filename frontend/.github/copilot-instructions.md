# dYdX Trading Bot Frontend - AI Coding Agent Instructions

Preferred service agent: `.github/agents/senior-react-defi-product.agent.md`

## Project Overview

React 19 + TypeScript + Vite frontend for **dYdX trading bot platform** - full-stack UI for backtesting, strategy management, and live bot operations. Frontend uses the Go backend on `localhost:8888`, which orchestrates/proxies Bot API operations.

## Architecture & Tech Stack

| Layer             | Technology                     | Purpose                                  |
| ----------------- | ------------------------------ | ---------------------------------------- |
| **Framework**     | React 19 + TypeScript 5 + Vite | Modern UI with HMR development           |
| **Data Fetching** | React Query (TanStack) v5      | Advanced caching, background sync, retry |
| **State**         | Zustand 5 (with persist)       | Auth state + localStorage persistence    |
| **Routing**       | React Router v7                | Nested routes with auth guards           |
| **Styling**       | Tailwind CSS v4                | Dark theme, utility-first CSS            |
| **Charts**        | Recharts 3                     | Financial data visualization             |
| **HTTP**          | Axios 1 + interceptors         | JWT auto-injection, 401 handling         |
| **Icons**         | Lucide React                   | UI icons (Loader, Play, etc.)            |

**Strategic choices:**

- **React Query over Zustand for API**: Server-state caching, background updates, retry logic separate from auth state
- **Zustand for auth only**: `enhancedAuth.ts` holds user + preferences, persisted to localStorage
- **Enhanced client pattern**: `enhancedClient.ts` wraps `api.ts` with bot/backtest methods not yet in base client

## Development Quick Start

```bash
npm run dev          # Dev server (HMR, port 5173)
npm run build        # Production build
npm run preview      # Test production build locally
npm run lint         # ESLint check
```

Preferred local workflow: `npm install`, `npm run dev`, and use the repo-root infra/stack commands when integration services are needed.

## Core Architecture: Five Layers

### 1. HTTP Client Layer (`src/api.ts` + `src/api/client.ts`)

**Centralized Axios client** with request/response interceptors:

```typescript
class ApiClient {
  // JWT auto-injection + refresh logic
  // 401 → auto logout + redirect to /login via interceptor
  // Axios request caching, retry with exponential backoff
  // Console logs with 🔌 prefix for debugging

  login(username, password): Promise<AuthResponse>;
  register(username, email, password): Promise<User>;
  getCurrentUser(): Promise<User>;

  // Backtests
  listBacktests(skip, limit): Promise<ApiResponse<{ backtests: BacktestRun[] }>>;
  getBacktest(runId): Promise<BacktestData>;
  runBacktest(params): Promise<{ run_id: string }>;
  getBacktestTrades(runId, limit, offset): Promise<{ total; trades }>;
  getBacktestPerformance(runId): Promise<PerformanceMetrics>;

  // WebSocket
  connectBacktestSocket(runId, token): WebSocket;
}
```

**Key features:**

- All endpoints return `{success, message, data, timestamp}`
- API response extractor: `response.data` (already unwrapped by client)
- Nested data pattern: `response.data?.backtests` (NOT `response.data.data.backtests`)
- Token stored in localStorage, attached as `Authorization: Bearer` header
- 401 responses auto-handled: logout + force redirect to `/login`

### 2. Query Layer (`src/api/hooks.ts` + `src/api/queryClient.ts`)

**React Query (TanStack) for server-state management** - handles caching, background sync, retries:

```typescript
// Custom hooks wrapping React Query (NOT direct useState)
export function useBotInstances(params) {
  return useQuery({
    queryKey: queryKeys.bots(params),
    queryFn: () => apiClient.listBotInstances(params),
    staleTime: 5 * 60 * 1000, // 5 min cache before "stale"
    gcTime: 10 * 60 * 1000, // 10 min garbage collection
    retry: failureCount < 3, // Auto-retry 3x with backoff
  });
}

export function useCreateBacktest() {
  return useMutation({
    mutationFn: (config) => apiClient.runBacktest(config),
    onSuccess: () => {
      // Invalidate backtest list after create
      queryClient.invalidateQueries({ queryKey: queryKeys.backtests });
    },
  });
}
```

**Why NOT useState for API data:**

- React Query handles stale-while-revalidate (SWR) pattern
- Background sync on window focus, reconnect, polling
- Deduplication of requests (same query → single HTTP call)
- Built-in loading/error states without boilerplate

**Cache configuration tiers** (in `queryClient.ts`):

- `realtime`: 1s stale, 2min gc, 5s polling (live trading data)
- `trading`: 5s stale, 5min gc (bot instance data)
- `static`: 30min stale, 1hr gc (reference data)

### 3. Auth State Management (`src/store/enhancedAuth.ts`)

**Zustand store (auth only) with localStorage persistence:**

```typescript
interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  preferences: UserPreferences; // Theme, currency, notifications
  sessionStarted: number | null;

  // Methods
  login(username, password): Promise<void>;
  logout(): Promise<void>;
  updatePreferences(partial): void;
  initialize(): Promise<void>;
}

// Usage in components:
const { user, isAuthenticated, login, logout } = useAuthStore();
```

**Key principles:**

- Auth state ONLY (NOT API data) → use React Query for everything else
- Persisted via Zustand middleware → survives page refresh
- Direct mutation methods (no complex immutability)
- Preferences stored for UX (theme, currency, dashboard defaults)

### 4. Page Components (`src/pages/`)

Route-level components that compose smaller reusable components:

- **LoginPage** - Auth form with email/password + 2FA support
- **DashboardPage** - Main hub: BacktestRunner + BacktestList + stats overview
- **BacktestDetailsV2** - Backtest visualization: charts (equity, P&L, trade scatter), trade table
- **Settings** - User prefs, DYDX key management, strategy configuration
- **BotDashboard** - Live trading view: bot instances, positions, real-time stats

### 5. Reusable Components (`src/components/`)

Smaller, focused UI components organized by domain:

**Core:**

- **BacktestRunner** - Form for backtest params (dates, pairs, thresholds) → `api.runBacktest()`
- **BacktestList** - Paginated table of backtest runs
- **BacktestProgress** - Real-time progress via WebSocket

**Bot Management:**

- **BotManager** - CRUD for bot instances
- **DYDXKeyManager** - Secure credential management

**Advanced:**

- **StrategyBuilder** - Visual/config-based strategy creation
- **StrategyLibrary** - Browse & clone saved strategies
- **BacktestComparator** - Multi-backtest analysis

## Critical Data Flows

### Authentication Flow

```
Login Form → useAuthStore.login(username, password)
  → api.login() → POST /api/v1/auth/login
  → Token in localStorage + Axios header
  → api.getCurrentUser() → Load user profile
  → isAuthenticated() = true → ProtectedRoute allows Dashboard access
```

### Backtest Execution Flow

```
BacktestRunner form submit
  → api.runBacktest({start_date, end_date, num_pairs, ...})
  → POST /api/v1/backtests/run
  → Returns {run_id, status}
  → Dashboard refreshes BacktestList
  → List fetches api.listBacktests()
  → New backtest appears in table
  → User clicks row → Navigate to /backtest/{runId}
  → BacktestDetailsPage fetches api.getBacktest(runId)
  → Renders charts + table
```

### Real-Time Updates

```
BacktestDetailsPage mounts
  → useBacktestProgress hook initializes
  → Opens WebSocket through backend: ws://localhost:8888/api/v1/backtests/{runId}/live?access_token=JWT
  → On message: Update progress state (% complete, current pair)
  → On close: Log "🔌 Disconnected from backtest progress"
```

## API Response Handling Pattern

**IMPORTANT**: Backend response has nested structure:

```typescript
// Raw response from api.listBacktests()
{
  success: true,
  message: "Success",
  data: {
    backtests: [BacktestRun, ...]  // ← Nested here!
  },
  timestamp: "2024-10-18..."
}
```

**In component**: `const backTests = response.data?.backtests || []` (see `BacktestList.tsx` line 40).

## Styling & UI Conventions

### Dark Theme (Always)

- **Backgrounds**: `bg-slate-900` (page), `bg-slate-800` (cards), `bg-slate-700` (hover)
- **Text**: `text-white` (primary), `text-gray-300` (secondary), `text-slate-300` (tertiary)
- **Borders**: `border-slate-700` (cards), `border-slate-600` (inputs)

### Financial Color Coding

- **Profit/Positive**: `text-green-400` for PnL > 0, `bg-green-900` for badges
- **Loss/Negative**: `text-red-400` for PnL < 0, `bg-red-900` for error states
- **Neutral/Running**: `text-blue-300`, `bg-blue-900` for "running" status
- **Pending**: `text-yellow-300`, `bg-yellow-900` for pending trades

### Loading & Error States

**All data-fetching components must follow this pattern:**

```typescript
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

if (loading) return <div>Loading spinner with Loader from lucide-react</div>;
if (error) return <div className="bg-red-900 border-red-700">Error message</div>;
return <div>Data visualization</div>;
```

**Loading spinner**: Import `Loader` from `lucide-react`, use `animate-spin` class.

## Logging & Debugging

**Emoji-prefixed console logs** for easy filtering:

- `🔐` - Auth flow (login, logout, token)
- `📊` - Backtest operations (run, list, results)
- `🔌` - WebSocket/connectivity (connect, disconnect, messages)
- `❌` - Errors (catch blocks, API failures)
- `🔧` - App/component lifecycle (mount, unmount, navigation)

**Example**: `console.log('🔌 api.ts: login response:', response.data);`

## Protected Routes Pattern

```typescript
const ProtectedRoute: React.FC<{ children }> = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  if (!isAuthenticated && !user) return <Navigate to="/login" />;
  return <>{children}</>;
};

<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route
    path="/dashboard"
    element={
      <ProtectedRoute>
        <Dashboard />
      </ProtectedRoute>
    }
  />
</Routes>;
```

**401 handling**: Axios interceptor catches 401 → calls `api.logout()` → redirects to /login.

## Recharts Chart Patterns

All Recharts visualizations follow this structure - responsive containers with dark theme colors:

- Always wrap in ResponsiveContainer for mobile responsiveness
- Use dark colors from Tailwind palette
- Tooltip styling for dark theme: backgroundColor = '1e293b'
- Common stroke colors: 22c55e (green), ef4444 (red), 3b82f6 (blue)
- CartesianGrid: stroke = '475569' for dark backgrounds

## Environment Variables

```bash
# repo-root .env (development)
VITE_API_URL=http://localhost:8888

# Development reads VITE_API_URL from the repo-root .env.
# Production uses VITE_API_URL from environment at build time
```

**Note**: `VITE_*` prefix required for Vite to embed in bundle. Build fails silently without this.

## Error Boundary (App-Level)

`App.tsx` includes `ErrorBoundary` class component - catches React rendering errors:

```typescript
class ErrorBoundary extends React.Component<...> {
  render() {
    if (hasError) return <div>⚠️ Application Error: {error.message}</div>;
    return this.props.children;
  }
}
```

**Behavior**: Prevents white-screen crashes, logs to console with `❌` prefix.

## File Structure Rationale

```
src/
├── api.ts                    # Base API client (100% of API calls originate here)
├── api/                      # API layer
│   ├── client.ts            # Extended API client with advanced features
│   ├── enhancedClient.ts    # Wrapper adding bot/backtest methods
│   ├── hooks.ts             # 50+ React Query custom hooks
│   ├── queryClient.ts       # React Query config + cache utils
│   ├── types.ts             # All TypeScript interfaces (600+ lines)
│   ├── websocket.ts         # WebSocket manager + reconnection logic
│   └── QueryProvider.tsx    # React Query provider wrapper
├── App.tsx                   # Error boundary + router + React Query provider
├── main.tsx                  # React entry point
├── index.css                 # Tailwind @imports
├── pages/                    # Route-level components (Dashboard, BacktestDetails, Login)
├── components/               # Reusable UI (BacktestRunner, BacktestList, charts)
├── hooks/                    # Custom React hooks (useBacktestProgress)
└── store/                    # Zustand stores (enhancedAuth.ts for auth + prefs)
```

**Key pattern**: `api.ts` → `apiClient` (base methods) → `enhancedClient.ts` → `enhancedApiClient` (extended methods) → `hooks.ts` (React Query wrappers)

## Common Additions Guide

### Adding a New API Endpoint

1. Add interface to `src/api/types.ts` type definitions
2. Add method to `ApiClient` in `src/api/client.ts` with proper error handling
3. If extending existing functionality, add wrapper method to `enhancedClient.ts`
4. Create React Query hook in `src/api/hooks.ts` (use `useQuery` or `useMutation`)
5. Add query key to `queryKeys` in `queryClient.ts`
6. Add cache config to `queryConfigs` if needed (realtime/trading/static)
7. Use console.log with emoji prefix (🔌 or 📊)
8. Handle `response.data` extraction (already done in base client)

### Adding a New Query Hook

```typescript
// In src/api/hooks.ts
export function useMyNewData(id: string) {
  return useQuery({
    queryKey: queryKeys.myThing(id), // Add to queryKeys in queryClient.ts
    queryFn: () => apiClient.getMyData(id),
    ...queryConfigs.trading, // Pick cache tier
    enabled: !!id, // Conditional fetching
  });
}

// Usage in component:
const { data, isLoading, error } = useMyNewData(id);
```

### Adding a New Page

1. Create file in `src/pages/PageName.tsx` (functional component with `React.FC`)
2. Add route in `App.tsx` Router
3. Use `useAuthStore()` for auth state, `useNavigate()` for routing
4. Use React Query hooks for API data (NOT useState)
5. Wrap with `<ProtectedRoute>` if authenticated-only
6. Use Tailwind dark theme colors (slate-900, slate-800, etc.)

### Adding a New Component

1. Create file in `src/components/ComponentName.tsx`
2. Define props interface at top of file
3. Use React Query hooks or accept data via props
4. Include loading + error states with proper styling
5. Export as named export (not default)
6. Use emoji-prefixed logging for debugging

## API Response Patterns & Integration

### Enhanced Client Wrapper Pattern

The `enhancedClient.ts` extends base `ApiClient` to delegate methods:

```typescript
// enhancedClient.ts - Extends existing client with new methods
class EnhancedAPIClient {
  private baseClient = apiClient; // Reference to base client

  // Delegate all base methods
  login = this.baseClient.login.bind(this.baseClient);
  getCurrentUser = this.baseClient.getCurrentUser.bind(this.baseClient);

  // Add new methods for bot/backtest endpoints
  async listBotInstances(params): Promise<{ count; data }> {
    // Fetch from /api/v1/bots endpoint
  }

  async getBacktest(runId): Promise<any> {
    // Delegate to base client
  }
}
```

**Why this pattern:**

- Base `apiClient` is single source of truth for core endpoints
- New bot/backtest methods added without modifying base
- All use same Axios instance (same interceptors, token injection)
- Keeps concerns separated: core auth vs domain features

### React Query Hook Integration

Every API call goes through React Query hooks (in `hooks.ts`):

```typescript
// hooks.ts - React Query wrappers
export function useBotInstances(params = {}) {
  return useQuery({
    queryKey: queryKeys.bots(params),
    queryFn: () => apiClient.listBotInstances(params), // ← Uses enhancedClient
    ...queryConfigs.trading, // Cache tier
    enabled: !!params, // Conditional
  });
}

// In components:
const { data, isLoading, error } = useBotInstances({ limit: 10 });
```

**Never fetch API data directly in components** - always use React Query hooks for:

- Automatic caching/stale-while-revalidate
- Background refetch on focus/reconnect
- Built-in loading/error states
- Query deduplication

### Bot Instance & Backtest Data Models

Key types in `src/api/types.ts`:

```typescript
interface BotInstance {
  instance_id: string;
  status: 'RUNNING' | 'STOPPED' | 'ERROR';
  total_trades: number;
  win_rate: number;
  pnl: number;
  uptime_seconds: number;
}

interface BacktestRun {
  run_id: string;
  status: string;
  progress_percent: number;
  start_date: string;
  end_date: string;
  num_pairs: number;
}
```

## TypeScript Strict Mode

`tsconfig.json` enforces:

- `strict: true` - Full type checking
- `noUnusedLocals: true` - Catches dead code
- `noUnusedParameters: true` - Unused params flagged
- `noFalltallCasesInSwitch: true` - Switch statements must be exhaustive

**All files must compile without warnings** - CI/CD will fail otherwise.

## Docker Workflows

```bash
# Development (HMR enabled, watches source)
docker build -f Dockerfile.dev -t dydx-frontend-dev .
docker run -p 5173:5173 dydx-frontend-dev

# Production (optimized build, port 3000)
docker build -t dydx-frontend .
docker run -p 3000:3000 dydx-frontend
```

## Performance Notes

- **Code splitting**: React Router auto-splits pages
- **CSS**: Tailwind v4 has optimized output (~19 KB)
- **API efficiency**: Use WebSocket for real-time (not polling)
- **Memoization**: Use `useMemo()` for expensive chart calculations

When working on this codebase, prioritize: (1) type safety, (2) dark theme consistency, (3) centralized API patterns, (4) console logging for debugging.
