# Quick Start Guide - dYdX Trading Bot

**Get your bot trading in 5 minutes!** 🚀

> **⚠️ IMPORTANT:** This bot now includes **JWT Authentication**. See [AUTHENTICATION_GUIDE.md](AUTHENTICATION_GUIDE.md) for complete setup details.

---

## Prerequisites

1. **Python 3.10+** installed
2. **dYdX testnet account** with funds (get from faucet)
3. **Wallet credentials** (address + mnemonic)
4. **Authentication setup** (included in this guide)

---

## 5-Minute Setup

### 1. Setup Authentication (Terminal 1)

```bash
cd /home/chris/workspace/dydx-trading-bot/bot
source venv/bin/activate

# Initialize authentication database
python init_auth_db.py
```

Expected output:

```text
============================================================
dYdX Trading Bot - Authentication Database Setup
============================================================
INFO: 🚀 Starting database initialization...
INFO: ✅ Database tables created successfully
INFO: 👤 Creating default admin user...
INFO: ✅ Default admin user created:
INFO:    Username: admin
INFO:    Password: admin123
INFO:    Email: admin@localhost
============================================================
🎉 SETUP COMPLETE!
============================================================
```

### 2. Start API Server (Terminal 1)

```bash
# Start the authenticated API server (port 8000)
python start_api.py
```

Expected output:

```text
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     JWT Authentication enabled
INFO:     Swagger UI available at http://localhost:8000/docs
```

### 3. Login and Get Token (Terminal 2)

```bash
# Login with default admin credentials
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

Save the `access_token` from the response:

```bash
# Export token for subsequent requests
export TOKEN="your_access_token_here"
```

### 4. Create Bot Instance (Terminal 2)

```bash
# Replace with your actual credentials
export ADDRESS="dydx1a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9"
export MNEMONIC="word1 word2 word3 ... word12"

# Now use authenticated requests (note port 8000 and Authorization header)
curl -X POST http://localhost:8000/api/v1/bots \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "instance_id": "my-first-bot",
    "instance_name": "My First Bot",
    "credentials": {
      "address": "'$ADDRESS'",
      "mnemonic": "'$MNEMONIC'"
    },
    "trading_params": {
      "is_testnet": true,
      "zscore_threshold": 1.5,
      "usd_per_trade": 10.0,
      "find_cointegrated_pairs": true,
      "manage_exits": true,
      "place_trades": true
    }
  }'
```

### 5. Start Trading

```bash
# All requests now require authentication
curl -X POST http://localhost:8000/api/v1/bots/my-first-bot/start \
  -H "Authorization: Bearer $TOKEN"

# Wait 5-10 seconds and check status
sleep 5
curl http://localhost:8000/api/v1/bots/my-first-bot \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Monitor Live

```bash
# Get bot stats (authenticated)
curl http://localhost:8000/api/v1/bots/my-first-bot/stats \
  -H "Authorization: Bearer $TOKEN"

# Get trades (authenticated)
curl http://localhost:8000/api/v1/bots/my-first-bot/trades \
  -H "Authorization: Bearer $TOKEN"

# Or use Swagger UI: http://localhost:8000/docs
# Click "Authorize" button and enter: Bearer your_token_here
```

### 7. Stop Trading

```bash
curl -X POST http://localhost:8000/api/v1/bots/my-first-bot/stop \
  -H "Authorization: Bearer $TOKEN"
```

---

## What Just Happened?

1. **Authentication System** initialized with default admin user
2. **Secure API Server** started on port 8000 with JWT authentication
3. **Login Process** obtained Bearer token for API access
4. **Bot Instance** created with your credentials and trading parameters (authenticated)
5. **Bot Process** started and:
   - Connected to dYdX
   - Analyzed available trading pairs
   - Found cointegrated pairs (correlated pairs suitable for arbitrage)
   - Started placing trades when signal (Z-score) reached threshold
6. **Real-time monitoring** available via authenticated REST API and WebSocket

> **🔒 Security Note:** All bot endpoints now require Bearer token authentication for enhanced security.

---

## Key Commands

### Authentication

```bash
# Login (get Bearer token)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Set token for subsequent requests
export TOKEN="your_access_token_here"
```

### Create Bot

```bash
curl -X POST http://localhost:8000/api/v1/bots \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{ ... }'
```

### List Bots

```bash
curl http://localhost:8000/api/v1/bots \
  -H "Authorization: Bearer $TOKEN"
```

### Get Bot Status

```bash
curl http://localhost:8000/api/v1/bots/{instance_id} \
  -H "Authorization: Bearer $TOKEN"
```

### Start Bot

```bash
curl -X POST http://localhost:8000/api/v1/bots/{instance_id}/start \
  -H "Authorization: Bearer $TOKEN"
```

### Stop Bot

```bash
curl -X POST http://localhost:8000/api/v1/bots/{instance_id}/stop \
  -H "Authorization: Bearer $TOKEN"
```

### Get Stats

```bash
curl http://localhost:8000/api/v1/bots/{instance_id}/stats \
  -H "Authorization: Bearer $TOKEN"
```

### Get Trade History

```bash
curl http://localhost:8000/api/v1/bots/{instance_id}/trades \
  -H "Authorization: Bearer $TOKEN"
```

---

## Understanding the Trading Parameters

