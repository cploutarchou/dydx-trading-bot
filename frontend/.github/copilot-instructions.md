# dYdX Trading Bot Frontend - AI Coding Agent Instructions

## Project Overview

React 19 + TypeScript + Vite frontend for **dYdX pairs trading backtest system** - a statistical arbitrage backtesting UI for cryptocurrency pairs trading. This is the complete frontend implementation; the backend API runs separately on `localhost:8888`.

## Architecture & Tech Stack

| Layer         | Technology                       | Purpose                              |
| ------------- | -------------------------------- | ------------------------------------ |
| **Framework** | React 19 + TypeScript 5 + Vite 7 | Modern UI with HMR development       |
| **State**     | Zustand 5 (with persist)         | Lightweight alternative to Redux     |
| **Routing**   | React Router v7                  | Client-side navigation               |
| **Styling**   | Tailwind CSS v4                  | Dark-themed utility styles           |
| **Charts**    | Recharts 3                       | Financial data visualization         |
| **HTTP**      | Axios 1 + interceptors           | Centralized API client with JWT auth |
| **Icons**     | Lucide React                     | UI icons (Loader, Play, etc.)        |

**Key decision: Zustand over Redux** - See `src/store/auth.ts` - chosen for simplicity and built-in localStorage persistence via middleware.

## Development Quick Start

```bash
npm run dev          # Dev server (HMR, port 5173)
npm run build        # Production build
npm run preview      # Test production build locally
npm run lint         # ESLint check
```

**DevContainer preferred**: `code frontend/` → click "Reopen in Container" (includes all deps + Docker).

## Core Architecture: Four Layers

### 1. API Client Layer (`src/api.ts`)

**Centralized Axios client** - single source of truth for all backend calls:

```typescript
class ApiClient {
  // JWT auto-injection via request interceptor
  // 401 handling: logout + redirect to /login
  // Detailed console logs with 🔌 prefix for debugging

  login(username, password): Promise<{ access_token }>; // POST /api/v1/auth/login
  getCurrentUser(): Promise<User>; // GET /api/v1/users/me
  listBacktests(skip, limit): Promise<ApiResponse>; // GET /api/v1/backtests?skip=X&limit=Y
  getBacktest(runId): Promise<BacktestData>; // GET /api/v1/backtests/{runId}
  runBacktest(params): Promise<{ run_id }>; // POST /api/v1/backtests/run
  connectBacktestSocket(runId, token): WebSocket; // ws://localhost/ws/backtest/{runId}?token=X
}
```

**Pattern**: All endpoints return `{success, message, data, timestamp}` - extract `response.data` and handle nested `response.data.backtests` pattern.

### 2. State Management (`src/store/auth.ts`)

**Zustand store with localStorage persistence:**

```typescript
useAuthStore: {
  user: User | null
  loading: boolean
  error: string | null
  login(username, password): Promise<void>        // Calls api.login + getCurrentUser
  logout(): void                                   // Clears token + user from state
  isAuthenticated(): boolean                       // Simple guard for ProtectedRoute
}
```

**Usage pattern**: `const { user, isAuthenticated, login, logout } = useAuthStore()` - no selectors needed.

### 3. Page Components (`src/pages/`)

Route-level components that compose smaller reusable components:

- **LoginPage** - Form with email/password, calls `useAuthStore.login()`
- **DashboardPage** - Main hub: header + BacktestRunner + BacktestList, refresh trigger state
- **BacktestDetailsPage** - Single backtest view with charts (equity curve, P&L by pair, trade scatter), trade table, WebSocket real-time updates

### 4. Reusable Components (`src/components/`)

Smaller, focused UI components:

- **BacktestRunner** - Form for backtest parameters (dates, pairs, thresholds) + `api.runBacktest()` call
- **BacktestList** - Table of backtest runs with status badges, navigate to details on click
- **BacktestProgress** - Real-time progress display via `useBacktestProgress` hook (WebSocket)

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
  → Opens WebSocket: ws://localhost/ws/backtest/{runId}?token=JWT
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
# .env.local (development)
VITE_API_URL=http://localhost:8888

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
├── api.ts                    # Single client (100% of API calls go through here)
├── App.tsx                   # Error boundary + router setup
├── main.tsx                  # React entry point
├── index.css                 # Tailwind @imports
├── pages/                    # Route-level (Dashboard, BacktestDetails, Login)
├── components/               # Reusable UI (BacktestRunner, BacktestList)
├── hooks/                    # Custom hooks (useBacktestProgress for WebSocket)
└── store/                    # Zustand stores (auth.ts only currently)
```

## Common Additions Guide

### Adding a New API Endpoint

1. Add interface to `src/api.ts` type definitions
2. Add method to `ApiClient` class with proper error handling
3. Use console.log with emoji prefix (🔌 or 📊)
4. Handle `response.data` extraction (already done in client)

### Adding a New Page

1. Create file in `src/pages/PageName.tsx` (functional component with `React.FC`)
2. Add route in `App.tsx` Router
3. Use `useAuthStore()` for auth state, `useNavigate()` for routing
4. Wrap with `<ProtectedRoute>` if authenticated-only

### Adding a New Component

1. Create file in `src/components/ComponentName.tsx`
2. Define props interface at top of file
3. Include loading + error states with proper styling
4. Export as named export (not default)

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
