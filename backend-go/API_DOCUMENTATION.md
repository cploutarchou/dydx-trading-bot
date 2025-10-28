# dYdX Trading Bot Backend - API Documentation

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Key Management API](#key-management-api)
  - [Create/Update Key](#createupdate-key)
  - [List Keys](#list-keys)
  - [Get Key Info](#get-key-info)
  - [Get Key with Secret](#get-key-with-secret)
  - [Delete Key](#delete-key)
- [Backtest API](#backtest-api)
  - [Get Candles](#get-candles)
  - [Get Positions](#get-positions)
  - [Get Trades](#get-trades)
- [Error Handling](#error-handling)

---

## Overview

The dYdX Trading Bot Backend is a Go-based REST API that manages:
- **dYdX Key Management**: Securely store and manage dYdX chain credentials
- **Backtest Data**: Access historical backtest data including candles, positions, and trades
- **User Authentication**: JWT-based authentication for all protected endpoints

### Base URL

```
http://localhost:8080/api/v1
```

### Content Type

All requests and responses use `application/json`.

---

## Authentication

### JWT Authentication

All endpoints except health checks require JWT authentication via Bearer token.

**Authorization Header Format:**
```
Authorization: Bearer <access_token>
```

**Token Types:**
- `access`: Short-lived token for API access (default: 30 minutes)
- `refresh`: Long-lived token for obtaining new access tokens (default: 7 days)

### Getting an Access Token

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password"
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_at": "2025-10-29T01:03:25Z",
    "token_type": "Bearer"
  },
  "timestamp": "2025-10-29T00:03:25Z"
}
```

---

## Key Management API

Securely manage dYdX chain credentials with encrypted storage.

### Create/Update Key

**Endpoint:** `POST /api/v1/keys/create`

**Description:** Create a new dYdX key or update an existing one for the specified network.

**Authorization:** Required (Bearer token)

**Request Body:**
```json
{
  "network": "testnet",
  "chain_address": "dydx1abc123...",
  "secret_phrase": "word1 word2 word3 ... word24"
}
```

**Parameters:**
- `network` (string, required): Either `"testnet"` or `"mainnet"`
- `chain_address` (string, required): Your dYdX chain address
- `secret_phrase` (string, required): Your dYdX mnemonic seed phrase (24 words)

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "network": "testnet",
    "chain_address": "dydx1abc123...",
    "is_active": true,
    "created_at": "2025-10-29T00:03:25Z",
    "updated_at": "2025-10-29T00:03:25Z"
  },
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Error Response (400):**
```json
{
  "success": false,
  "error": "Failed to create key: network must be 'testnet' or 'mainnet'",
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Example:**
```bash
curl -X POST http://localhost:8080/api/v1/keys/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "network": "testnet",
    "chain_address": "dydx1abc123def456...",
    "secret_phrase": "word1 word2 word3 ... word24"
  }'
```

---

### List Keys

**Endpoint:** `GET /api/v1/keys/list`

**Description:** Retrieve all active keys for the current user (without secrets).

**Authorization:** Required (Bearer token)

**Query Parameters:** None

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "keys": [
      {
        "id": 1,
        "network": "testnet",
        "chain_address": "dydx1abc123...",
        "is_active": true,
        "created_at": "2025-10-29T00:03:25Z",
        "updated_at": "2025-10-29T00:03:25Z"
      },
      {
        "id": 2,
        "network": "mainnet",
        "chain_address": "dydx1xyz789...",
        "is_active": true,
        "created_at": "2025-10-28T12:00:00Z",
        "updated_at": "2025-10-28T12:00:00Z"
      }
    ],
    "total": 2
  },
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Example:**
```bash
curl -X GET http://localhost:8080/api/v1/keys/list \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### Get Key Info

**Endpoint:** `GET /api/v1/keys/{network}`

**Description:** Get key information for a specific network (without secret).

**Authorization:** Required (Bearer token)

**Path Parameters:**
- `network` (string, required): Either `"testnet"` or `"mainnet"`

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "network": "testnet",
    "chain_address": "dydx1abc123...",
    "is_active": true,
    "created_at": "2025-10-29T00:03:25Z",
    "updated_at": "2025-10-29T00:03:25Z"
  },
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Error Response (404):**
```json
{
  "success": false,
  "error": "No key found for network: mainnet",
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Example:**
```bash
curl -X GET http://localhost:8080/api/v1/keys/testnet \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### Get Key with Secret

**Endpoint:** `GET /api/v1/keys/{network}/secret`

**Description:** Get full key with decrypted secret phrase (sensitive endpoint).

**Authorization:** Required (Bearer token)

**⚠️ Security Warning:** This endpoint returns your decrypted secret phrase. Only use over HTTPS in production.

**Path Parameters:**
- `network` (string, required): Either `"testnet"` or `"mainnet"`

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "network": "testnet",
    "chain_address": "dydx1abc123...",
    "secret_phrase": "word1 word2 word3 ... word24",
    "created_at": "2025-10-29T00:03:25Z",
    "updated_at": "2025-10-29T00:03:25Z"
  },
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Example:**
```bash
curl -X GET http://localhost:8080/api/v1/keys/testnet/secret \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### Delete Key

**Endpoint:** `DELETE /api/v1/keys/{network}`

**Description:** Delete (deactivate) a key for the current user.

**Authorization:** Required (Bearer token)

**Path Parameters:**
- `network` (string, required): Either `"testnet"` or `"mainnet"`

**Response (204 No Content):** No body

**Error Response (404):**
```json
{
  "success": false,
  "error": "No key found for network: mainnet",
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Example:**
```bash
curl -X DELETE http://localhost:8080/api/v1/keys/testnet \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Backtest API

Access historical backtest data including price candles, trading positions, and individual trades.

### Get Candles

**Endpoint:** `GET /api/v1/backtests/{run_id}/candles`

**Description:** Get historical candle data for a backtest run.

**Authorization:** Optional

**Path Parameters:**
- `run_id` (integer, required): Backtest run ID

**Query Parameters:**
- `market` (string, optional): Market symbol (e.g., "BTC-USD") - returns all markets if not specified
- `start_date` (string, optional): Start date in ISO format (YYYY-MM-DD)
- `end_date` (string, optional): End date in ISO format (YYYY-MM-DD)

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "run_id": 1,
    "candles": [
      {
        "market": "BTC-USD",
        "timestamp": "2025-09-20T00:00:00Z",
        "open": 45123.50,
        "high": 45234.75,
        "low": 45012.25,
        "close": 45189.00,
        "volume": 1234567.89
      }
    ],
    "count": 720,
    "markets": ["BTC-USD", "ETH-USD"]
  },
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Example:**
```bash
curl -X GET "http://localhost:8080/api/v1/backtests/1/candles?market=BTC-USD&start_date=2025-09-20&end_date=2025-10-20"
```

---

### Get Positions

**Endpoint:** `GET /api/v1/backtests/{run_id}/positions`

**Description:** Get trading positions from a backtest run.

**Authorization:** Optional

**Path Parameters:**
- `run_id` (integer, required): Backtest run ID

**Query Parameters:**
- `status` (string, optional): Filter by status - "OPEN", "CLOSED", or "ALL" (default: "ALL")
- `market_1` (string, optional): Filter by base market symbol
- `market_2` (string, optional): Filter by quote market symbol

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "run_id": 1,
    "positions": [
      {
        "position_id": 1,
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "entry_timestamp": "2025-09-20T12:00:00Z",
        "exit_timestamp": "2025-09-20T18:00:00Z",
        "entry_price_m1": 45123.50,
        "exit_price_m1": 45234.75,
        "entry_price_m2": 2534.12,
        "exit_price_m2": 2567.89,
        "hedge_ratio": 0.056,
        "entry_zscore": 1.85,
        "exit_zscore": 0.02,
        "pnl_m1_usd": 111.25,
        "pnl_m2_usd": -33.77,
        "total_pnl_usd": 77.48,
        "status": "CLOSED"
      }
    ],
    "count": 42,
    "open_count": 2,
    "closed_count": 40
  },
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Example:**
```bash
curl -X GET "http://localhost:8080/api/v1/backtests/1/positions?status=CLOSED&market_1=BTC-USD"
```

---

### Get Trades

**Endpoint:** `GET /api/v1/backtests/{run_id}/trades`

**Description:** Get individual trades from a backtest run (paginated).

**Authorization:** Optional

**Path Parameters:**
- `run_id` (integer, required): Backtest run ID

**Query Parameters:**
- `market_1` (string, optional): Filter by base market
- `market_2` (string, optional): Filter by quote market
- `skip` (integer, optional): Number of trades to skip for pagination (default: 0)
- `limit` (integer, optional): Maximum trades to return (1-500, default: 50)

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "run_id": 1,
    "trades": [
      {
        "trade_id": "trade_001",
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "entry_timestamp": "2025-09-20T12:00:00Z",
        "exit_timestamp": "2025-09-20T14:30:00Z",
        "entry_zscore": 1.82,
        "exit_zscore": 0.05,
        "entry_price_m1": 45123.50,
        "exit_price_m1": 45234.75,
        "entry_price_m2": 2534.12,
        "exit_price_m2": 2567.89,
        "hedge_ratio": 0.0562,
        "pnl_usd": 77.48,
        "pnl_pct": 0.77,
        "duration_hours": 2.5,
        "win": true
      }
    ],
    "count": 42,
    "total": 100,
    "skip": 0,
    "limit": 50
  },
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Example:**
```bash
curl -X GET "http://localhost:8080/api/v1/backtests/1/trades?market_1=BTC-USD&skip=0&limit=25"
```

---

## Error Handling

The API uses standard HTTP status codes and returns consistent error responses.

### Common Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 204 | No Content | Success with no response body |
| 400 | Bad Request | Invalid input or parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 404 | Not Found | Resource doesn't exist |
| 500 | Internal Server Error | Server error |

### Error Response Format

```json
{
  "success": false,
  "error": "Descriptive error message",
  "timestamp": "2025-10-29T00:03:25Z"
}
```

### Common Error Scenarios

**Missing Authorization Header:**
```json
{
  "success": false,
  "error": "missing authorization header",
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Invalid Token:**
```json
{
  "success": false,
  "error": "invalid token: token expired",
  "timestamp": "2025-10-29T00:03:25Z"
}
```

**Invalid Request Body:**
```json
{
  "success": false,
  "error": "Invalid request: network is required",
  "timestamp": "2025-10-29T00:03:25Z"
}
```

---

## Security Considerations

1. **HTTPS Only**: Always use HTTPS in production
2. **Secret Phrases**: Never log or expose secret phrases
3. **Token Storage**: Store JWT tokens securely on the client side
4. **Token Rotation**: Refresh tokens periodically
5. **Encryption**: All sensitive data is encrypted at rest
6. **Rate Limiting**: Consider implementing rate limiting for production
7. **CORS**: Configure CORS appropriately for your frontend domain

---

## Examples

### Complete Workflow

1. **Login and get tokens:**
```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'
```

2. **Create a dYdX key:**
```bash
curl -X POST http://localhost:8080/api/v1/keys/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -d '{
    "network": "testnet",
    "chain_address": "dydx1...",
    "secret_phrase": "word1 word2 ... word24"
  }'
```

3. **List all keys:**
```bash
curl -X GET http://localhost:8080/api/v1/keys/list \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

4. **Get backtest candles:**
```bash
curl -X GET "http://localhost:8080/api/v1/backtests/1/candles?market=BTC-USD" \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

## Support

For issues or questions, please refer to the main README or contact support.

