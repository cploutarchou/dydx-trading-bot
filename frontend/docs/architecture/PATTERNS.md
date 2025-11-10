# Code Patterns & Conventions

Project-specific patterns and best practices for this codebase.

## State Management Patterns

### Zustand Store Pattern

All global state uses Zustand with persistence.

**Template:**

```typescript
// src/store/exampleStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ExampleStore {
  // State
  count: number;
  items: Item[];

  // Methods
  increment: () => void;
  addItem: (item: Item) => void;
  clear: () => void;
}

export const useExampleStore = create<ExampleStore>()(
  persist(
    (set, get) => ({
      count: 0,
      items: [],

      increment: () => set((state) => ({ count: state.count + 1 })),

      addItem: (item) =>
        set((state) => ({ items: [...state.items, item] })),

      clear: () => set({ count: 0, items: [] }),
    }),
    {
      name: 'example-store', // localStorage key
    }
  )
);
```

**Usage in Components:**

```typescript
const MyComponent = () => {
  const { count, increment, addItem } = useExampleStore();

  return (
    <div>
      <p>Count: {count}</p>
      <button onClick={increment}>Increment</button>
    </div>
  );
};
```

**Key Points:**

- Always use `const { create } from 'zustand'` (v5 named export)
- Wrap with `persist()` middleware for localStorage
- Use `set()` to update state
- Store name should match file name

---

## Component Patterns

### Functional Component with Props Interface

**Template:**

```typescript
interface MyComponentProps {
  title: string;
  onSubmit?: (data: FormData) => void;
  isLoading?: boolean;
}

export const MyComponent: React.FC<MyComponentProps> = ({
  title,
  onSubmit,
  isLoading = false,
}) => {
  return (
    <div className="bg-slate-900 p-4">
      <h2 className="text-white text-xl">{title}</h2>
      <button
        onClick={() => onSubmit?.({ /* data */ })}
        disabled={isLoading}
        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
      >
        {isLoading ? 'Loading...' : 'Submit'}
      </button>
    </div>
  );
};
```

**Key Points:**

- Use `React.FC<Props>` for type safety
- Define `Props` interface above component
- Use destructuring for props
- Provide default values with `= defaultValue`

---

### Data Fetching Component Pattern

**Template:**

```typescript
interface FetchComponentProps {
  id: string;
}

export const FetchComponent: React.FC<FetchComponentProps> = ({ id }) => {
  const [data, setData] = useState<DataType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await api.getData(id);
        setData(response);

        console.log('📊 Data fetched:', response);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(message);

        console.error('❌ Failed to fetch:', message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader className="animate-spin" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-red-900 border border-red-700 p-4 rounded">
        <p className="text-white">Error: {error}</p>
      </div>
    );
  }

  // Success state
  if (!data) {
    return (
      <div className="bg-slate-800 p-4 rounded">
        <p className="text-slate-300">No data found</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 p-4">
      {/* Render data */}
    </div>
  );
};
```

**Key Points:**

- Always have `loading`, `error`, and data states
- Use `useEffect` for async operations
- Catch and display errors
- Show loading spinner
- Show empty state if no data
- Use emoji-prefixed console logs

---

### Form Component Pattern

**Template:**

```typescript
interface FormData {
  email: string;
  password: string;
}

interface LoginFormProps {
  onSubmit: (data: FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string;
}

export const LoginForm: React.FC<LoginFormProps> = ({
  onSubmit,
  isLoading = false,
  error,
}) => {
  const [formData, setFormData] = useState<FormData>({
    email: '',
    password: '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.currentTarget;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate
    if (!formData.email || !formData.password) {
      console.warn('⚠️ Form validation failed');
      return;
    }

    try {
      await onSubmit(formData);
      // Clear form on success
      setFormData({ email: '', password: '' });
    } catch (err) {
      console.error('❌ Form submission failed:', err);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-900 border border-red-700 p-3 rounded">
          <p className="text-white text-sm">{error}</p>
        </div>
      )}

      <div>
        <label className="block text-white mb-2">Email</label>
        <input
          type="email"
          name="email"
          value={formData.email}
          onChange={handleChange}
          className="w-full bg-slate-800 border border-slate-600 text-white p-2 rounded"
          disabled={isLoading}
          required
        />
      </div>

      <div>
        <label className="block text-white mb-2">Password</label>
        <input
          type="password"
          name="password"
          value={formData.password}
          onChange={handleChange}
          className="w-full bg-slate-800 border border-slate-600 text-white p-2 rounded"
          disabled={isLoading}
          required
        />
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold py-2 rounded"
      >
        {isLoading ? 'Signing in...' : 'Sign In'}
      </button>
    </form>
  );
};
```

**Key Points:**

- Use `useState` for form data
- Validate before submission
- Handle loading state
- Show error messages
- Clear form on success
- Use `preventDefault()` on form submit

---

## Styling Patterns

### Dark Theme Colors

