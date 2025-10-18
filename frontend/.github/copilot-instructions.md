# dYdX Trading Bot Frontend - AI Coding Agent Instructions

## Project Overview

React/TypeScript frontend for a **dYdX pairs trading backtest system**. This is the UI component of a larger trading bot that runs statistical arbitrage backtests on cryptocurrency pairs.

## Architecture & Core Patterns

### Tech Stack

- **React 18** + **TypeScript** + **Vite** (not Create React App)
- **Zustand** for state management (not Redux) - see `src/store/auth.ts`
- **TailwindCSS** with **dark theme** (slate-900 backgrounds)
- **Recharts** for financial data visualization
- **React Router** for SPA navigation
- **Axios** with custom interceptors for API communication

### API Integration Pattern

- **Centralized API client** in `src/api.ts` with automatic token management
- Backend expects `/api/v1/` prefixed endpoints
- **Development proxy**: API calls proxied to `localhost:8000` via Vite config
- **Production**: API URL via `VITE_API_URL` environment variable
- **Authentication**: JWT tokens stored in localStorage, auto-attached via Axios interceptors

### State Management Architecture

```typescript
// Zustand with persistence - prefer this pattern over useState for shared state
const useAuthStore = create<AuthStore>()(
  persist((set, get) => ({
    // Zustand store structure in src/store/auth.ts
  }))
);
```

### Component Patterns

- **Functional components** with hooks only (no class components)
- **Props interfaces** defined inline or at component top
- **Conditional rendering** for loading/error states in all data-fetching components
- **Protected routes** via `ProtectedRoute` wrapper component

## Key Development Workflows

### Running the Application

```bash
npm run dev          # Development server (port 5173)
npm run build        # Production build
npm run preview      # Preview production build
```

### Docker Development

```bash
# Development container
docker build -f Dockerfile.dev -t dydx-frontend-dev .
docker run -p 5173:5173 dydx-frontend-dev

# Production container
docker build -t dydx-frontend .
docker run -p 3000:3000 dydx-frontend
```

### API Development Pattern

When adding new endpoints:

1. Add interface definitions to `src/api.ts`
2. Add method to `ApiClient` class with proper error handling
3. Use extensive console.log debugging (project pattern - see existing endpoints)
4. Handle both `response.data` and `response.data.data` patterns from backend

## Project-Specific Conventions

### Styling Patterns

- **Dark theme mandatory**: Use `bg-slate-900`, `bg-slate-800`, `text-white` consistently
- **Color coding**: Green for profits (`text-green-400`), red for losses (`text-red-400`)
- **Loading states**: Always include loading spinners with `Loader` from `lucide-react`
- **Error states**: Red background cards (`bg-red-900 border-red-700`)

### Data Flow Patterns

- **Financial data**: All P&L values have both base currency (`pnl`) and USD (`pnl_usd`) variants
- **Date handling**: Backend returns ISO strings, display via `toLocaleDateString()` or `toLocaleString()`
- **Status indicators**: Color-coded badges for backtest status (`completed`, `running`, `failed`)

### Component Structure

```
src/
├── pages/           # Route-level components (Dashboard, Login, BacktestDetails)
├── components/      # Reusable UI components (BacktestRunner, BacktestList)
├── store/          # Zustand stores for global state
└── api.ts          # Centralized API client
```

## Critical Integration Points

### Authentication Flow

1. Login via `api.login()` → sets token in localStorage + Axios headers
2. `useAuthStore.login()` → calls API + loads user profile
3. Protected routes check `isAuthenticated()` from Zustand store
4. 401 responses → auto-logout + redirect to `/login`

### Backtest Data Flow

- **Start backtest**: `BacktestRunner` → `api.runBacktest()` → triggers list refresh
- **List backtests**: `BacktestList` → `api.listBacktests()` → expects `{data: {backtests: []}}`
- **View details**: `BacktestDetails` → `api.getBacktest(runId)` → renders charts + trade tables
- **Real-time updates**: WebSocket connection for running backtests (see `api.connectBacktestSocket()`)

### Chart Visualization Patterns

- **Equity curve**: Line chart of cumulative P&L over trades
- **P&L by pair**: Bar chart showing performance per trading pair
- **Trade scatter**: Z-score vs P&L visualization for individual trades
- Use `ResponsiveContainer` wrapper for all Recharts components

## Backend API Expectations

- **Authentication**: POST `/api/v1/auth/login` → `{access_token, token_type}`
- **Backtests**: GET `/api/v1/backtests` → `{data: {backtests: BacktestRun[]}}`
- **Run backtest**: POST `/api/v1/backtests/run` with parameters: `start_date`, `end_date`, `num_pairs`, `zscore_threshold`, `stats_window`, `usd_per_trade`
- **WebSocket**: `/ws/backtest/{runId}?token={jwt}` for real-time progress

## Error Handling Patterns

- **API errors**: Extract `error.response?.data?.message` or fallback to `error.message`
- **Component errors**: Use `ErrorBoundary` class component (already implemented in `App.tsx`)
- **Console debugging**: Extensive logging with emoji prefixes (`🔐`, `📊`, `🔌`, `❌`) for easy filtering

When working on this codebase, always maintain the dark theme aesthetics, implement proper loading states, and follow the established API client patterns for consistency.
