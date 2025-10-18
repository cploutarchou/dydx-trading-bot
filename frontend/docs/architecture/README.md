# Architecture Overview

Comprehensive documentation of the dYdX Trading Bot Frontend architecture.

## Quick Links

| Document | Purpose | Read Time |
|----------|---------|-----------|
| **[Data Flow](DATA_FLOW.md)** | Component interactions and data movement | 10 min |
| **[Patterns](PATTERNS.md)** | Code patterns and conventions | 15 min |
| **[API Integration](API_INTEGRATION.md)** | Backend communication patterns | 10 min |

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      React 19 Frontend                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Pages (Route Components)                 │   │
│  │  ┌──────────────┬──────────────┬────────────────────┐ │   │
│  │  │   Dashboard  │   Backtest   │   Login            │ │   │
│  │  │              │   Details    │                    │ │   │
│  │  └──────────────┴──────────────┴────────────────────┘ │   │
│  └─────────┬──────────────────────────────────────────────┘   │
│            │                                                    │
│  ┌─────────▼──────────────────────────────────────────────┐   │
│  │         Reusable Components (UI Building Blocks)        │   │
│  │  ┌─────────────┬──────────────┬──────────────────────┐ │   │
│  │  │  Backtest   │  Backtest    │  Backtest Progress  │ │   │
│  │  │  Runner     │  List        │                     │ │   │
│  │  └─────────────┴──────────────┴──────────────────────┘ │   │
│  └─────────┬──────────────────────────────────────────────┘   │
│            │                                                    │
│  ┌─────────▼──────────────────────────────────────────────┐   │
│  │          State Management (Zustand Stores)             │   │
│  │  ┌──────────────────────────────────────────────────┐ │   │
│  │  │  Auth Store: user, token, isAuthenticated()      │ │   │
│  │  │  Backtest Store (optional): backtest data        │ │   │
│  │  └──────────────────────────────────────────────────┘ │   │
│  └─────────┬──────────────────────────────────────────────┘   │
│            │                                                    │
│  ┌─────────▼──────────────────────────────────────────────┐   │
│  │          API Client (Centralized HTTP)                 │   │
│  │  ┌──────────────────────────────────────────────────┐ │   │
│  │  │  Axios with JWT interceptors                    │ │   │
│  │  │  Auto token attachment & refresh                │ │   │
│  │  │  Comprehensive error handling                   │ │   │
│  │  └──────────────────────────────────────────────────┘ │   │
│  └─────────┬──────────────────────────────────────────────┘   │
│            │                                                    │
└────────────┼────────────────────────────────────────────────────┘
             │
        ┌────▼─────────────────────┐
        │   Backend API            │
        │   http://localhost:8000  │
        └─────────────────────────┘
             │
        ┌────▼────┬──────────┬────────────┐
        │          │          │            │
    ┌───▼───┐ ┌───▼───┐ ┌───▼────┐ ┌───▼────┐
    │Auth   │ │Backtest
│ │Database │ │Cache  │
    └───────┘ └───────┘ └────────┘ └───────┘