**Background:**

```typescript
// Main background
className="bg-slate-900"    // #0f172a

// Secondary background
className="bg-slate-800"    // #1e293b

// Hover state
className="hover:bg-slate-700"  // #334155

// Border
className="border-slate-600"    // #475569
className="border-slate-700"    // #334155
```

**Text Colors:**

```typescript
// Primary text (bright)
className="text-white"      // #ffffff

// Secondary text (muted)
className="text-slate-300"  // #cbd5e1
className="text-slate-400"  // #94a3b8

// Financial colors
className="text-green-400"  // Profits, positive +$1,000
className="text-red-400"    // Losses, negative -$500
```

**Buttons:**

```typescript
// Primary button
className="bg-blue-600 hover:bg-blue-700 text-white"

// Secondary button
className="bg-slate-700 hover:bg-slate-600 text-slate-100"

// Danger button
className="bg-red-600 hover:bg-red-700 text-white"

// Disabled state
className="disabled:opacity-50 disabled:cursor-not-allowed"
```

**Cards/Containers:**

```typescript
className="bg-slate-900 border border-slate-700 rounded p-4"
```

**Example Component:**

```typescript
<div className="bg-slate-900 border border-slate-700 rounded p-6 space-y-4">
  <h2 className="text-white text-lg font-semibold">Title</h2>
  <p className="text-slate-300">Description</p>

  <div className="flex items-center justify-between">
    <span className="text-slate-400">Label</span>
    <span className="text-green-400 font-semibold">+$1,000</span>
  </div>

  <button className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded">
    Action
  </button>
</div>
```

---

### Loading States

All data-fetching components must show loading spinner:

```typescript
import { Loader } from 'lucide-react';

if (loading) {
  return (
    <div className="flex items-center justify-center p-8">
      <Loader className="animate-spin text-blue-400" size={32} />
    </div>
  );
}
```

---

### Error States

All components must show error UI:

```typescript
if (error) {
  return (
    <div className="bg-red-900 border border-red-700 rounded p-4">
      <h3 className="text-white font-semibold mb-2">Error</h3>
      <p className="text-slate-300 text-sm">{error}</p>
    </div>
  );
}
```

---

## API Client Patterns

### Adding New Endpoint

**Step 1: Define Interface**

```typescript
// In src/api.ts
interface BacktestParams {
  start_date: string;
  end_date: string;
  num_pairs: number;
  zscore_threshold: number;
  stats_window: number;
  usd_per_trade: number;
}

interface BacktestResponse {
  run_id: string;
  status: 'running' | 'completed' | 'failed';
}
```

**Step 2: Add Method to ApiClient**

```typescript
class ApiClient {
  // ... existing methods ...

  async runBacktest(params: BacktestParams): Promise<BacktestResponse> {
    try {
      console.log('📊 Starting backtest:', params);

      const response = await this.client.post<BacktestResponse>(
        '/backtests/run',
        params
      );

      console.log('📊 Backtest started:', response.data);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to start backtest:', error);
      throw error;
    }
  }
}
```

**Step 3: Use in Component**

```typescript
try {
  const result = await api.runBacktest(params);
  console.log('✅ Backtest result:', result);
  setBacktestId(result.run_id);
} catch (error) {
  const message = error instanceof Error ? error.message : 'Unknown error';
  setError(message);
}
```

**Key Points:**

- Define TypeScript interfaces first
- Use console logs with emojis (📊, 🔐, ✅, ❌)
- Always catch and log errors
- Return typed responses
- Handle both `response.data` and `response.data.data` patterns

---

### Error Handling

**Pattern for extracting error message:**

```typescript
const handleRequest = async () => {
  try {
    const data = await api.someMethod();
  } catch (error) {
    // Extract error message
    let message: string;

    if (error instanceof Error) {
      message = error.message;
    } else if (error.response?.data?.message) {
      message = error.response.data.message;
    } else if (error.response?.data?.error) {
      message = error.response.data.error;
    } else {
      message = 'An error occurred';
    }

    console.error('❌ Request failed:', message);
    setError(message);
  }
};
```

---

## Authentication Patterns

### Protected Route

**Template:**

```typescript
// src/components/ProtectedRoute.tsx
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/auth';

export const ProtectedRoute = () => {
  const { isAuthenticated } = useAuthStore();

  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};
```

**Usage:**

```typescript
<Routes>
  <Route path="/login" element={<Login />} />
  <Route element={<ProtectedRoute />}>
    <Route path="/dashboard" element={<Dashboard />} />
    <Route path="/backtest/:id" element={<BacktestDetails />} />
  </Route>
</Routes>
```

---

### Login Flow

```typescript
const LoginPage = () => {
  const navigate = useNavigate();
  const { login, error, loading } = useAuthStore();

  const handleSubmit = async (email: string, password: string) => {
    try {
      await login(email, password);
      // Store login automatically sets token in Axios
      navigate('/dashboard');
    } catch (err) {
      // Error displayed from store
      console.error('❌ Login failed:', err);
    }
  };

  return (
    <LoginForm
      onSubmit={handleSubmit}
      isLoading={loading}
      error={error}
    />
  );
};
```

