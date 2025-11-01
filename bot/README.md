# dYdX Trading Bot - API-Controlled Multi-Instance System

## 🎯 Overview

Successfully transformed the dYdX trading bot into a **multi-instance, API-controlled system** that allows:

- 🚀 **API Control**: Start/stop bots via REST API calls
- 🔄 **Multi-Instance Support**: Run multiple bots simultaneously with isolated configurations  
- ⚙️ **Dynamic Configuration**: Trading parameters sent via API payload (not stored in .env)
- 🌐 **Web Interface**: FastAPI server with automatic documentation
- 🏗️ **Proper Architecture**: Separated static vs dynamic configuration

## 📁 Project Structure

```
bot/
├── 📄 API System
│   ├── bot_api_server.py          # FastAPI server with REST endpoints
│   ├── bot_api_models.py          # Pydantic models for API validation
│   └── bot_instance_manager.py    # Multi-instance management
│
├── 🔧 Configuration
│   ├── .env                       # Static environment variables
│   ├── example.env               # Template with all variables
│   └── config.py                 # Configuration management
│
├── 🤖 Bot Core (Original Files)
│   ├── main.py                   # Original single-instance bot
│   ├── main_instance.py          # Instance-aware bot (WIP)
│   ├── func_*.py                # Trading logic functions
│   └── constants.py             # Trading constants
│
├── 🚀 Startup Scripts
│   ├── start_api.py             # API server startup
│   ├── run_api.sh              # Bash script to start API
│   └── requirements.txt         # Python dependencies
│
├── 📚 Documentation  
│   └── .github/copilot-instructions.md  # AI coding agent instructions
│
└── 📊 Runtime Data
    └── pair_history/           # Historical trading pair data
```

## 🔑 Key Features

### 1. API-Controlled Bot Management

- **POST /bots** - Create new bot instance
- **GET /bots** - List all bot instances  
- **GET /bots/{bot_id}** - Get specific bot status
- **POST /bots/{bot_id}/start** - Start bot instance
- **POST /bots/{bot_id}/stop** - Stop bot instance
- **DELETE /bots/{bot_id}** - Remove bot instance
- **POST /bots/quick-deploy** - One-click bot deployment

### 2. Multi-Instance Architecture

- Each bot runs as separate process with unique ID
- Isolated state files: `bot_agents_{instance_id}.json`
- Independent configuration and logging
- Process-level isolation for stability

### 3. Configuration Management

**Static (.env file):**

```bash
# Telegram notifications
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Infrastructure settings  
LOG_LEVEL=INFO
LOG_FILE=bot_{instance_id}.log
```

**Dynamic (API payload):**

```json
{
  "credentials": {
    "stark_private_key": "0x...",
    "dydx_private_key": "0x...", 
    "wallet_address": "0x..."
  },
  "trading_params": {
    "is_testnet": true,
    "usd_per_trade": 100,
    "zscore_threshold": 1.5,
    "strategy": "statistical_arbitrage"
  },
  "bot_settings": {
    "abort_all_positions": false,
    "find_cointegrated_pairs": true,
    "manage_exits": true,
    "place_trades": true
  }
}
```

## 🚀 Quick Start

### 1. Start the API Server

```bash
# Method 1: Using the startup script
./run_api.sh

# Method 2: Manual activation
source venv/bin/activate
python start_api.py
```

### 2. Access the API

- **Web UI**: <http://localhost:8000>
- **API Docs**: <http://localhost:8000/docs>
- **Health Check**: <http://localhost:8000/health>

### 3. Deploy a Bot Instance

```bash
curl -X POST "http://localhost:8000/bots/quick-deploy" \
  -H "Content-Type: application/json" \
  -d '{
    "credentials": {
      "stark_private_key": "0x...",
      "dydx_private_key": "0x...",
      "wallet_address": "0x..."
    },
    "trading_params": {
      "is_testnet": true,
      "usd_per_trade": 100,
      "zscore_threshold": 1.5
    }
  }'
```

## 📊 API Endpoints Reference