```

## Technology Stack

### Frontend Framework

- **React 19** - Latest UI library with new features
- **TypeScript** - Type-safe JavaScript
- **Vite 7** - Fast, modern bundler (replaces Create React App)
- **React Router v7** - Client-side routing

### State Management

- **Zustand 5** - Lightweight, modern state management
- **Persist middleware** - Automatic localStorage persistence
- **No Redux** - Zustand chosen for simplicity

### Styling

- **Tailwind CSS v4** - Utility-first CSS framework
- **Dark theme** - slate-900 backgrounds throughout
- **Responsive design** - Mobile-first approach

### Data Visualization

- **Recharts 3** - React chart library for financial data
- **Responsive containers** - Auto-sizing charts

### HTTP Communication

- **Axios 1** - Promise-based HTTP client
- **Custom interceptors** - Auto JWT injection, error handling
- **Centralized client** - Single source of truth for API calls

### Development

- **ESLint** - Code quality
- **Prettier** - Code formatting
- **TypeScript strict mode** - Maximum type safety
- **Vite HMR** - Hot Module Replacement for fast development

## Key Directories

```
frontend/
├── src/
│   ├── pages/               # Route-level components
│   │   ├── Dashboard.tsx   # Main backtest dashboard
│   │   ├── BacktestDetails.tsx  # Individual backtest details
│   │   └── Login.tsx        # Authentication
│   │
│   ├── components/          # Reusable UI components
│   │   ├── BacktestRunner.tsx    # Run new backtests
│   │   ├── BacktestList.tsx      # List of backtests
│   │   └── BacktestProgress.tsx  # Real-time progress
│   │
│   ├── hooks/              # Custom React hooks
│   │   └── useBacktestProgress.ts # WebSocket + progress
│   │
│   ├── store/              # Zustand stores
│   │   └── auth.ts         # Authentication state
│   │
│   ├── api.ts              # Centralized API client
│   ├── App.tsx             # Root component + error boundary
│   ├── main.tsx            # Entry point
│   └── index.css           # Global styles
│
├── .devcontainer/          # Development environment
├── docker-compose.yml      # Local services
├── vite.config.ts          # Vite bundler config
├── tailwind.config.js      # Tailwind configuration
├── tsconfig.json           # TypeScript config
└── package.json            # Dependencies

docs/                       # Documentation (you are here)
├── README.md              # Documentation index
├── SETUP.md               # Setup guide
├── architecture/
│   ├── README.md          # Architecture overview (this file)
│   ├── DATA_FLOW.md       # Component interactions
│   ├── PATTERNS.md        # Code patterns
│   └── API_INTEGRATION.md # API patterns
└── guides/
    └── TROUBLESHOOTING.md # Common issues
```

## Core Concepts

### Authentication Flow

```
┌─────────────────────────────────────────┐
│ User inputs credentials on Login page   │
└────────────────┬────────────────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │ api.login(email,    │
        │ password) called    │
        └────────┬────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │ POST /api/v1/auth/  │
        │ login with creds    │
        └────────┬────────────┘
                 │
                 ▼
        ┌──────────────────────────┐
        │ Backend returns JWT      │
        │ token + user data        │
        └────────┬─────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────┐
    │ Zustand auth store updates:        │
    │ - user = response.user             │
    │ - token stored in localStorage     │
    │ - Axios interceptor attaches token │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌────────────────────────────────┐
    │ User navigated to Dashboard    │
    └────────────────────────────────┘
```

### Data Flow: Starting a Backtest

```
BacktestRunner component
       │
       ▼ (user clicks Run Backtest)
handleRunBacktest()
       │
       ├─ Validate form inputs
       │
       ├─ Call api.runBacktest(params)
       │       │
       │       ▼ POST /api/v1/backtests/run
       │       Backend processes backtest
       │       │
       │       └─ Returns { run_id, status }
       │
       ├─ Zustand store updates
       │
       └─ Trigger BacktestList refresh
              │
              ▼ Fetch updated list
         api.listBacktests()
              │
              ├─ GET /api/v1/backtests
              │
              └─ Update UI with new backtest
```

### Real-time WebSocket Connection

```
BacktestDetails component mounts
       │
       ▼ useBacktestProgress hook initializes
Creates WebSocket connection to:
/ws/backtest/{runId}?token={jwt}
       │
       ├─ Logs: "🔌 Connecting to backtest progress..."
       │
       ├─ On message: Updates progress state
       │
       ├─ On error: Attempts reconnection with backoff
       │
       └─ On component unmount: Closes connection
              Logs: "🔌 Disconnected from backtest progress"
```

## State Management Structure

### Auth Store (Zustand)

```typescript
{
  user: {
    id: string;
    email: string;
    // ... other user fields
  } | null;
  
  loading: boolean;
  error: string | null;
  
  // Methods
  login(email: string, password: string): Promise<void>;
  logout(): void;
  getCurrentUser(): Promise<void>;
  isAuthenticated(): boolean;
}
```

**Persistence:** Stored in `localStorage` with key `'auth-store'`

**Usage:**

```typescript
const { user, isAuthenticated, login, logout } = useAuthStore();
```

## API Client Pattern

### Centralized HTTP Client

All API calls go through a single `ApiClient` class in `src/api.ts`:

```typescript
class ApiClient {
  // Authentication
  login(email: string, password: string): Promise<{access_token, token_type}>;
  getCurrentUser(): Promise<User>;
  