---

## Console Logging Patterns

Use emoji prefixes for easy filtering:

```typescript
console.log('🔐 Auth event:', user);       // Authentication
console.log('📊 Data received:', backtest); // Data/API
console.log('🔌 WebSocket event:', msg);   // Network/WebSocket
console.log('✅ Success:', result);        // Success
console.warn('⚠️ Warning:', issue);        // Warning
console.error('❌ Error:', error);         // Error
```

**Filter in DevTools:** `Ctrl+Shift+K` then type emoji prefix

---

## TypeScript Patterns

### Props Interface

```typescript
// Always define above component
interface ComponentProps {
  title: string;
  count: number;
  onClose: () => void;
  items?: string[];  // optional
}

export const Component: React.FC<ComponentProps> = ({ ... }) => {
  // ...
};
```

### API Response Types

```typescript
interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

interface BacktestRun {
  run_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  results?: BacktestResults;
}
```

### Union Types for Status

```typescript
type BacktestStatus = 'pending' | 'running' | 'completed' | 'failed';

const getStatusColor = (status: BacktestStatus): string => {
  switch (status) {
    case 'completed':
      return 'text-green-400';
    case 'failed':
      return 'text-red-400';
    case 'running':
      return 'text-blue-400';
    default:
      return 'text-slate-400';
  }
};
```

---

## Performance Patterns

### Memoization for Expensive Components

```typescript
const ExpensiveChart = React.memo(
  ({ data }: { data: DataPoint[] }) => {
    return (
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          {/* Chart config */}
        </LineChart>
      </ResponsiveContainer>
    );
  }
);
```

### useCallback for Event Handlers

```typescript
const ListComponent = ({ items, onItemClick }: Props) => {
  const handleClick = useCallback(
    (id: string) => {
      onItemClick(id);
    },
    [onItemClick]
  );

  return (
    <ul>
      {items.map((item) => (
        <li key={item.id} onClick={() => handleClick(item.id)}>
          {item.name}
        </li>
      ))}
    </ul>
  );
};
```

### useMemo for Expensive Calculations

```typescript
const Dashboard = ({ backtests }: Props) => {
  const statistics = useMemo(() => {
    return {
      totalPnL: backtests.reduce((sum, b) => sum + (b.pnl || 0), 0),
      winRate: calculateWinRate(backtests),
    };
  }, [backtests]);

  return <div>{statistics.totalPnL}</div>;
};
```

---

## File Organization

### Component File Structure

```
src/components/BacktestRunner.tsx
├─ Imports
├─ Interface definitions
├─ Component declaration
├─ Hooks (useState, useEffect, etc)
├─ Event handlers
├─ Render logic
└─ Export

Example:
───────────────────────────────
import React, { useState } from 'react';
import { api } from '../api';

interface Props {
  onBacktestStarted?: () => void;
}

export const BacktestRunner: React.FC<Props> = ({ onBacktestStarted }) => {
  const [formData, setFormData] = useState(...);

  const handleSubmit = async (...) => {...};

  return (...);
};
```

### Store File Structure

```
src/store/auth.ts
├─ Interface definitions (AuthStore)
├─ Create Zustand store
├─ Export named hook
└─ Usage documentation

Example:
───────────────────────────────
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthStore {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
}

export const useAuthStore = create<AuthStore>()(
  persist((set) => ({
    user: null,
    login: async (...) => {...},
  }), { name: 'auth-store' })
);
```

---

## Common Mistakes to Avoid

### ❌ Don't Use Default Export from Zustand v5

```typescript
// WRONG - will fail in v5
import create from 'zustand';

// RIGHT - use named export
import { create } from 'zustand';
```

### ❌ Don't Forget Loading/Error States

```typescript
// WRONG - no loading state
const MyComponent = () => {
  const [data, setData] = useState(null);
  return <div>{data}</div>;
};

// RIGHT - complete state handling
const MyComponent = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  if (loading) return <Loader />;
  if (error) return <Error />;
  return <div>{data}</div>;
};
```

### ❌ Don't Mutate State Directly

```typescript
// WRONG
set((state) => {
  state.items.push(newItem);
  return state;
});

// RIGHT
set((state) => ({
  items: [...state.items, newItem],
}));
```

### ❌ Don't Skip Error Handling in API Calls

```typescript
// WRONG
const data = await api.getData();
setData(data);

// RIGHT
try {
  const data = await api.getData();
  setData(data);
} catch (error) {
  setError(error.message);
}
```

---

## See Also

- [README.md](README.md) - Architecture overview
- [DATA_FLOW.md](DATA_FLOW.md) - Component interactions
- [API_INTEGRATION.md](API_INTEGRATION.md) - API details