### Bot Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/bots` | List all bot instances |
| POST | `/bots` | Create new bot instance |
| GET | `/bots/{bot_id}` | Get bot status |
| POST | `/bots/{bot_id}/start` | Start specific bot |
| POST | `/bots/{bot_id}/stop` | Stop specific bot |
| DELETE | `/bots/{bot_id}` | Delete bot instance |

### Quick Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/bots/quick-deploy` | Deploy and start bot in one call |
| POST | `/bots/stop-all` | Emergency stop all bots |
| GET | `/system/status` | Overall system status |

### Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | API server health check |
| GET | `/bots/{bot_id}/logs` | Get bot logs (if implemented) |

## 🔧 Environment Configuration

### Required Environment Variables

**Static Configuration (.env):**

```bash
# Telegram Settings (Optional)
TELEGRAM_TOKEN=              # Telegram bot token for notifications
TELEGRAM_CHAT_ID=           # Chat ID for notifications

# Logging Settings
LOG_LEVEL=INFO              # Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_FILE=bot_{instance_id}.log  # Log file pattern

# File Paths (Support {instance_id} placeholder)
BOT_AGENTS_FILE=bot_agents_{instance_id}.json
BOT_PAIRS_FILE=cointegrated_pairs_{instance_id}.json

# Database Settings (if using database)
DATABASE_URL=               # Database connection string
```

**Dynamic Configuration (API):**

```json
{
  "credentials": {
    "stark_private_key": "Required - dYdX Stark private key",
    "dydx_private_key": "Required - dYdX private key", 
    "wallet_address": "Required - Wallet address"
  },
  "trading_params": {
    "is_testnet": true,        // Use testnet (true) or mainnet (false)
    "usd_per_trade": 100,      // USD amount per trade
    "zscore_threshold": 1.5,   // Z-score threshold for entries
    "max_half_life": 24,       // Maximum cointegration half-life
    "strategy": "statistical_arbitrage"  // Trading strategy
  },
  "bot_settings": {
    "abort_all_positions": false,      // Close positions on startup
    "find_cointegrated_pairs": true,   // Run cointegration analysis
    "manage_exits": true,              // Manage existing positions
    "place_trades": true               // Place new trades
  }
}
```

## 🔄 Development Workflow

### Adding New Features

1. **API Changes**: Update `bot_api_models.py` and `bot_api_server.py`
2. **Bot Logic**: Modify functions in `func_*.py` files
3. **Configuration**: Add new settings to models
4. **Testing**: Use `/docs` endpoint for API testing

### Running Multiple Bots

```python
# Bot 1: Conservative strategy
{
  "trading_params": {
    "usd_per_trade": 50,
    "zscore_threshold": 2.0
  }
}

# Bot 2: Aggressive strategy  
{
  "trading_params": {
    "usd_per_trade": 200,
    "zscore_threshold": 1.0
  }
}
```

## 🛡️ Security Considerations

1. **API Security**: No authentication implemented (add JWT/API keys for production)
2. **Credentials**: Never log private keys or sensitive data
3. **Environment**: Use separate .env files for different environments
4. **Process Isolation**: Each bot runs in separate process for security

## 📈 Monitoring & Logging

- **Instance Logs**: Each bot has separate log file with instance ID
- **API Logs**: FastAPI server logs all requests  
- **Telegram Alerts**: Real-time notifications for bot events
- **Process Monitoring**: psutil integration for system resource monitoring

## 🔮 Future Enhancements

- [ ] Web-based dashboard UI
- [ ] Authentication and authorization
- [ ] Database integration for persistent storage
- [ ] Real-time WebSocket updates
- [ ] Performance metrics and analytics
- [ ] Automated scaling based on market conditions
- [ ] Strategy backtesting integration

## 📝 Notes

- **Type Safety**: Pydantic models ensure API data validation
- **Error Handling**: Comprehensive error handling with meaningful messages
- **Scalability**: Architecture supports horizontal scaling
- **Maintainability**: Clean separation of concerns and modular design

---

**🎉 Ready to run multiple dYdX trading bots simultaneously with full API control!**
