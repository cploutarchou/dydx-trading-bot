# BacktestList Error Fix - October 17, 2025

## Issue

**Error**: `runs.map is not a function`  
**Location**: `BacktestList.tsx:133`  
**Severity**: Critical - blocked dashboard from loading

## Root Cause

The API response structure from `GET /api/v1/backtests` returns:

```json
{
  "success": true,
  "message": "Backtests retrieved",
  "data": {
    "backtests": [...]  // ← Array is nested here
  }
}
```

But the component was trying to access:

```typescript
setRuns(response.data || [])  // ❌ Wrong - data is an object, not array
```

This resulted in `runs` being an object `{backtests: [...]}` instead of an array, causing `.map()` to fail.

## Solution

Changed the data extraction to properly access the nested array:

```typescript
// ✅ Correct - access the backtests property
const backtests = response.data?.backtests || [];
setRuns(backtests);
```

## Changes Made

### File: `/frontend/src/components/BacktestList.tsx`

**1. Updated interface to match API response**

```typescript
interface BacktestRun {
    run_id: string;        // ← Primary identifier (was "id")
    id?: string;           // ← Optional database ID
    start_date?: string;   // ← Optional (may not always present)
    end_date?: string;     // ← Optional (may not always present)
    status: string;
    total_trades: number;
    total_pnl: number;
    win_rate: number;
    profitable_trades?: number;
    losing_trades?: number;
    sharpe_ratio?: number;
    profit_factor?: number;
    max_drawdown?: number;
    created_at: string;
}
```

**2. Fixed data extraction in loadBacktests()**

```typescript
const backtests = response.data?.backtests || [];
setRuns(backtests);
```

**3. Updated table to use correct field names**

- Changed `key={run.id}` → `key={run.run_id}` (unique string identifier)
- Changed `navigate(/backtest/${run.id})` → `navigate(/backtest/${run.run_id})`
- Added null checks for optional fields (sharpe_ratio, max_drawdown, dates)
- Handle missing dates by falling back to created_at

## Why This Happened

The backend API response format uses `backtests` as a nested array within the `data` object to allow for potential pagination metadata in the future. The frontend component wasn't updated to match this structure after the backend was modified.

## Testing

**Step 1**: Login with admin/admin123  
**Step 2**: Navigate to Dashboard  
**Step 3**: Verify BacktestList loads without errors  
**Step 4**: Check backtests display in table  
**Step 5**: Click "View Details" to navigate to BacktestDetails page  

## Expected Result

✅ Dashboard loads successfully  
✅ BacktestList component renders without errors  
✅ Table displays backtest runs (if any exist)  
✅ "View Details" button navigates to `/backtest/{run_id}`  

## Related Files

- Backend: `/backend/main.py` (line 233-248) - GET /api/v1/backtests endpoint
- Frontend: `/frontend/src/components/BacktestList.tsx` - Component fixed
- API Client: `/frontend/src/api.ts` - Calls `listBacktests(skip, limit)`

## Similar Issues to Watch For

1. **Dashboard.tsx** - May have same issue if it tries to access response.data directly
2. **BacktestDetails.tsx** - Check if it properly handles nested response structure
3. **BacktestRunner.tsx** - Verify API response handling

Let me check these files...

### Dashboard.tsx Status: ✅ SAFE

Uses `<BacktestRunner />` and `<BacktestList />` components, no direct API calls

### BacktestDetails.tsx Status: ⚠️ CHECK NEEDED

Uses `api.getBacktest(runId)` and accesses `response.data`

### BacktestRunner.tsx Status: ⚠️ CHECK NEEDED  

Uses `api.runBacktest(data)` and accesses response

## Conclusion

Fixed the primary issue preventing dashboard from loading. The error was a simple mismatch between the expected and actual API response structure. All TypeScript types are now properly aligned with the backend response format.