  // Backtests
  listBacktests(): Promise<{data: {backtests: BacktestRun[]}}>;
  getBacktest(runId: string): Promise<BacktestRun>;
  runBacktest(params: BacktestParams): Promise<{run_id: string}>;
  
  // Real-time
  connectBacktestSocket(runId: string, token: string): WebSocket;
}
```

### Key Features

- **JWT Interceptor**: Automatically attaches token to every request
- **Error Handling**: Extracts error messages, handles 401 (logout + redirect)
- **Debug Logging**: Emoji-prefixed logs (🔐, 📊, 🔌, ❌) for filtering
- **Base URL**: Automatically set from environment: `http://localhost:8000/api/v1/`

### Error Handling

```typescript
try {
  const response = await api.runBacktest(params);
  // Handle success
} catch (error) {
  const message = error.response?.data?.message || error.message;
  // Display user-friendly error
}
```

## Protected Routes

The app uses a `ProtectedRoute` wrapper component:

```typescript
<Routes>
  <Route path="/login" element={<Login />} />
  <Route element={<ProtectedRoute />}>
    <Route path="/dashboard" element={<Dashboard />} />
    <Route path="/backtest/:id" element={<BacktestDetails />} />
  </Route>
</Routes>
```

**Behavior:**

- If not authenticated → redirected to `/login`
- If authenticated → proceed to route
- Token refresh handled by API interceptor

## Styling Conventions

### Color Coding

- **Green** (`text-green-400`) - Profits, positive values
- **Red** (`text-red-400`) - Losses, negative values
- **White** (`text-white`) - Primary text
- **Slate-gray** (`text-slate-300`) - Secondary text
- **Dark backgrounds** (`bg-slate-900`, `bg-slate-800`) - Dark theme

### Loading States

Every data-fetching component has:

```typescript
if (loading) return <div className="flex items-center justify-center"><Loader /></div>;
if (error) return <div className="bg-red-900 border-red-700 p-4">Error: {error}</div>;

// Show data
```

## Components

### Pages

- **Login.tsx** - Authentication, form submission
- **Dashboard.tsx** - List of backtests, ability to run new tests
- **BacktestDetails.tsx** - Detailed results, charts, trade history

### Reusable Components

- **BacktestRunner.tsx** - Form to configure and run backtest
- **BacktestList.tsx** - Table/grid of backtest runs
- **BacktestProgress.tsx** - Real-time progress display with WebSocket

### Hooks

- **useBacktestProgress.ts** - WebSocket connection for progress updates

## Environment Configuration

### Development (.env.local)

```bash
VITE_API_URL=http://localhost:8000
```

### Production (.env.production)

```bash
VITE_API_URL=https://api.your-domain.com
```

### Build-time Variables

- `VITE_API_URL` - Backend API base URL
- All other `VITE_*` variables are embedded in bundle

## Performance Considerations

### Code Splitting

- React Router automatically code-splits pages
- Lazy loading via `React.lazy()` if needed

### Bundle Size

- Current: ~637 KB JavaScript
- CSS: ~19 KB (Tailwind v4 optimized)

### API Optimization

- Backtest list caching (optional with Zustand)
- WebSocket for real-time updates (instead of polling)

### Rendering

- React 19 Compiler-optimized renders
- Memoization with `useMemo()` for expensive operations
- Recharts components wrapped in `ResponsiveContainer`

## Next Steps

See:

- **[DATA_FLOW.md](DATA_FLOW.md)** - Detailed component interactions
- **[PATTERNS.md](PATTERNS.md)** - Code patterns and best practices
- **[API_INTEGRATION.md](API_INTEGRATION.md)** - Backend integration details
