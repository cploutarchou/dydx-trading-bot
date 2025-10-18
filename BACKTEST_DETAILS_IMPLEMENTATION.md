# Backtest Details Page Implementation

## Overview

The BacktestDetails page is a comprehensive visualization component that displays detailed backtest results with charts, trade breakdowns, and performance metrics. It's accessed via `/backtest/{runId}` and provides in-depth analysis of individual backtest executions.

## Architecture

### Data Flow

```
BacktestDetails.tsx (React Component)
    ↓ useParams extracts runId
    ↓ useEffect calls api.getBacktest(runId)
    ↓ Backend endpoint GET /api/v1/backtests/{run_id}
    ↓ Database queries BacktestRun + BacktestResult + TradeLog
    ↓ Response includes run metrics + pair results + all trades
    ↓ Component generates derived datasets
    ↓ Charts render with Recharts library
```

### Backend Response Structure

```json
{
  "success": true,
  "data": {
    "id": 1,
    "run_id": "uuid-string",
    "status": "completed",
    "total_trades": 45,
    "profitable_trades": 28,
    "win_rate": 0.62,
    "total_pnl_usd": 1234.56,
    "sharpe_ratio": 1.45,
    "max_drawdown": 0.18,
    "starting_balance": 1000.0,
    "ending_balance": 2234.56,
    "results": [
      {
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "total_trades": 15,
        "pnl_usd": 500.00,
        "sharpe_ratio": 1.2,
        "trades": [
          {
            "trade_number": 1,
            "entry_timestamp": "2025-10-17T10:00:00Z",
            "exit_timestamp": "2025-10-17T11:30:00Z",
            "entry_price_1": 45000,
            "entry_price_2": 3000,
            "exit_price_1": 45500,
            "exit_price_2": 3050,
            "pnl_usd": 125.50,
            "entry_zscore": 1.8,
            "exit_zscore": 0.1
          }
        ]
      }
    ],
    "all_trades": [...]  // Flattened array of all trades
  }
}
```

## Component Structure

### Page Layout (Top to Bottom)

```
┌─────────────────────────────────────────────┐
│  Header (Title, Date Range, Status Badge)   │
├─────────────────────────────────────────────┤
│  Top Metrics (4 columns)                    │
│  • Total Trades | Win Rate | Total PnL | Sharpe │
├─────────────────────────────────────────────┤
│  Charts Section (2 columns)                 │
│  ┌──────────────────┬──────────────────┐    │
│  │ Equity Curve     │ P&L by Pair      │    │
│  │ (LineChart)      │ (BarChart)       │    │
│  └──────────────────┴──────────────────┘    │
├─────────────────────────────────────────────┤
│  Risk Metrics (4 columns)                   │
│  • Max Drawdown | Profit Factor | Winning Trades │
├─────────────────────────────────────────────┤
│  Pair Selection (Buttons)                   │
│  [BTC/ETH] [ETH/SOL] [SOL/ADA] ...         │
├─────────────────────────────────────────────┤
│  Trade Performance Chart (if pair selected) │
│  (ScatterChart showing individual trades)   │
├─────────────────────────────────────────────┤
│  Trade Breakdown Table                      │
│  (Detailed entry/exit prices, P&L for each) │
└─────────────────────────────────────────────┘
```

### Key Features

#### 1. **Equity Curve Chart**

- **Type**: LineChart (Recharts)
- **Data**: Cumulative account balance over trades
- **Calculation**:

  ```typescript
  balance = starting_balance
  for each trade:
      balance += trade.pnl_usd
  ```

- **Visual**: Blue line showing account growth
- **Tooltip**: Shows exact balance on hover

#### 2. **P&L by Pair Chart**

- **Type**: BarChart (Recharts)
- **Data**: Total P&L for each market pair tested
- **Color**: Green for positive, red for negative (via Tailwind)
- **Interaction**: Pair buttons below allow filtering to see individual trades

#### 3. **Trade Performance Scatter Plot**