| Parameter | What It Does | Good Values |
|-----------|-------------|------------|
| `zscore_threshold` | Entry signal sensitivity (lower = more trades) | 0.5-2.0 |
| `usd_per_trade` | Position size per trade | 10-100 |
| `find_cointegrated_pairs` | Search for tradeable pairs | true |
| `manage_exits` | Monitor and close positions | true |
| `place_trades` | Execute trades (false = analysis only) | true |

---

## Common Scenarios

### Scenario 1: Backtest Before Trading

```bash
# Test strategy on historical data
curl -X POST http://localhost:8889/api/v1/bots/quick-deploy \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "backtest-1",
    "instance_name": "Backtest Run",
    "strategy_params": {
      "zscore_threshold": 1.5,
      "usd_per_trade": 50.0
    },
    "backtest_config": {
      "start_date": "2025-09-01",
      "end_date": "2025-10-31"
    }
  }'

# Check results
curl http://localhost:8889/api/v1/bots/backtest-1/stats
```

### Scenario 2: Run Multiple Bots

```bash
# Bot 1: Conservative (fewer, safer trades)
curl -X POST http://localhost:8889/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "bot-conservative",
    "instance_name": "Conservative Bot",
    "credentials": { "address": "...", "mnemonic": "..." },
    "trading_params": {
      "is_testnet": true,
      "zscore_threshold": 2.0,
      "usd_per_trade": 10.0
    }
  }'

curl -X POST http://localhost:8889/api/v1/bots/bot-conservative/start

# Bot 2: Aggressive (more, frequent trades)
curl -X POST http://localhost:8889/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "bot-aggressive",
    "instance_name": "Aggressive Bot",
    "credentials": { "address": "...", "mnemonic": "..." },
    "trading_params": {
      "is_testnet": true,
      "zscore_threshold": 1.0,
      "usd_per_trade": 50.0
    }
  }'

curl -X POST http://localhost:8889/api/v1/bots/bot-aggressive/start

# Check both
curl http://localhost:8889/api/v1/bots
```

### Scenario 3: Monitor in Real-Time

**Python WebSocket Monitor:**

```python
import asyncio
import websockets
import json

async def monitor():
    uri = "ws://localhost:8889/api/v1/bots/my-first-bot/positions/live"
    
    async with websockets.connect(uri) as ws:
        print("Connected! Monitoring positions...")
        
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            
            if data['type'] == 'position_opened':
                print(f"✓ NEW: {data['position']['market_1']}/{data['position']['market_2']}")
            
            elif data['type'] == 'position_updated':
                p = data['updates']
                print(f"  P&L: ${p['unrealized_pnl_usd']:.2f}")
            
            elif data['type'] == 'position_closed':
                print(f"✗ CLOSED: ${data['exit_info']['realized_pnl_usd']:.2f}")

asyncio.run(monitor())
```

---

## Troubleshooting

### Issue: "Address already in use"

```bash
# Kill existing process on port 8000
lsof -i :8000
kill -9 <PID>
```

### Issue: "Bot won't start trading"

```bash
# Check logs for errors (authenticated request)
# 1. Check dYdX connection
# 2. Verify testnet funds available
# 3. Check credentials are correct
# 4. Verify Bearer token is valid
curl http://localhost:8000/api/v1/bots/my-first-bot \
  -H "Authorization: Bearer $TOKEN"
# Look at status and last_activity
```

### Issue: "No cointegrated pairs found"

```bash
# Bot searches for correlated pairs
# If none found, try:
# 1. Increase analysis window (stats_window: 30)
# 2. Lower threshold (zscore_threshold: 1.0)
# 3. Wait longer (analysis takes time)
```

---

## Next Steps

1. **Explore Full API:** Visit <http://localhost:8000/docs> (authenticate with Bearer token)
2. **Setup 2FA Security:** See `AUTHENTICATION_GUIDE.md` for two-factor authentication
3. **Read Full Guide:** See `API_USAGE_GUIDE.md` for complete API reference
4. **Setup Production:** See `SETUP_AND_DEPLOYMENT.md` for secure deployment
5. **Monitor Real-Time:** See `REALTIME_SYSTEM.md` for live monitoring

---

## Key Files

| File | Purpose |
|------|---------|
| `bot_api_server.py` | Main API server |
| `config.py` | Trading configuration |
| `constants.py` | Feature flags |
| `API_USAGE_GUIDE.md` | Complete API reference |
| `SETUP_AND_DEPLOYMENT.md` | Production setup |

---

## Support

**All endpoints documented at:** <http://localhost:8000/docs> (Swagger UI with Authentication)

**Authentication Setup:**

1. **Complete Guide:** See `AUTHENTICATION_GUIDE.md` for comprehensive setup
2. **API Reference:** Check `API_USAGE_GUIDE.md` for detailed endpoints
3. **Production Setup:** See `SETUP_AND_DEPLOYMENT.md` for secure deployment

**Need help?**

1. Check `AUTHENTICATION_GUIDE.md` for authentication issues
2. Check `API_USAGE_GUIDE.md` for detailed API reference
3. Check `SETUP_AND_DEPLOYMENT.md` for troubleshooting
4. Review bot logs for error messages

---

**Ready to trade securely? Run the commands above and start earning!** 🚀🔒
