# Backend Import Error Fix

## Problem

When starting the backend with Uvicorn, an ImportError occurred:

```
ImportError: cannot import name 'HTTPAuthCredentials' from 'fastapi.security'
```

## Root Cause

The `backend/main.py` was trying to import `HTTPAuthCredentials` directly from `fastapi.security`, but this class is not directly exported from that module in the version of FastAPI being used (0.104.1).

## Solution

Changed the import statement to use `HTTPAuthorizationCredentials` instead, which is the correct export from `fastapi.security`:

**File**: `backend/main.py`

**Before**:

```python
from fastapi.security import HTTPAuthCredentials, HTTPBearer
```

**After**:

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
```

**Updated usages** (2 locations):

- Line 119: `async def get_current_user()` - Changed parameter type
- Line 208: `async def refresh_token()` - Changed parameter type

## Testing

Verified the fix with:

1. ✅ Direct import test: `from fastapi.security import HTTPAuthorizationCredentials`
2. ✅ Backend module import: `from backend.main import app`
3. ✅ Uvicorn config loader: `Config(app=app)` succeeds

## Running the Backend

Now you can start the backend with:

```bash
cd /Users/chris/workspace/dydx-trading-bot
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the quick start script:

```bash
./scripts/dev-start.sh
```

## Related Files

- `backend/main.py` - Contains the FastAPI app and auth endpoints
- `backend/auth.py` - JWT token handling
- `backend/requirements.txt` - Dependency specifications
