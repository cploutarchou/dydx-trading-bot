# Developer Reference - Complete Technical Guide

**Comprehensive technical reference for developers**

**Version:** 1.0.0 | **Last Updated:** November 2025 | **Status:** Production Ready

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Bot Instance Management](#bot-instance-management)
3. [Bot Lifecycle States](#bot-lifecycle-states)
4. [API Request/Response Schemas](#api-requestresponse-schemas)
5. [WebSocket Message Formats](#websocket-message-formats)
6. [Error Handling](#error-handling)
7. [Complete Code Examples](#complete-code-examples)
8. [Performance Optimization](#performance-optimization)

---

## System Architecture

### Component Diagram

```
┌─────────────────────────────────────────────┐
│  Client Application / Dashboard             │
│  REST, WebSocket, Browser                   │
└────────────────┬────────────────────────────┘
                 │
        ┌────────▼────────┐
        │ FastAPI Server  │
        │ port 8889       │
        └────────┬────────┘
                 │
    ┌────────────┼────────────┬──────────────┐
    │            │            │              │
    ▼            ▼            ▼              ▼
┌────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐
│  Bot   │  │Database│  │WebSocket │  │Backtest  │
│Manager │  │ ORM    │  │ Server   │  │Engine    │
└────────┘  └────────┘  └──────────┘  └──────────┘
    │            │
    │            ▼
    │    ┌──────────────────┐
    │    │SQLite/PostgreSQL │
    │    └──────────────────┘
    │
    ▼
┌──────────────────────────┐
│  Bot Subprocess Instances │
│  (Per config)            │
│  • dYdX Client           │
│  • Trading Logic         │
│  • Real-Time Monitoring  │
└──────────────────────────┘
```

### Data Flow

**Trading Flow:**

```
dYdX API → Bot Process → DB Persistence
                     ↓
              Real-Time Service
                     ↓
          WebSocket Broadcast
                     ↓
           Client (Dashboard)
```

---

## Bot Instance Management

### Creating Bot Instance

**Schema:**

```python
BotInstanceConfig = {
    "instance_id": str,           # Unique identifier
    "instance_name": str,         # Display name
    "credentials": {
        "address": str,           # dYdX wallet
        "mnemonic": str           # BIP39 mnemonic
    },
    "trading_params": {
        "is_testnet": bool,
        "zscore_threshold": float,
        "usd_per_trade": float,
        # ... other params
    }
}
```

**Database Record Created:**

- bot_instances table
- Links to all trading data
- References for jobs, trades, positions

### Lifecycle Tracking

```python
BotInstance = {
    "instance_id": str,
    "status": BotStatus,          # stopped|starting|running|stopping|error
    "process_id": int,            # PID when running
    "created_at": datetime,
    "started_at": datetime,
    "stopped_at": datetime,
    "config": dict,               # Full configuration
}
```

---

## Bot Lifecycle States

### State Machine

```
    ┌─────────┐
    │ STOPPED │ ◄─────────────────────┐
    └────┬────┘                       │
         │ POST /start                │
         ▼                            │
    ┌─────────────┐                   │
    │  STARTING   │                   │
    └────┬────────┘                   │
         │ (process launched)         │
         ▼                            │
    ┌─────────┐                       │
    │ RUNNING │                       │
    └────┬────┘                       │
         │ POST /stop                 │
         ▼                            │
    ┌─────────────┐                   │
    │  STOPPING   │                   │
    └────┬────────┘                   │
         │ (cleanup)                  │
         └──────────────────────────→ │
                                      │
    ERROR state (process crash/error) ──┘
```

### Waiting for State Change

```python
import requests
import time

def wait_for_status(instance_id, target_status, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        response = requests.get(
            f"http://localhost:8889/api/v1/bots/{instance_id}"
        )
        status = response.json()['data']['status']
        
        if status == target_status:
            return True
        elif status == 'error':
            raise RuntimeError("Bot entered error state")
        
        time.sleep(1)
    
    raise TimeoutError(f"Timeout waiting for {target_status}")

# Usage
wait_for_status("bot-1", "running", timeout=30)
```

---

## API Request/Response Schemas

### Standard Response Wrapper

```python
{
    "success": bool,
    "message": str,
    "data": { ... },              # Endpoint-specific
    "error_code": str,            # On error only
    "timestamp": "ISO8601"
}
```

### Status Codes

- `200` - Success
- `400` - Bad Request (invalid input)
- `404` - Not Found (resource doesn't exist)
- `409` - Conflict (invalid state)
- `500` - Server Error

### Bot Status Enum

```python
class BotStatus(str, Enum):
    STOPPED = "stopped"           # Not running
    STARTING = "starting"         # Process launching
    RUNNING = "running"           # Active trading
    STOPPING = "stopping"         # Shutting down
    ERROR = "error"               # Failed/crashed
```

### Trading Parameters Schema

```python
TradingParameters = {
    "is_testnet": bool,           # Network selection
    
    # Execution Flags
    "abort_all_positions": bool,  # Close on startup
    "find_cointegrated_pairs": bool,  # Run analysis
    "manage_exits": bool,         # Monitor positions
    "place_trades": bool,         # Execute trades
    
    # Strategy
    "resolution_timeframe": str,  # "1HOUR", "4HOURS", etc.
    "strategy": str,              # "cointegration"
    
    # Parameters
    "stats_window": int,          # 5-100 days
    "max_half_life": int,         # 1-168 hours
    "zscore_threshold": float,    # 0.5-5.0
    "usd_per_trade": float,       # 1.0-10000.0
    "usd_min_collateral": float,  # 10.0+
    "close_at_zscore_cross": bool # Exit on mean reversion
}
```

---

## WebSocket Message Formats

### Connection Lifecycle

```
Client → WebSocket Connect
   ↓
Server → Initial State Message
   ↓
Client ← Stream Messages (updates)
   ↓
Server → Ping (keep-alive)
   ↓
Client → Pong
   ↓
Client → WebSocket Close
```

### Position Stream Messages

**Initial State:**

```json
{
    "type": "initial_state",
    "timestamp": "ISO8601",
    "positions": [
        {
            "id": int,
            "position_id": "POS-001",
            "market_1": "BTC-USD",
            "market_2": "ETH-USD",
            "status": "OPEN",
            "entry_price_m1": float,
            "current_price_m1": float,
            "entry_price_m2": float,
            "current_price_m2": float,
            "size_m1": float,
            "size_m2": float,
            "unrealized_pnl_usd": float,
            "z_score": float,
            "hedge_ratio": float,
            "opened_at": "ISO8601"
        }
    ]
}
```

**Position Updated:**

```json
{
    "type": "position_updated",
    "timestamp": "ISO8601",
    "position_id": "POS-001",
    "updates": {
        "current_price_m1": float,
        "current_price_m2": float,
        "unrealized_pnl_usd": float,
        "z_score": float
    }
}
```

**Position Closed:**

```json
{
    "type": "position_closed",
    "timestamp": "ISO8601",
    "position_id": "POS-001",
    "exit_info": {
        "exit_price_m1": float,
        "exit_price_m2": float,
        "realized_pnl_usd": float,
        "duration_hours": float,
        "exit_reason": "zscore_cross"
    }
}
```

---

## Error Handling

### Error Response Example

```json
{
    "success": false,
    "message": "Bot instance 'invalid-id' not found",
    "data": null,
    "error_code": "NOT_FOUND",
    "timestamp": "ISO8601"
}
```

### Python Error Handling Pattern

```python
import requests
from typing import Optional, Dict, Any

def api_call(
    method: str,
    endpoint: str,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """Safe API call with error handling"""
    
    try:
        url = f"http://localhost:8889{endpoint}"
        
        response = requests.request(
            method=method.upper(),
            url=url,
            timeout=30,
            **kwargs
        )
        
        # Handle different error codes
        if response.status_code == 404:
            raise Exception("Resource not found")
        elif response.status_code == 409:
            error_msg = response.json().get('message', 'Conflict')
            raise Exception(f"Conflict: {error_msg}")
        elif response.status_code >= 400:
            error_data = response.json()
            raise Exception(
                f"Error {response.status_code}: "
                f"{error_data.get('message', 'Unknown')}"
            )
        
        return response.json()
    
    except requests.exceptions.Timeout:
        raise Exception("API request timed out")
    except requests.exceptions.ConnectionError:
        raise Exception("Cannot connect to API")
    except Exception as e:
        raise Exception(f"API error: {str(e)}")
```

---

## Complete Code Examples

### Example 1: Bot Deployment Workflow

```python
import requests
import time

class BotDeployer:
    def __init__(self, api_url="http://localhost:8889"):
        self.api_url = api_url
    
    def deploy_bot(self, config):
        """Complete deployment workflow"""
        
        # 1. Create bot
        print("Creating bot instance...")
        response = requests.post(
            f"{self.api_url}/api/v1/bots",
            json=config
        )
        bot_data = response.json()['data']
        instance_id = bot_data['instance_id']
        print(f"✓ Bot created: {instance_id}")
        
        # 2. Start bot
        print("Starting bot...")
        requests.post(f"{self.api_url}/api/v1/bots/{instance_id}/start")
        
        # 3. Wait for running status
        for attempt in range(30):
            response = requests.get(
                f"{self.api_url}/api/v1/bots/{instance_id}"
            )
            status = response.json()['data']['status']
            
            if status == 'running':
                print("✓ Bot is running")
                break
            elif status == 'error':
                print("✗ Bot failed to start")
                return False
            
            time.sleep(1)
        
        return True
    
    def get_realtime_stats(self, instance_id):
        """Get current bot statistics"""
        response = requests.get(
            f"{self.api_url}/api/v1/bots/{instance_id}/stats"
        )
        return response.json()['data']

# Usage
deployer = BotDeployer()
config = {
    "instance_id": "prod-bot-001",
    "instance_name": "Production Bot 1",
    "credentials": { "address": "...", "mnemonic": "..." },
    "trading_params": {
        "is_testnet": False,
        "zscore_threshold": 1.5,
        "usd_per_trade": 100.0
    }
}

deployer.deploy_bot(config)
```

### Example 2: Async Multi-Bot Monitoring

```python
import asyncio
import aiohttp

class AsyncBotMonitor:
    def __init__(self, api_url="http://localhost:8889"):
        self.api_url = api_url
    
    async def get_bot_stats(self, session, instance_id):
        """Fetch bot stats asynchronously"""
        async with session.get(
            f"{self.api_url}/api/v1/bots/{instance_id}/stats"
        ) as response:
            return await response.json()
    
    async def monitor_all_bots(self, bot_ids):
        """Monitor multiple bots concurrently"""
        async with aiohttp.ClientSession() as session:
            # Fetch all stats in parallel
            tasks = [
                self.get_bot_stats(session, bot_id)
                for bot_id in bot_ids
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Display results
            for bot_id, result in zip(bot_ids, results):
                stats = result['data']
                print(f"{bot_id}:")
                print(f"  Trades: {stats['total_trades']}")
                print(f"  P&L: ${stats['total_pnl_usd']:.2f}")
                print(f"  Win Rate: {stats['win_rate']:.2%}")

# Usage
async def main():
    monitor = AsyncBotMonitor()
    await monitor.monitor_all_bots(["bot-1", "bot-2", "bot-3"])

asyncio.run(main())
```

### Example 3: WebSocket Real-Time Monitoring

```python
import asyncio
import websockets
import json

async def monitor_positions(bot_id):
    """Connect to position WebSocket and process updates"""
    
    uri = f"ws://localhost:8889/api/v1/bots/{bot_id}/positions/live"
    
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {bot_id}")
        
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                if data['type'] == 'initial_state':
                    print(f"Initial positions: {len(data['positions'])}")
                
                elif data['type'] == 'position_opened':
                    pos = data['position']
                    print(f"✓ OPENED: {pos['position_id']}")
                
                elif data['type'] == 'position_updated':
                    print(f"  • {data['position_id']}: "
                          f"${data['updates']['unrealized_pnl_usd']:.2f}")
                
                elif data['type'] == 'position_closed':
                    print(f"✗ CLOSED: {data['position_id']} "
                          f"P&L: ${data['exit_info']['realized_pnl_usd']:.2f}")
            
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break

asyncio.run(monitor_positions("bot-1"))
```

---

## Performance Optimization

### Connection Pooling

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_pooled_session():
    """Create session with connection pooling"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=1
    )
    
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

session = create_pooled_session()
response = session.get("http://localhost:8889/api/v1/bots")
```

### Caching Strategy

```python
import time
from functools import wraps

class APICache:
    def __init__(self, ttl=60):
        self.cache = {}
        self.ttl = ttl
    
    def cached_call(self, key, func, *args, **kwargs):
        """Call with caching"""
        
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
        
        result = func(*args, **kwargs)
        self.cache[key] = (result, time.time())
        return result

# Usage
cache = APICache(ttl=30)
result = cache.cached_call(
    "bot-1:stats",
    requests.get,
    "http://localhost:8889/api/v1/bots/bot-1/stats"
)
```

### Batch Operations

```python
def batch_create_bots(configs, batch_size=5):
    """Create multiple bots with batching"""
    
    results = []
    for i in range(0, len(configs), batch_size):
        batch = configs[i:i + batch_size]
        
        # Create batch in parallel
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=batch_size
        ) as executor:
            futures = [
                executor.submit(create_bot, config)
                for config in batch
            ]
            
            results.extend([
                future.result() for future in futures
            ])
    
    return results
```

---

**Last Updated:** November 2, 2025  
**Status:** Production Ready  
**For questions:** See API_USAGE_GUIDE.md or SETUP_AND_DEPLOYMENT.md