- **Type**: ScatterChart (Recharts)
- **Data**: One point per trade (X=trade#, Y=P&L USD)
- **Visual**: Purple dots, sized by trade size
- **Interactive**: Hover shows trade details

#### 4. **Trade Breakdown Table**

- **Columns**:
  - Trade # (sequential number)
  - Entry Time (ISO datetime)
  - Exit Time (ISO datetime or '-')
  - Entry Z-Score (3 decimal places)
  - Exit Z-Score (3 decimal places)
  - P&L ($) (color-coded green/red)
- **Row Coloring**:
  - Green background for winning trades
  - Red background for losing trades
- **Sorting**: Chronological order (entry_timestamp)
- **Pagination**: All trades from selected pair shown

### Data Transformations

#### Equity Curve Generation

```typescript
const generateEquityCurveData = () => {
  let balance = backtest.starting_balance;
  const data = [{ timestamp: 'Start', balance }];
  
  backtest.all_trades.forEach((trade, idx) => {
    balance += trade.pnl_usd;
    data.push({
      timestamp: `Trade ${idx + 1}`,
      balance,
    });
  });
  
  return data;
};
```

#### P&L by Pair Generation

```typescript
const generatePnlByPairData = () => {
  return backtest.results.map((result) => ({
    pair: `${result.market_1.split('-')[0]}/${result.market_2.split('-')[0]}`,
    pnl: result.pnl_usd,
    trades: result.total_trades,
  }));
};
```

#### Trade Scatter Generation

```typescript
const generateTradeScatterData = () => {
  return selectedResult.trades.map((trade, idx) => ({
    tradeNumber: idx + 1,
    pnl: trade.pnl_usd,
    zscore: trade.entry_zscore,
  }));
};
```

## TypeScript Interfaces

### Main Data Structure

```typescript
interface BacktestData {
  id: number;
  run_id: string;
  status: 'running' | 'completed' | 'failed';
  created_at: string;
  start_date: string;
  end_date: string;
  num_pairs: number;
  total_markets: number;
  duration_seconds: number;
  total_trades: number;
  profitable_trades: number;
  win_rate: number;
  total_pnl: number;
  total_pnl_usd: number;
  sharpe_ratio: number;
  max_drawdown: number;
  profit_factor: number;
  starting_balance: number;
  ending_balance?: number;
  results: BacktestResult[];  // Pair results
  all_trades: Trade[];        // Flattened trades
}
```

### Pair Result

```typescript
interface BacktestResult {
  market_1: string;           // e.g., "BTC-USD"
  market_2: string;           // e.g., "ETH-USD"
  total_trades: number;
  profitable_trades: number;
  win_rate: number;
  pnl: number;
  pnl_usd: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  profit_factor?: number;
  trades: Trade[];            // Individual trades for this pair
}
```

### Individual Trade

```typescript
interface Trade {
  trade_number: number;
  entry_timestamp: string;
  exit_timestamp?: string;
  entry_price_1: number;
  entry_price_2: number;
  exit_price_1?: number;
  exit_price_2?: number;
  quantity_1: number;
  quantity_2: number;
  side_1: string;             // "BUY" or "SELL"
  side_2: string;             // Opposite direction
  pnl?: number;
  pnl_usd?: number;
  entry_zscore?: number;
  exit_zscore?: number;       // Should cross zero for exit
}
```

## Styling

### Tailwind CSS Classes Used

**Layout**:

- `min-h-screen bg-slate-50` - Full page background
- `max-w-7xl mx-auto` - Content width constraint
- `grid grid-cols-1 lg:grid-cols-2` - Responsive 2-column layout

**Cards**:

- `bg-white p-6 rounded-lg shadow` - Standard card styling
- `hover:shadow-md transition` - Interactive hover effect

**Metrics Display**:

- `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4` - Responsive metric cards
- `text-3xl mb-2` for icons
- `text-2xl font-bold` for large numbers

**Buttons**:

- `px-4 py-2 rounded-lg font-medium transition` - Standard button
- `bg-blue-600 text-white` for active state
- `bg-slate-100 text-slate-700 hover:bg-slate-200` for inactive

**Status Badges**:

- `bg-green-100 text-green-700` for completed
- `bg-yellow-100 text-yellow-700` for running

**Table**:

- `bg-green-50` for winning trades (positive PnL)
- `bg-red-50` for losing trades (negative PnL)
- `text-green-700` for positive P&L text
- `text-red-700` for negative P&L text

## Dependencies

### npm Packages

```json
{
  "recharts": "^2.10.0",
  "react": "^18.2.0",
  "react-router-dom": "^6.15.0",
  "lucide-react": "^0.263.0"
}
```

**Recharts Components Used**:

- `LineChart` - Equity curve visualization
- `BarChart` - P&L by pair
- `ScatterChart` - Trade performance
- `Line`, `Bar`, `Scatter` - Chart types
- `XAxis`, `YAxis` - Axes
- `CartesianGrid` - Background grid
- `Tooltip` - Hover information
- `ResponsiveContainer` - Responsive sizing

## State Management

```typescript
const [backtest, setBacktest] = useState<BacktestData | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);
```

- **backtest**: Full backtest data from API
- **loading**: Fetch in progress
- **error**: API error message
- **selectedResult**: Currently selected pair for detailed view

## API Integration

### Endpoint: GET /api/v1/backtests/{run_id}

**Request**:

```typescript
const response = await api.getBacktest(runId);
```

**Auth**: JWT Bearer token (added by interceptor)

**Response**:

```typescript
interface ApiResponse {
  success: boolean;
  message: string;
  data: BacktestData;
  timestamp: string;
}
```

**Errors**:

- 401: Unauthorized (token expired)
- 403: Forbidden (not owner of backtest)
- 404: Backtest not found

## Performance Optimizations

1. **Data Transformations**: Pre-calculated during render
   - Equity curve: O(n) where n = number of trades
   - P&L by pair: O(m) where m = number of pairs
   - Trade scatter: O(k) where k = trades in selected pair

2. **Recharts**: ResponsiveContainer avoids layout thrashing

3. **Table Rendering**: All rows rendered at once (not virtualized)
   - Acceptable for typical 20-50 trades per pair

4. **Chart Rendering**: isAnimationActive={false} on expensive animations

## Future Enhancements

### Priority 1 - Quick Wins

1. **Download CSV** export of trade data
2. **Copy trade details** to clipboard
3. **Statistics summary card** below title (best/worst trade, avg duration)

### Priority 2 - Advanced Features

1. **Real-time progress** updates via WebSocket during backtest execution
2. **Trade replay animation** - visualize trades in real-time
3. **Rolling statistics** chart (sharpe over time, drawdown over time)
4. **Trade correlation matrix** - heatmap of trade relationships

### Priority 3 - Professional Features

1. **Custom date range selector** for "zoom in" on equity curve
2. **Multiple backtest comparison** side-by-side
3. **Risk profile analyzer** (tail risk, VaR, CVaR)
4. **Strategy optimization suggestions** based on historical trades

## Testing Checklist

- [ ] Load backtest with 0 trades (edge case)
- [ ] Load backtest with 1 pair (single result)
- [ ] Load backtest with 10+ pairs (performance test)
- [ ] Check responsive layout on mobile (1 column)
- [ ] Verify colors for extreme values (very high/low P&L)
- [ ] Test with expired JWT (redirect to login)
- [ ] Test with unauthorized user (403 error)
- [ ] Verify chart tooltips on hover
- [ ] Test pair selection buttons
- [ ] Verify table sorting by entry_timestamp

## Troubleshooting

### Charts Not Rendering

**Issue**: Recharts requires valid numeric data
**Solution**: Verify data has required fields (timestamp, balance, etc.)

### Table Showing Empty

**Issue**: Trades array empty or not included in response
**Solution**: Check backend endpoint includes trades in formatted_results

### Tooltip Shows NaN

**Issue**: Type casting issue with formatter
**Solution**: Use `(value: any)` and cast to `(value as number).toFixed(2)`

### Styling Not Applied

**Issue**: Tailwind classes not compiled
**Solution**: Ensure `postcss.config.js` includes tailwindcss plugin

## Code References

- Component: `/Users/chris/workspace/dydx-trading-bot/frontend/src/pages/BacktestDetails.tsx` (414 lines)
- API Client: `/Users/chris/workspace/dydx-trading-bot/frontend/src/api.ts` (line 67-69)
- Backend Endpoint: `/Users/chris/workspace/dydx-trading-bot/backend/main.py` (lines 263-349)
- Database Models: `/Users/chris/workspace/dydx-trading-bot/backend/database.py`
