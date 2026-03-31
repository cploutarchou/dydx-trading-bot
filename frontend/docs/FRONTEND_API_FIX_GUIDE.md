# Frontend API Fix Guide (401/404)

This guide is the source of truth for frontend integration with backend auth and settings endpoints.

## 1) Correct Endpoints To Use

| Purpose | Method | Endpoint |
|---|---|---|
| Login | `POST` | `/api/v1/auth/login` |
| Refresh token | `POST` | `/api/v1/auth/refresh` |
| Get settings | `GET` | `/api/v1/settings` |
| Update settings | `PUT` | `/api/v1/settings` |
| Get keys list | `GET` | `/api/v1/keys/list` |
| Get strategies | `GET` | `/api/v1/strategies` |
| Get bots | `GET` | `/api/v1/bots` |
| Redis connectivity status (preferred existing route) | `POST` | `/api/v1/settings/test-connection` |
| Redis status compatibility route | `GET` | `/api/v1/redis/status` |
| Redis settings record | `GET` | `/api/v1/settings/redis` |

## 2) Auth Contract For Protected Endpoints

Protected endpoints require a valid **access token**.

Backend accepts token in this order:
1. `Authorization: Bearer <access_token>` (preferred)
2. `X-Authorization: Bearer <access_token>`
3. `X-Access-Token: <access_token>`
4. Cookie `access_token` (if browser sends credentials)
5. Query `?access_token=...` (debug fallback only)

If token is missing/invalid/expired, backend returns `401`.

## 3) Root Cause Of Reported Errors

- `401` on `/api/v1/strategies`, `/api/v1/bots`, `/api/v1/settings`, `/api/v1/keys/list` happened because requests had no auth token.
- `404` on `/api/v1/redis/status` happened because that route was not previously registered. A compatibility route now exists.

## 4) Frontend Implementation Examples

### Fetch (recommended pattern)

```javascript
const API_BASE = "http://localhost:8888";

export async function apiGet(path, accessToken) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    credentials: "include",
  });

  if (res.status === 401) {
    // trigger refresh flow, then retry once
  }

  return res.json();
}
```

### Axios interceptor

```javascript
import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8888",
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
```

### PowerShell (manual test)

```powershell
$token = "<ACCESS_TOKEN>"
Invoke-RestMethod -Method GET -Uri "http://localhost:8888/api/v1/keys/list" -Headers @{ Authorization = "Bearer $token" }
```

## 5) Refresh Flow (Frontend)

1. Login via `/api/v1/auth/login` and store access token from response.
2. On `401` with token-expired behavior, call `/api/v1/auth/refresh`.
3. Replace stored access token and retry original request once.
4. If refresh fails, force re-login.

## 6) Quick Troubleshooting Checklist

- Is request path exactly correct (`/api/v1/settings/redis`, not `/api/v1/redis/settings`)?
- Is `Authorization` header present on every protected call?
- Is token an **access token** (not refresh token)?
- If relying on cookies, is `credentials: "include"` / `withCredentials: true` enabled?
- Use backend debug endpoints when needed:
  - `GET /api/v1/debug/headers`
  - `GET /api/v1/debug/whoami` (requires auth)

## 7) Minimum Frontend Changes Required

1. Add centralized request interceptor/helper to always attach bearer token.
2. Replace old/mismatched Redis paths with the endpoints listed above.
3. Add one retry-on-refresh mechanism for `401` responses.
4. Validate all protected calls are made only after login token is available.

